"""시장 역할: 원문 수집 → 근거 추출·검증 → 평가 → 제한된 보완."""
import re
from hashlib import sha256
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .schemas import Analysis, CRITERIA, MarketResult, unknown, Extraction, DraftAnalysis, DraftAssessment
from .tools import Budget, ProviderError
from .collection import collect_sources
from .search_plan import initial_questions, repair_questions
from .research import annotate
from .validation import validate_analysis, normalized
from .claims import validate_claims, materialize, pool_dispositions, recover_previous, previous_draft, review_claims
from .sources import content_quality


class RunState(TypedDict, total=False):
    data: object
    round: int
    evidence: dict
    sources: dict
    analysis: Analysis
    errors: list
    history: list
    queries: list
    fatal: bool
    claim_pool: dict
    candidate_pool: dict
    claim_review_log: dict
    reviews: dict
    extraction_errors: list
    composition_errors: list
    repair_kind: str
    repair_used: bool
    model_successes: int
    compose_successes: int
    draft: DraftAnalysis
    result: MarketResult
    source_linked_drafts: dict
    retained_draft_findings: list
    review_notes: list


def _claim_key(claim):
    citation = claim.citation
    identity = '\n'.join([claim.tech_id, claim.criterion_id, citation.evidence_id,
                          normalized(citation.quote)])
    return 'CLM-' + sha256(identity.encode()).hexdigest()[:16]


def _retained_findings(state):
    """Keep source-linked model content without promoting it to accepted evidence."""
    candidates = dict(state.get('source_linked_drafts', {}))
    for key, claim in state.get('candidate_pool', {}).items():
        candidates.setdefault(key, {'claim': claim.model_dump(mode='json'), 'review_notes': []})
    rows = []
    for key, candidate in candidates.items():
        if state['claim_dispositions'].get(key) == 'included':
            continue
        claim = candidate['claim']
        citation = claim['citation']
        if citation['evidence_id'] not in state['evidence']:
            continue
        notes = list(candidate.get('review_notes', []))
        disposition = state['claim_dispositions'].get(key)
        if disposition:
            notes.append(disposition)
        rows.append({
            'id': key, 'technology_ids': [claim['tech_id']],
            'criterion_id': claim['criterion_id'], 'text': claim['statement'],
            'basis': claim['basis'], 'source_scope': claim['relation_to_technology'],
            'conditions': claim['conditions'], 'metric': claim.get('metric'),
            'evidence_ids': [citation['evidence_id']], 'supports': [citation],
            'review_status': 'needs_review',
            'review_notes': list(dict.fromkeys(notes or ['출처 연결을 보존한 미확정 분석입니다.'])),
        })
    # Preserve the model's assessment wording too when canonical materialization
    # replaced it. Quotes remain the actual linked claim quotes, never new ones.
    for index, draft in enumerate(state['draft'].assessments):
        linked = [candidates[key]['claim'] for key in draft.claim_ids if key in candidates]
        supports = [claim['citation'] for claim in linked
                    if claim['citation']['evidence_id'] in state['evidence']]
        final = next((row for row in state['analysis'].assessments
                      if (row.tech_id, row.criterion_id) == (draft.tech_id, draft.criterion_id)), None)
        if not supports or not draft.judgment.strip() or (final and final.judgment == draft.judgment):
            continue
        notes = [error['code'] for error in state.get('composition_errors', [])
                 if error.get('tech_id') == draft.tech_id
                 and error.get('criterion_id') == draft.criterion_id]
        rows.append({
            'id': f'MARKET-DRAFT-{index + 1:03d}', 'technology_ids': [draft.tech_id],
            'criterion_id': draft.criterion_id, 'text': draft.judgment,
            'basis': draft.basis, 'conditions': draft.conditions,
            'evidence_ids': list(dict.fromkeys(c['evidence_id'] for c in supports)),
            'supports': supports, 'review_status': 'needs_review',
            'review_notes': list(dict.fromkeys(notes + ['근거 연결과 함께 보존한 모델 평가 초안입니다.'])),
        })
    return rows


def relevant_candidate(row, tech):
    """일반 제품 문서를 걸러내는 최소 검사. 사실성·동일 기술 여부는 별도 평가한다."""
    text = f"{row.get('title', '')} {row.get('content', '')}"
    # RDKV는 TV/셋톱박스 플랫폼에서도 쓰는 약어다. 이름 일치만으로 채택하지 않는다.
    if tech.approach == 'SW' and re.search(r'\brdkv\b|rdk.video', text, re.I):
        return bool(re.search(r'kv[\s_-]*cache|rate.distortion|\bllm\b|language model|quantization|attention', text, re.I))
    return bool(re.search(r"kv[\s_-]*cache|key[\s_-]*value[\s_-]*cache|\bcxl\b|compute express link|"
        r"photonic.{0,30}memory|llm.{0,30}(memory|inference)|ai[\s_-]+(server|infrastructure|accelerator)|"
        r"추론.{0,15}(메모리|인프라)|인공지능.{0,10}서버", text, re.I))


def run_market(data, web, analyst, *, mode="live", budget=None, auto_repair=True,
               round_number=0, previous=None, existing_evidence=None, existing_claims=None):
    if round_number not in {0,1}:
        raise ValueError('round_number must be 0 or 1')
    budget = budget or Budget(data.limits)
    budget.constrain(data.limits)
    initial_evidence = {k:e.model_copy(deep=True) for k,e in {**data.evidence,**(existing_evidence or {})}.items()}
    for e in initial_evidence.values():
        if e.access_status=='full_text' and e.content_status=='unchecked':
            tech=next((data.technologies[t] for t in e.tech_ids if t in data.technologies),next(iter(data.technologies.values())))
            e.content_status,e.content_reason=content_quality(e.excerpt,e.url,tech)
    initial_pool,_=validate_claims(data,[*recover_previous(previous),*(existing_claims or {}).values()],initial_evidence)

    def blank_draft():
        reason = '미확인: fixture 모드에는 실제 시장 근거가 없습니다' if mode=='fixture' else '이번 조사에서 선정 기술 자체를 판단할 직접 근거를 확인하지 못함'
        return DraftAnalysis(assessments=[DraftAssessment(tech_id=t,criterion_id=c,judgment=reason,
            verdict='unknown',basis='unknown',claim_ids=[],conditions=[],gaps=[reason]) for t in data.technologies for c in CRITERIA],followup_questions=[])

    def collect(state):
        rows=[r.model_copy(deep=True) for r in state['analysis'].assessments]
        covered={(c.tech_id,c.criterion_id) for c in state['claim_pool'].values()}
        for r in rows:
            if (r.tech_id,r.criterion_id) in covered:
                r.verdict,r.gaps='conditional',[]  # 조사 우선순위만 계산; 보고서 판정과 분리
        questions=initial_questions(data) if state['round']==0 else repair_questions(data,rows,[],state['queries'])
        return collect_sources(state,data,web,budget,questions,relevant_candidate)

    def extract(state):
        update={'history':state['history']+['extract']}
        eligible={k:e for k,e in state['evidence'].items() if e.access_status=='full_text' and e.content_status=='substantive'}
        fresh=set(eligible)-state['reviews'].keys()
        if state['fatal'] or not eligible or not budget.remaining('llm') or (not fresh and state['repair_kind']!='extract'):
            return update
        try:
            answer=budget.call('llm',lambda:Extraction.model_validate(analyst.extract(data,state['evidence'],
                previous=state['claim_pool'],issues=state['extraction_errors'])))
            added,errors=validate_claims(data,answer.claims,state['evidence'])
            retained=dict(state.get('source_linked_drafts',{}))
            for claim in answer.claims:
                if claim.citation.evidence_id in state['evidence']:
                    retained[_claim_key(claim)]={
                        'claim':claim.model_dump(mode='json'),
                        'review_notes':[error['code'] for error in errors
                            if (error.get('tech_id'),error.get('criterion_id'),error.get('evidence_id'))
                            == (claim.tech_id,claim.criterion_id,claim.citation.evidence_id)]}
            update['source_linked_drafts']=retained
            reviews={r.evidence_id:r.model_dump() for r in answer.reviews if r.evidence_id in eligible}
            for eid in eligible:
                if eid not in reviews:
                    errors.append(dict(stage='claims',code='missing_source_review',evidence_id=eid))
            claimed_ids={c.citation.evidence_id for c in answer.claims}
            for eid,r in reviews.items():
                if (r['outcome']=='claims_extracted') != (eid in claimed_ids):
                    errors.append(dict(stage='claims',code='source_review_mismatch',evidence_id=eid))
            pool={**state['claim_pool'],**added}
            analysis,_=materialize(data,blank_draft(),pool)
            update.update(claim_pool=pool,reviews={**state['reviews'],**reviews},analysis=analysis,
                extraction_errors=errors,model_successes=state['model_successes']+1,
                errors=[e for e in state['errors'] if e['stage'] not in {'claims','llm_extract'}]+errors)
        except ProviderError as exc:
            error=dict(stage='llm_extract',code=exc.code)
            update.update(extraction_errors=[error],errors=state['errors']+[error],fatal=exc.fatal)
        return update

    def can_repair(state):
        return auto_repair and not state['repair_used'] and not state['fatal'] and budget.remaining('llm')>0

    def after_extract(state):
        # 유효 근거가 있으면 평가 작성 1회를 우선 확보한다.
        room=budget.remaining('llm')-(1 if state['claim_pool'] else 0)
        if can_repair(state) and room>0:
            if state['extraction_errors']:
                return 'repair_extract'
            covered={(c.tech_id,c.criterion_id) for c in state['claim_pool'].values()}
            if len(covered)<len(data.technologies)*len(CRITERIA) and budget.remaining('search') and budget.remaining('extract'):
                return 'repair_collect'
        return 'compose'

    def compose(state):
        update={'history':state['history']+['compose']}
        draft=state.get('draft',blank_draft())
        current=[e for e in state['errors'] if e['stage'] not in {'compose','validate','llm_compose'}]
        errors=[]
        input_pool=state['candidate_pool'] if state['repair_kind']=='compose' else state['claim_pool']
        pool={k:c for k,c in input_pool.items() if k in initial_pool}
        candidates={**state.get('candidate_pool',{}),**input_pool}
        review_log=dict(state.get('claim_review_log',{}))
        if input_pool and not state['fatal']:
            if budget.remaining('llm'):
                try:
                    draft=budget.call('llm',lambda:DraftAnalysis.model_validate(analyst.compose(data,input_pool,
                        previous=state.get('draft'),issues=state['composition_errors'])))
                    update['model_successes']=state['model_successes']+1
                    update['compose_successes']=state['compose_successes']+1
                    pool,log,review_errors=review_claims(input_pool,draft.claim_reviews)
                    review_log.update(log)
                    errors+=review_errors
                except ProviderError as exc:
                    errors.append(dict(stage='llm_compose',code=exc.code))
                    update['fatal']=exc.fatal
            else:
                errors.append(dict(stage='llm_compose',code='budget_exhausted:llm'))
        for key in candidates:
            if key not in pool and key not in review_log:
                review_log[key]='unreviewed: 평가 단계가 완료되지 않음'
        analysis,link_errors=materialize(data,draft,pool)
        analysis,validation_errors=validate_analysis(data,analysis,state['evidence'])
        errors+=link_errors+validation_errors
        # 인용 수정 실패도 미확인의 이유로 보존한다.
        current+=errors
        reviewed={}
        for c in pool.values():
            reviewed.setdefault((c.tech_id,c.criterion_id),[]).append(c.citation.evidence_id)
        analysis=annotate(analysis,data,state['evidence'],state['queries'],current,budget,
            state['model_successes']>0,reviewed=reviewed)
        update.update(draft=draft,analysis=analysis,composition_errors=errors,errors=current,
            claim_pool=pool,candidate_pool=candidates,claim_review_log=review_log)
        return update

    def after_compose(state):
        return 'repair_compose' if state['composition_errors'] and can_repair(state) else 'finish'

    def repair(kind):
        def action(state):
            return dict(round=1,repair_used=True,repair_kind=kind,history=state['history']+['repair_'+kind])
        return action

    def finish(state):
        statuses={t:'completed' if all(r.verdict!='unknown' for r in state['analysis'].assessments if r.tech_id==t)
            else 'unknown' for t in data.technologies}
        api_failure=any(e['stage'].startswith('llm') or e['stage'] in {'search','extract'} for e in state['errors']
            if not e['code'].startswith('budget_'))
        failed=state['fatal'] or (state['model_successes']==0 and api_failure)
        result=MarketResult(status='failed' if failed else ('completed' if all(v=='completed' for v in statuses.values()) else 'unknown'),
            round=state['round'],assessments=state['analysis'].assessments,followup_questions=state['analysis'].followup_questions,
            technology_status=statuses,errors=state['errors'],usage=dict(budget.used),mode=mode)
        return {'result':result,'history':state['history']+['finish']}

    graph=StateGraph(RunState)
    for name,action in [('collect',collect),('extract',extract),('compose',compose),('finish',finish)]:
        graph.add_node(name,action)
    for kind in ['collect','extract','compose']:
        graph.add_node('repair_'+kind,repair(kind))
        graph.add_edge('repair_'+kind,kind)
    graph.add_edge(START,'collect')
    graph.add_edge('collect','extract')
    graph.add_conditional_edges('extract',after_extract,{'repair_extract':'repair_extract','repair_collect':'repair_collect','compose':'compose'})
    graph.add_conditional_edges('compose',after_compose,{'repair_compose':'repair_compose','finish':'finish'})
    graph.add_edge('finish',END)
    draft=previous_draft(previous,initial_pool,blank_draft())
    analysis,_=materialize(data,draft,initial_pool)
    state=graph.compile().invoke(dict(data=data,round=round_number,evidence=initial_evidence,sources={},analysis=analysis,
        errors=[],history=[],queries=[],fatal=False,claim_pool=initial_pool,candidate_pool={},claim_review_log={},reviews={},extraction_errors=[],composition_errors=[],source_linked_drafts={},
        repair_kind='',repair_used=round_number==1,model_successes=0,compose_successes=0,draft=draft),config={'recursion_limit':20})
    state.update(events=list(budget.events),initial_evidence_ids=list(initial_evidence),model=getattr(analyst,'model','injected'),
        token_usage=list(getattr(analyst,'usage',[])),output_checks=list(getattr(analyst,'output_checks',[])),
        debug_analyses=list(getattr(analyst,'debug_analyses',[])),claim_dispositions=pool_dispositions(state['claim_pool'],state['analysis']))
    state['claim_dispositions'].update({k:v for k,v in state['claim_review_log'].items() if k not in state['claim_pool']})
    state['retained_draft_findings']=_retained_findings(state)
    state['review_notes']=list(dict.fromkeys(note for row in state['retained_draft_findings']
                                           for note in row['review_notes']))
    return state


def parent_update(state):
    evidence = {eid: e.model_dump(mode="json") for eid, e in state["evidence"].items() if eid not in state["initial_evidence_ids"]}
    documents = {e["doc_id"]: {"url": e["url"], "title": e["title"], "content_hash": e["content_hash"],
        "retrieved_at": e["retrieved_at"], "page_count": None} for e in evidence.values()}
    result = state["result"].model_dump(mode="json")
    return {"assessments": {"market": result}, "documents": documents, "evidence": evidence,
        "retained_draft_findings": state.get("retained_draft_findings", []),
        "review_notes": state.get("review_notes", []),
        "errors": {f'market-{result["round"]}-{i}': error for i, error in enumerate(result["errors"])}}
