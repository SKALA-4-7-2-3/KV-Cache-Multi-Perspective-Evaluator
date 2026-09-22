"""시장 역할: 원문 수집 → 근거 추출·검증 → 평가 → 제한된 보완."""
import re
from typing import TypedDict
from urllib.parse import urlsplit

from langgraph.graph import END, START, StateGraph

from .schemas import Analysis, CRITERIA, MarketResult, unknown, Extraction, DraftAnalysis, DraftAssessment
from .tools import Budget, ProviderError
from .collection import collect_sources
from .search_plan import initial_questions, repair_questions
from .research import annotate
from .validation import validate_analysis
from .premises import technical_evidence
from .claims import validate_claims, materialize, pool_dispositions, recover_previous, previous_draft, review_claims, limit_claims
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
    repairs: dict
    examined: dict
    extraction_history: list


def relevant_candidate(row, tech):
    """일반 제품 문서를 걸러내는 최소 검사. 사실성·동일 기술 여부는 별도 평가한다."""
    text = f"{row.get('title', '')} {row.get('content', '')}"
    # 다른 기술 논문의 벤치마크가 시장 자료의 제한된 원문 슬롯을 독점하지 않게 한다.
    if urlsplit(row.get('url','')).hostname=='arxiv.org' and tech.name.casefold() not in text.casefold():
        return bool(re.search(r'market|economic|adoption|pricing|serving cost',text,re.I))
    # RDKV는 TV/셋톱박스 플랫폼에서도 쓰는 약어다. 이름 일치만으로 채택하지 않는다.
    if tech.approach == 'SW' and re.search(r'\brdkv\b|rdk.video', text, re.I):
        return bool(re.search(r'kv[\s_-]*cache|rate.distortion|\bllm\b|language model|quantization|attention', text, re.I))
    return bool(re.search(r"kv[\s_-]*cache|key[\s_-]*value[\s_-]*cache|\bcxl\b|compute express link|"
        r"photonic.{0,30}memory|llm.{0,30}(memory|inference)|ai[\s_-]+(server|infrastructure|accelerator)|"
        r"추론.{0,15}(메모리|인프라)|인공지능.{0,10}서버", text, re.I))


def run_market(data, web, analyst, *, mode="live", budget=None, auto_repair=True,
               round_number=0, previous=None, existing_evidence=None, existing_claims=None, previous_progress=None):
    if round_number not in {0,1}:
        raise ValueError('round_number must be 0 or 1')
    budget = budget or Budget(data.limits)
    budget.constrain(data.limits)
    progress=previous_progress if previous_progress is not None else budget.progress
    initial_evidence = {k:e.model_copy(deep=True) for k,e in {**data.evidence,**(existing_evidence or {})}.items()}
    for e in initial_evidence.values():
        if e.access_status=='full_text' and e.content_status=='unchecked':
            tech=next((data.technologies[t] for t in e.tech_ids if t in data.technologies),next(iter(data.technologies.values())))
            e.content_status,e.content_reason=content_quality(e.excerpt,e.url,tech)
    initial_pool,_=validate_claims(data,[*recover_previous(previous),*(existing_claims or {}).values()],initial_evidence)

    review_reserve=2 if hasattr(analyst,'audit') else 1

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
        eligible.update(technical_evidence(data,state['evidence']))
        fresh={k for k,e in eligible.items() if k not in state['reviews']
            or not set(e.criteria)<=set(state['reviews'][k].get('criteria',[]))}
        if state['fatal'] or not eligible or not budget.remaining('llm') or (not fresh and not state['extraction_errors']):
            return update
        targets=fresh|{e.get('evidence_id') for e in state['extraction_errors']}
        reviewing={k:e for k,e in eligible.items() if k in targets}
        if not reviewing:
            reviewing=eligible  # 이전 단계 전역 오류의 재시도
        try:
            room=budget.remaining('llm')-review_reserve
            if room <= 0 and state['claim_pool']:
                return update
            answer=budget.call('llm',lambda:Extraction.model_validate(analyst.extract(data,reviewing,
                previous=state['claim_pool'],issues=state['extraction_errors'])),max_attempts=max(1,min(2,room)))
            added,errors=validate_claims(data,answer.claims,state['evidence'])
            reviews={r.evidence_id:r.model_dump() for r in answer.reviews if r.evidence_id in reviewing}
            for eid in reviewing:
                if eid not in reviews:
                    errors.append(dict(stage='claims',code='missing_source_review',evidence_id=eid))
            claimed_ids={c.citation.evidence_id for c in added.values()}
            examined={k:list(v) for k,v in state['examined'].items()}
            for eid,r in reviews.items():
                r['outcome']='claims_extracted' if eid in claimed_ids else 'no_market_claim'
                for tech_id in eligible[eid].tech_ids:
                    for criterion in r.get('criteria',[]):
                        examined.setdefault((tech_id,criterion),[]).append(eid)
            for claim in answer.claims:
                if claim.citation.evidence_id in eligible:
                    examined.setdefault((claim.tech_id,claim.criterion_id),[]).append(claim.citation.evidence_id)
            pool={**state['claim_pool'],**added}
            analysis,_=materialize(data,blank_draft(),pool)
            update.update(claim_pool=pool,reviews={**state['reviews'],**reviews},analysis=analysis,examined=examined,
                extraction_history=state['extraction_history']+[{'claims':[c.model_dump(mode='json') for c in answer.claims],
                    'errors':errors,'reviews':reviews}],
                extraction_errors=errors,model_successes=state['model_successes']+1,
                errors=[e for e in state['errors'] if e['stage'] not in {'claims','llm_extract'}]+errors)
        except ProviderError as exc:
            error=dict(stage='llm_extract',code=exc.code,scope='global')
            update.update(extraction_errors=[error],errors=state['errors']+[error],fatal=exc.fatal)
        return update

    def can_repair(state,kind):
        return auto_repair and not state['repairs'].get(kind) and not state['fatal'] and budget.remaining('llm')>(1 if kind=='compose' and hasattr(analyst,'audit') else 0)

    def after_extract(state):
        # 유효 근거가 있으면 평가 작성 1회를 우선 확보한다.
        room=budget.remaining('llm')-review_reserve
        if room>0:
            if can_repair(state,'collect') and budget.remaining('search'):
                return 'repair_collect'
            if state['extraction_errors'] and can_repair(state,'extract'):
                return 'repair_extract'
        return 'compose'

    def compose(state):
        update={'history':state['history']+['compose']}
        draft=state.get('draft',blank_draft())
        current=[e for e in state['errors'] if e['stage'] not in {'compose','validate','llm_compose'}]
        errors=list(state['composition_errors'])
        all_candidates=state['candidate_pool'] if state['repair_kind']=='compose' else state['claim_pool']
        input_pool=limit_claims(all_candidates)
        pool={k:c for k,c in input_pool.items() if k in initial_pool}
        candidates={**state.get('candidate_pool',{}),**all_candidates}
        review_log=dict(state.get('claim_review_log',{}))
        if input_pool and not state['fatal']:
            if budget.remaining('llm'):
                try:
                    draft=budget.call('llm',lambda:DraftAnalysis.model_validate(analyst.compose(data,input_pool,
                        previous=state.get('draft'),issues=state['composition_errors'])),
                        max_attempts=max(1,min(2,budget.remaining('llm')-(1 if hasattr(analyst,'audit') else 0))))
                    errors=[]  # 새 평가가 성공한 경우에만 이전 평가 오류를 해소한다.
                    update['model_successes']=state['model_successes']+1
                    update['compose_successes']=state['compose_successes']+1
                    pool,log,review_errors=review_claims(input_pool,draft.claim_reviews)
                    review_log.update(log)
                    errors+=review_errors
                except ProviderError as exc:
                    errors.append(dict(stage='llm_compose',code=exc.code,scope='global'))
                    update['fatal']=exc.fatal
            else:
                errors.append(dict(stage='llm_compose',code='budget_exhausted:llm'))
        for key in candidates:
            if key not in pool and key not in review_log:
                review_log[key]='candidate_limit' if key not in input_pool else 'unreviewed: 평가 단계가 완료되지 않음'
        analysis,link_errors=materialize(data,draft,pool)
        analysis,validation_errors=validate_analysis(data,analysis,state['evidence'])
        errors+=link_errors+validation_errors
        # 인용 수정 실패도 미확인의 이유로 보존한다.
        current+=errors
        reviewed={k:list(v) for k,v in state['examined'].items()}
        for c in pool.values():
            reviewed.setdefault((c.tech_id,c.criterion_id),[]).append(c.citation.evidence_id)
        analysis=annotate(analysis,data,state['evidence'],state['queries'],current,budget,
            state['model_successes']>0,reviewed=reviewed)
        update.update(draft=draft,analysis=analysis,composition_errors=errors,errors=current,
            claim_pool=pool,candidate_pool=candidates,claim_review_log=review_log)
        return update

    def after_compose(state):
        return 'repair_compose' if state['composition_errors'] and can_repair(state,'compose') else 'audit'

    def audit(state):
        if not hasattr(analyst,'audit') or not state['claim_pool']:
            return {}
        errors=list(state['errors'])
        try:
            draft=budget.call('llm',lambda:DraftAnalysis.model_validate(analyst.audit(data,state['claim_pool'])),max_attempts=1)
            pool,log,review_errors=review_claims(state['claim_pool'],draft.claim_reviews)
            analysis,link_errors=materialize(data,draft,pool)
            analysis,validation_errors=validate_analysis(data,analysis,state['evidence'])
            errors=[e for e in errors if e['stage'] not in {'audit','llm_audit'}]
            errors+=[{**e,'stage':'audit'} for e in review_errors+link_errors+validation_errors]
            analysis=annotate(analysis,data,state['evidence'],state['queries'],errors,budget,True,reviewed=state['examined'])
            return dict(claim_pool=pool,analysis=analysis,errors=errors,draft=draft,
                claim_review_log={**state['claim_review_log'],**log},history=state['history']+['audit'],
                model_successes=state['model_successes']+1)
        except ProviderError as exc:
            return dict(errors=errors+[dict(stage='llm_audit',code=exc.code,scope='global')],
                fatal=exc.fatal,history=state['history']+['audit_failed'])

    def repair(kind):
        def action(state):
            return dict(round=1,repairs={**state['repairs'],kind:True},repair_kind=kind,history=state['history']+['repair_'+kind])
        return action

    def finish(state):
        statuses={t:'completed' if all(r.verdict!='unknown' for r in state['analysis'].assessments if r.tech_id==t)
            else 'unknown' for t in data.technologies}
        api_failure=any(e['stage'].startswith('llm') or e['stage'] in {'search','extract'} for e in state['errors']
            if not e['code'].startswith('budget_'))
        failed=state['fatal'] or (state['model_successes']==0 and api_failure)
        incomplete=bool(state['errors']) or any(r.research_status=='not_started' for r in state['analysis'].assessments)
        execution='failed' if failed else ('partial' if incomplete else 'completed')
        progress={'queries':state['queries'],'repairs':state['repairs'],'reviews':state['reviews'],
            'errors':state['errors'],'extraction_errors':state['extraction_errors'],
            'composition_errors':state['composition_errors'],'model_successes':state['model_successes'],
            'extraction_history':state['extraction_history'],
            'examined':[{'tech_id':t,'criterion_id':c,'evidence_ids':list(dict.fromkeys(ids))}
                for (t,c),ids in state['examined'].items()]}
        budget.progress=progress
        result=MarketResult(status='failed' if failed else ('completed' if all(v=='completed' for v in statuses.values()) else 'unknown'),
            round=state['round'],assessments=state['analysis'].assessments,followup_questions=state['analysis'].followup_questions,
            technology_status=statuses,errors=state['errors'],usage=dict(budget.used),mode=mode,
            execution_status=execution,progress=progress)
        return {'result':result,'history':state['history']+['finish']}

    graph=StateGraph(RunState)
    for name,action in [('collect',collect),('extract',extract),('compose',compose),('audit',audit),('finish',finish)]:
        graph.add_node(name,action)
    for kind in ['collect','extract','compose']:
        graph.add_node('repair_'+kind,repair(kind))
        graph.add_edge('repair_'+kind,kind)
    graph.add_edge(START,'collect')
    graph.add_edge('collect','extract')
    graph.add_conditional_edges('extract',after_extract,{'repair_extract':'repair_extract','repair_collect':'repair_collect','compose':'compose'})
    graph.add_conditional_edges('compose',after_compose,{'repair_compose':'repair_compose','audit':'audit'})
    graph.add_edge('audit','finish')
    graph.add_edge('finish',END)
    draft=previous_draft(previous,initial_pool,blank_draft())
    analysis,_=materialize(data,draft,initial_pool)
    state=graph.compile().invoke(dict(data=data,round=round_number,evidence=initial_evidence,sources={},analysis=analysis,
        errors=list(progress.get('errors',[])),history=[],queries=progress.get('queries',[]),fatal=False,claim_pool=initial_pool,candidate_pool={},claim_review_log={},
        reviews=progress.get('reviews',{}),extraction_errors=list(progress.get('extraction_errors',[])),composition_errors=list(progress.get('composition_errors',[])),
        repair_kind='',repairs=progress.get('repairs',{k:round_number==1 for k in ['collect','extract','compose']}),
        examined={(r['tech_id'],r['criterion_id']):r['evidence_ids'] for r in progress.get('examined',[])},extraction_history=list(progress.get('extraction_history',[])),
        model_successes=progress.get('model_successes',0),compose_successes=0,draft=draft),config={'recursion_limit':24})
    state.update(events=list(budget.events),initial_evidence_ids=list(initial_evidence),model=getattr(analyst,'model','injected'),
        token_usage=list(getattr(analyst,'usage',[])),output_checks=list(getattr(analyst,'output_checks',[])),
        debug_analyses=list(getattr(analyst,'debug_analyses',[])),claim_dispositions=pool_dispositions(state['claim_pool'],state['analysis']))
    state['claim_dispositions'].update({k:v for k,v in state['claim_review_log'].items() if k not in state['claim_pool']})
    return state


def parent_update(state):
    evidence = {eid: e.model_dump(mode="json") for eid, e in state["evidence"].items() if eid not in state["initial_evidence_ids"]}
    documents = {e["doc_id"]: {"url": e["url"], "title": e["title"], "content_hash": e["content_hash"],
        "retrieved_at": e["retrieved_at"], "page_count": None} for e in evidence.values()}
    result = state["result"].model_dump(mode="json")
    return {"assessments": {"market": result}, "documents": documents, "evidence": evidence,
        "errors": {f'market-{result["round"]}-{i}': error for i, error in enumerate(result["errors"])}}
