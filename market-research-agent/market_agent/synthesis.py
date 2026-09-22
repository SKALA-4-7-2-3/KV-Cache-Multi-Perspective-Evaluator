"""LLM이 작성하고 별도 검토한 자료 종합 평가의 결정적 경계 검사."""
import re
from collections import Counter
from .adaptive_materials import POLICIES, eligible
from .schemas import Analysis, Assessment, SupportingMaterial
from .quantities import numeric_tokens
from .validation import normalized


def packet_item_valid(item, evidence, data, level, sources=None):
    e=evidence.get(item.get('evidence_id'))
    if not e or not eligible(e,data,level):return False
    bodies=[e.excerpt,*[s.text for s in e.segments]]
    if sources and e.doc_id in sources:bodies.append(sources[e.doc_id])
    return bool(item.get('text','').strip() and any(normalized(item['text']) in normalized(body) for body in bodies))


def apply_synthesis(data, current, draft, reviews, packet, evidence, level, *, targets=None, sources=None):
    targets=set(targets if targets is not None else [(r.tech_id,r.criterion_id) for r in draft.assessments])
    counts=Counter((r.tech_id,r.criterion_id) for r in draft.assessments)
    review_counts=Counter((r.tech_id,r.criterion_id) for r in reviews.reviews)
    by_review={(r.tech_id,r.criterion_id):r for r in reviews.reviews}
    rows={(r.tech_id,r.criterion_id):r.model_copy(deep=True) for r in current.assessments}
    errors=[];records={}
    for d in draft.assessments:
        key=(d.tech_id,d.criterion_id);review=by_review.get(key);code=None
        refs=[packet[q] for q in dict.fromkeys(d.quote_ids) if q in packet]
        if key not in targets or d.tech_id not in data.technologies:code='unexpected_assessment'
        elif counts[key]!=1:code='duplicate_assessment'
        elif not d.quote_ids or len(refs)!=len(set(d.quote_ids)):code='missing_material_reference'
        elif any(d.tech_id not in evidence.get(p['evidence_id']).tech_ids for p in refs if p['evidence_id'] in evidence):code='material_ownership'
        elif any(not packet_item_valid(p,evidence,data,level,sources) for p in refs):code='invalid_material'
        elif d.relation_to_technology not in POLICIES[level]['relations']:code='broader_scope_deferred'
        elif d.relation_to_technology=='exact' and not any(
                normalized(data.technologies[d.tech_id].name) in normalized(p['text']) or
                bool(set(re.findall(r'\d{4}\.\d{4,5}',data.technologies[d.tech_id].url)) & set(re.findall(r'\d{4}\.\d{4,5}',evidence[p['evidence_id']].url)))
                for p in refs):code='identity_requires_related_scope'
        elif not review or review_counts[key]!=1:code='missing_semantic_review'
        elif not all([review.supported,review.relevant,review.scope_preserved,review.uncertainty_preserved,review.reason.strip()]):code='semantic_review_rejected'
        elif not all([d.observation.strip(),d.judgment.strip(),d.conditions]) or any(not c.strip() for c in d.conditions):code='incomplete_synthesis'
        elif not numeric_tokens(d.observation+' '+d.judgment)<=set().union(*(numeric_tokens(p['text']) for p in refs)):code='unsupported_number'
        if code:
            issue=dict(stage='synthesis',code=code,tech_id=d.tech_id,criterion_id=d.criterion_id)
            if review and code=='semantic_review_rejected':issue['reason']=review.reason
            errors.append(issue)
            continue
        statuses={p['access_status'] for p in refs}
        all_full=statuses=={'full_text'}
        mode='grounded' if all_full and d.relation_to_technology=='exact' else (
            'scenario' if statuses=={'provided_summary'} else 'provisional')
        materials=[];conditions=list(d.conditions)
        for p in refs:
            status={'full_text':'reference_only','snippet':'search_excerpt','provided_summary':'provided_context'}[p['access_status']]
            reason='관찰·판단과 원자료의 의미 검토 완료'
            if status=='search_excerpt':reason+='; 검색 발췌이며 원문 추가 확인 필요'
            if status=='provided_context':reason+='; 기술 입력 전제이며 시장 실적을 입증하지 않음'
            materials.append(SupportingMaterial(evidence_id=p['evidence_id'],quote=p['text'],locator=p['locator'],review_status=status,reason=reason))
        if not all_full:conditions.append('검색 발췌·기술 입력을 활용한 조건부 추론이며 독립 시장 실적 검증이 아님')
        if d.relation_to_technology!='exact':conditions.append('관련 기술군·인접 시장의 정보이며 선정 기술의 실제 출시·채택·인증과 구분')
        if any(not evidence[p['evidence_id']].published_at for p in refs):conditions.append('발행일이 없는 자료는 평가 기준일 당시 상태 추가 확인 필요')
        rows[key]=Assessment(tech_id=d.tech_id,criterion_id=d.criterion_id,observation=d.observation,judgment=d.judgment,
            basis='inference',relation_to_technology=d.relation_to_technology,evidence_ids=[],citations=[],metric=None,
            conditions=list(dict.fromkeys(conditions)),gaps=d.limitations,verdict='conditional' if mode=='grounded' else 'provisional',
            evaluation_mode=mode,confidence='medium' if mode=='grounded' else 'low',generation_method='model_synthesis',
            evaluation_level=level,supporting_materials=materials,research_status='reviewed',
            reviewed_evidence_ids=list(dict.fromkeys(p['evidence_id'] for p in refs)))
        records['::'.join(key)]={'decision':d.model_dump(mode='json'),'review':review.model_dump(mode='json'),
            'level':level,'packet':{q:packet[q] for q in d.quote_ids}}
    for tech,criterion in targets-counts.keys():
        errors.append(dict(stage='synthesis',code='missing_assessment',tech_id=tech,criterion_id=criterion))
    return Analysis(assessments=list(rows.values()),followup_questions=current.followup_questions),errors,records
