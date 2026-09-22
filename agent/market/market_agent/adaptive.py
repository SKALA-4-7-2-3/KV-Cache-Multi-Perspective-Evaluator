"""검색과 자료 종합 평가를 번갈아 실행하는 단계별 시장 조사 Graph."""
from typing import TypedDict
from langgraph.graph import START, END, StateGraph

from .schemas import Analysis, CRITERIA, MarketResult, Synthesis, SynthesisRow, SynthesisReviews, SynthesisReview, Segment, unknown
from .tools import Budget, ProviderError
from .collection import collect_sources
from .search_plan import initial_questions, progressive_questions
from .sources import content_quality
from .adaptive_materials import build_packet
from .synthesis import apply_synthesis, retain_drafts
from .delivery import complete_delivery, delivery_coverage, technology_status
from .research import annotate


class AdaptiveState(TypedDict, total=False):
    evidence: dict
    sources: dict
    analysis: Analysis
    errors: list
    history: list
    queries: list
    fatal: bool
    research_level: int
    round: int
    packet: dict
    draft: object
    targets: list
    records: dict
    stage_history: list
    model_successes: int
    repair_attempts: int
    result: MarketResult
    retained_draft_findings: list


def restore_records(data, progress, evidence, sources=None):
    analysis=Analysis(assessments=[],followup_questions=[]);errors=[];records={}
    for record in progress.get('synthesis_records',{}).values():
        try:
            draft=Synthesis(assessments=[SynthesisRow.model_validate(record['decision'])])
            reviews=SynthesisReviews(reviews=[SynthesisReview.model_validate(record['review'])])
            updated,issues,accepted=apply_synthesis(data,analysis,draft,reviews,record['packet'],evidence,record['level'],sources=sources)
            analysis=updated;errors+=issues;records.update(accepted)
        except (ValueError,KeyError,TypeError):
            errors.append(dict(stage='synthesis',code='invalid_saved_synthesis'))
    return analysis,errors,records


def merge_verified(data, analysis, previous, evidence):
    if not previous:return analysis
    from .validation import validate_analysis
    legacy=Analysis(assessments=[r for r in previous.assessments if r.generation_method=='verified_claim' and r.basis!='unknown'],followup_questions=[])
    checked,_=validate_analysis(data,legacy,evidence)
    rows={(r.tech_id,r.criterion_id):r for r in checked.assessments if r.basis!='unknown'}
    rows.update({(r.tech_id,r.criterion_id):r for r in analysis.assessments})
    return Analysis(assessments=list(rows.values()),followup_questions=analysis.followup_questions)


def pending(data, analysis):
    resolved={(r.tech_id,r.criterion_id) for r in analysis.assessments
        if r.basis!='unknown' and r.evaluation_mode in {'grounded','provisional'}
        and r.generation_method!='deterministic_fallback'}
    return [(t,c) for t in data.technologies for c in CRITERIA if (t,c) not in resolved]


def run_adaptive(data, web, analyst, *, mode='live', budget=None, auto_repair=True,
                 round_number=0, previous=None, existing_evidence=None, existing_claims=None, previous_progress=None):
    if round_number not in {0,1}:raise ValueError('round_number must be 0 or 1')
    budget=budget or Budget(data.limits);budget.constrain(data.limits)
    progress=previous_progress if previous_progress is not None else budget.progress
    for kind,used in progress.get('usage',{}).items():
        if kind in budget.used and isinstance(used,int) and used>=0:budget.used[kind]=max(budget.used[kind],used)
    evidence={k:e.model_copy(deep=True) for k,e in {**data.evidence,**(existing_evidence or {})}.items()}
    for e in evidence.values():
        if e.access_status=='full_text' and e.content_status=='unchecked':
            tech=next((data.technologies[t] for t in e.tech_ids if t in data.technologies),next(iter(data.technologies.values())))
            e.content_status,e.content_reason=content_quality(e.excerpt,e.url,tech)
    analysis,restore_errors,records=restore_records(data,progress,evidence)
    # 구형 부모 결과도 기존 검증 경로를 거쳐 보존한다. 새 잠정 결과는 저장된 검토 기록이 필요하다.
    if previous is None and progress.get('verified_rows'):
        previous=Analysis.model_validate({'assessments':progress['verified_rows'],'followup_questions':[]})
    analysis=merge_verified(data,analysis,previous,evidence)

    def collect(state):
        from .node import relevant_candidate
        targets=pending(data,state['analysis'])
        rows=[unknown(t,c,'보완 대상') for t,c in targets]
        questions=initial_questions(data) if state['research_level']==0 else progressive_questions(data,rows,state['queries'],state['research_level'])
        seen={q['query'] for q in state['queries']}
        questions=[q for q in questions if q.query not in seen] if targets else []
        collected=collect_sources(state,data,web,budget,questions,lambda r,t:relevant_candidate(r,t,state['research_level']))
        collected['targets']=targets
        collected['packet']=build_packet(data,collected['evidence'],state['research_level'],targets,collected['sources'])
        return collected

    def synthesize(state):
        update={'history':state['history']+['synthesize'],'draft':None}
        if state['fatal'] or not state['targets'] or not state['packet']:return update
        if budget.remaining('llm')<2:
            update['errors']=state['errors']+[dict(stage='llm_synthesize',code='budget_exhausted:llm',scope='global')]
            return update
        try:
            draft=budget.call('llm',lambda:Synthesis.model_validate(analyst.synthesize(data,state['packet'],state['research_level'],
                state['targets'],previous=state['analysis'],issues=state['errors'])),max_attempts=min(2,budget.remaining('llm')-1))
            update.update(draft=draft,model_successes=state['model_successes']+1)
        except ProviderError as exc:
            update.update(errors=state['errors']+[dict(stage='llm_synthesize',code=exc.code,scope='global')],fatal=exc.fatal)
        return update

    def review(state):
        if state['draft'] is None:return {}
        try:
            reviews=budget.call('llm',lambda:SynthesisReviews.model_validate(analyst.review_synthesis(data,state['draft'],state['packet'],state['research_level'])),max_attempts=1)
            analysis,issues,records=apply_synthesis(data,state['analysis'],state['draft'],reviews,state['packet'],state['evidence'],
                state['research_level'],targets=state['targets'],sources=state['sources'])
            retained=retain_drafts(data,state['draft'],state['packet'],state['evidence'],state['research_level'],
                issues,state['retained_draft_findings'],sources=state['sources'])
            for record in records.values():
                for item in record['packet'].values():
                    e=state['evidence'][item['evidence_id']]
                    if item['text'] not in e.excerpt and not any(item['text'] in segment.text for segment in e.segments):
                        e.segments.append(Segment(text=item['text'],start=item.get('start',0),end=item.get('end',len(item['text'])),locator=item['locator']))
            errors=[e for e in state['errors'] if e['stage'] not in {'llm_synthesize','llm_synthesis_review'}
                and not (e['stage']=='synthesis' and (e.get('tech_id'),e.get('criterion_id')) in set(state['targets']))]
            errors+=issues
            reviewed={(r.tech_id,r.criterion_id):r.reviewed_evidence_ids for r in analysis.assessments}
            analysis=annotate(analysis,data,state['evidence'],state['queries'],errors,budget,True,reviewed=reviewed)
            return dict(analysis=analysis,errors=errors,records={**state['records'],**records},model_successes=state['model_successes']+1,
                retained_draft_findings=retained,
                history=state['history']+['review_synthesis'],stage_history=state['stage_history']+[{
                    'level':state['research_level'],'targets':state['targets'],'accepted':list(records),'errors':issues,'packet_size':len(state['packet'])}])
        except ProviderError as exc:
            issue=dict(stage='llm_synthesis_review',code=exc.code,scope='global')
            retained=retain_drafts(data,state['draft'],state['packet'],state['evidence'],state['research_level'],
                [issue],state['retained_draft_findings'],sources=state['sources'])
            return dict(errors=state['errors']+[issue],fatal=exc.fatal,retained_draft_findings=retained,
                history=state['history']+['review_synthesis_failed'])

    def route(state):
        if auto_repair and not state['fatal'] and state['research_level']<2 and pending(data,state['analysis']) and budget.remaining('llm')>=2:
            return 'broaden'
        if auto_repair and not state['fatal'] and state['research_level']==2 and state['packet'] and failed_targets(state) and state['repair_attempts']<2 and budget.remaining('llm')>=2:
            return 'repair'
        return 'finish'

    def failed_targets(state):
        valid={(r.tech_id,r.criterion_id) for r in state['analysis'].assessments
            if r.basis!='unknown' and r.generation_method in {'model_synthesis','verified_claim'}}
        return [(t,c) for t in data.technologies for c in CRITERIA if (t,c) not in valid]

    def repair(state):
        targets=failed_targets(state)
        return dict(targets=targets,packet=build_packet(data,state['evidence'],2,targets,state['sources']),
            repair_attempts=state['repair_attempts']+1,history=state['history']+['repair_synthesis'])

    def broaden(state):
        return dict(research_level=state['research_level']+1,round=1,history=state['history']+['broaden'])

    def finish(state):
        # 미완료 행은 실제 조사 상태를 붙인 뒤에만 비상 출력으로 완성한다.
        by_key={(r.tech_id,r.criterion_id):r for r in state['analysis'].assessments}
        raw=Analysis(assessments=[by_key.get((t,c),unknown(t,c,'자료 종합 평가를 완료하지 못함'))
            for t in data.technologies for c in CRITERIA],followup_questions=[])
        reviewed={(r.tech_id,r.criterion_id):r.reviewed_evidence_ids for r in raw.assessments}
        raw=annotate(raw,data,state['evidence'],state['queries'],state['errors'],budget,state['model_successes']>0,reviewed=reviewed)
        result_analysis=complete_delivery(data,raw,state['evidence'],state['errors'])
        fallback=any(r.generation_method=='deterministic_fallback' for r in result_analysis.assessments)
        execution='failed' if state['fatal'] else ('partial' if state['errors'] or fallback else 'completed')
        statuses=technology_status(data,result_analysis)
        progress=dict(engine='adaptive-v1',research_level=state['research_level'],queries=state['queries'],errors=state['errors'],
            retained_draft_findings=state['retained_draft_findings'],
            synthesis_records=state['records'],verified_rows=[r.model_dump(mode='json') for r in raw.assessments if r.generation_method=='verified_claim' and r.basis!='unknown'],stage_history=state['stage_history'],model_successes=state['model_successes'],
            delivery_coverage=delivery_coverage(result_analysis),usage=dict(budget.used),repair_attempts=state['repair_attempts'])
        budget.progress=progress
        result=MarketResult(status='failed' if state['fatal'] else ('completed' if all(v=='completed' for v in statuses.values()) else 'provisional'),
            round=state['round'],assessments=result_analysis.assessments,followup_questions=[],technology_status=statuses,
            errors=state['errors'],usage=dict(budget.used),mode=mode,execution_status=execution,progress=progress)
        return dict(result=result,analysis=raw,history=state['history']+['finish'])

    graph=StateGraph(AdaptiveState)
    for name,fn in [('collect',collect),('synthesize',synthesize),('review',review),('broaden',broaden),('repair',repair),('finish',finish)]:graph.add_node(name,fn)
    graph.add_edge(START,'collect');graph.add_edge('collect','synthesize');graph.add_edge('synthesize','review')
    graph.add_conditional_edges('review',route,{'broaden':'broaden','repair':'repair','finish':'finish'})
    graph.add_edge('broaden','collect');graph.add_edge('finish',END)
    graph.add_edge('repair','synthesize')
    state=graph.compile().invoke(dict(evidence=evidence,sources={},analysis=analysis,errors=list(progress.get('errors',[]))+restore_errors,
        history=[],queries=list(progress.get('queries',[])),fatal=False,research_level=progress.get('research_level',round_number),round=round_number,
        records=records,stage_history=list(progress.get('stage_history',[])),model_successes=progress.get('model_successes',0),
        retained_draft_findings=list(progress.get('retained_draft_findings',[])),
        repair_attempts=progress.get('repair_attempts',0)),config={'recursion_limit':24})
    state.update(data=data,events=list(budget.events),initial_evidence_ids=list(evidence),model=getattr(analyst,'model','injected'),
        token_usage=list(getattr(analyst,'usage',[])),output_checks=list(getattr(analyst,'output_checks',[])),
        debug_analyses=list(getattr(analyst,'debug_analyses',[])),claim_pool={},candidate_pool={},claim_review_log={},claim_dispositions={})
    state['review_notes']=list(dict.fromkeys(note for row in state['retained_draft_findings'] for note in row['review_notes']))
    return state
