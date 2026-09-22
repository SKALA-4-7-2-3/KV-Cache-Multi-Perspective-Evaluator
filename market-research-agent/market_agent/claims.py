"""주장 단위로 검증하고, 검증된 ID만 평가의 인용으로 변환한다."""
import hashlib
import re
from collections import Counter

from .schemas import Analysis, Assessment, ContextFinding, CRITERIA, unknown, Claim, DraftAnalysis, DraftAssessment
from .validation import valid_citations, identity_supported, metric_supported, quantitative_claim, normalized


def recover_previous(previous):
    """부모의 기존 Analysis 계약을 지원한다. 복수 출처 주장을 임의로 쪼개지 않는다."""
    claims=[]
    for row in previous.assessments if previous else []:
        items=[(row.judgment,row.basis,row.relation_to_technology,row.citations,row.conditions,row.metric)]
        items += [(c.statement,c.basis,c.relation_to_technology,c.citations,c.conditions,c.metric) for c in row.context_findings]
        for statement,basis,relation,citations,conditions,metric in items:
            if basis=='unknown' or relation=='unknown' or len(citations)!=1:
                continue
            claims.append(Claim(tech_id=row.tech_id,criterion_id=row.criterion_id,statement=statement,basis=basis,
                relation_to_technology=relation,citation=citations[0],conditions=conditions,metric=metric))
    return claims


def previous_draft(previous,pool,fallback):
    if not previous:
        return fallback
    old={(r.tech_id,r.criterion_id):r for r in previous.assessments}
    rows=[]
    for row in fallback.assessments:
        r=old.get((row.tech_id,row.criterion_id))
        if r and r.basis!='unknown':
            ids=[k for k,c in pool.items() if (c.tech_id,c.criterion_id,c.relation_to_technology)==(r.tech_id,r.criterion_id,'exact')
                and any(c.citation.evidence_id==x.evidence_id and normalized(c.citation.quote)==normalized(x.quote) for x in r.citations)]
            covered={(pool[k].citation.evidence_id,normalized(pool[k].citation.quote)) for k in ids}
            expected={(c.evidence_id,normalized(c.quote)) for c in r.citations}
            if covered and covered==expected:
                row=DraftAssessment(tech_id=r.tech_id,criterion_id=r.criterion_id,judgment=r.judgment,verdict=r.verdict,
                    basis=r.basis,claim_ids=ids,conditions=r.conditions,gaps=r.gaps)
        rows.append(row)
    return DraftAnalysis(assessments=rows,followup_questions=previous.followup_questions)


def validate_claims(data, claims, evidence):
    pool, errors = {}, []
    for original in claims:
        claim = original.model_copy(deep=True)
        c = claim.citation
        e = evidence.get(c.evidence_id)
        code = None
        if claim.tech_id not in data.technologies:
            code = 'unexpected_technology'
        elif not e or e.access_status in {'snippet', 'failed'}:
            code = 'source_not_verified'
        elif e.access_status == 'full_text' and e.content_status != 'substantive':
            code = 'content_not_substantive'
        elif e.access_status == 'provided_summary' and not (
                claim.criterion_id == 'business_value' and claim.basis == 'inference' and claim.conditions):
            code = 'summary_is_not_market_fact'
        elif not valid_citations([c], evidence, data.as_of):
            code = 'missing_or_invalid_quote'
        elif claim.relation_to_technology == 'exact' and not identity_supported(data.technologies[claim.tech_id],[c],evidence):
            code = 'identity_unverified'
        elif claim.relation_to_technology != 'exact' and normalized(c.subject) not in normalized(e.excerpt):
            code = 'subject_unverified'
        elif claim.basis == 'inference' and not claim.conditions:
            code = 'inference_requires_conditions'
        elif (claim.metric or quantitative_claim(claim.statement)) and not metric_supported(claim.metric,[c],evidence):
            code = 'unsupported_metric'
        if code:
            errors.append(dict(stage='claims',code=code,scope='cell',tech_id=claim.tech_id,criterion_id=claim.criterion_id,
                evidence_id=c.evidence_id,candidate=claim.model_dump_json()))
            continue
        if e.published_at is None:
            claim.conditions = list(dict.fromkeys([*claim.conditions,'발행일 미확인: 기준일 당시 상태 추가 확인 필요']))
        if claim.relation_to_technology != 'exact':
            claim.conditions = list(dict.fromkeys([*claim.conditions,'선정 논문과 제품·구현의 동일성 미확인']))
        # 한 문서의 같은 인용·항목은 문장 표현이 달라도 하나의 근거로 센다.
        identity = '\n'.join([claim.tech_id,claim.criterion_id,c.evidence_id,normalized(c.quote)])
        key = 'CLM-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
        pool.setdefault(key,claim)
    return pool, errors


def criterion_supported(claim):
    """시장 역할에 명백히 맞지 않는 기술 설명을 의미 검토의 독립 최소 조건으로 거른다."""
    quote=re.sub(r'no cost to efficiency','',claim.citation.quote,flags=re.I)
    # 버전/거리 등 수치도 주변 문장만으로 덧붙이지 않는다. FP8 같은 이름의 숫자는 제외한다.
    numbers=lambda text:set(re.findall(r'(?<![A-Za-z0-9])\d+(?:\.\d+)?',text))
    quote_numbers=numbers(quote)
    months='January February March April May June July August September October November December'.split()
    for number,month in enumerate(months,1):
        if re.search(r'\b'+month+r'\s+\d{1,4}\b',quote):quote_numbers.add(str(number))
    if not numbers(claim.statement)<=quote_numbers:
        return False
    if claim.criterion_id=='standardization':
        return bool(re.search(r'standard|specification|consortium|IEEE|JEDEC|표준|규격',quote,re.I))
    if claim.criterion_id=='commercialization':
        return bool(re.search(r'product|commercial|launch|releas|licen[cs]e|available|repository|github|제품|출시|라이선스',quote,re.I))
    if claim.criterion_id=='adoption':
        return bool(re.search(r'customer|production|deployed|adopted|uses? |using |고객|도입|운영',quote,re.I))
    if claim.criterion_id=='ecosystem_support':
        return bool(re.search(r'support|integrat|compatib|framework|library|runtime|interoperab|지원|통합',quote,re.I))
    if claim.criterion_id=='business_value':
        return bool(re.search(r'cost|price|memory efficiency|energy efficiency|latency|throughput|speedup|speed.up|footprint|'
            r'reduc.{0,45}memory|memory.{0,45}(reduc|sav|capac|utiliz)|utilization|energy|비용|메모리.{0,20}절약',quote,re.I))
    return True


def review_claims(pool, reviews):
    """작성 모델이 인용의 의미까지 검토한 주장만 전달한다. 검토 누락은 실패다."""
    counts = Counter(r.claim_id for r in reviews)
    by_id = {r.claim_id:r for r in reviews}
    accepted, log, errors = {}, {}, []
    for key, claim in pool.items():
        review = by_id.get(key)
        if not review or counts[key] != 1 or not review.reason.strip():
            log[key] = 'unreviewed'
            errors.append(dict(stage='compose',code='missing_claim_review',tech_id=claim.tech_id,
                criterion_id=claim.criterion_id,claim_id=key))
        elif review.supported and review.market_relevant and review.relation_supported and review.conditions_preserved and criterion_supported(claim):
            checked=claim.model_copy(deep=True)
            checked.evidence_level=claim.evidence_level if claim.evidence_level in {'research_experiment','simulation'} else review.evidence_level
            if checked.criterion_id=='business_value' and ('arxiv.org' in checked.citation.source_character or checked.evidence_level in {'research_experiment','simulation'}):
                checked.basis='inference'
                checked.conditions=list(dict.fromkeys([*checked.conditions,'연구상 기술 효과는 고객 가치의 전제이며 실제 고객 비용·ROI 실측 결과가 아님']))
            if review.evidence_level in {'projection','planned_release','inference'}:
                checked.basis='inference'
                checked.conditions=list(dict.fromkeys([*checked.conditions,'전망·계획에 근거한 추론이며 실제 고객 성과 미검증']))
            if 'arxiv.org' in checked.citation.source_character and re.search(r'carbon|environment|sustainab',checked.citation.quote,re.I):
                checked.evidence_level='projection'
                checked.basis='inference'
                checked.conditions=list(dict.fromkeys([*checked.conditions,'환경·에너지 효과는 연구 저자의 전망이며 실측 고객 성과 미검증']))
            checked.citation.source_character = checked.citation.source_character.split('; 근거 수준:')[0] + f'; 근거 수준: {checked.evidence_level}'
            accepted[key] = checked
            log[key] = 'accepted: ' + review.reason
        else:
            log[key] = 'rejected: ' + (review.reason if criterion_supported(claim) else 'criterion_evidence_mismatch: 해당 시장 항목의 명시적 근거 부족')
    return accepted, log, errors


def limit_claims(pool, total=12, per_cell=2):
    """입력 순서의 독점을 막고 기술·항목별로 균등하게 후보를 배정한다."""
    groups={}
    for key,claim in pool.items():
        groups.setdefault((claim.tech_id,claim.criterion_id),[]).append((key,claim))
    ordered={}
    for cell,items in sorted(groups.items()):
        items.sort(key=lambda x:(not criterion_supported(x[1]),x[1].relation_to_technology!='exact',x[1].basis!='fact',x[0]))
        first=items[:1]
        rest=items[1:]
        rest.sort(key=lambda x:x[1].relation_to_technology==first[0][1].relation_to_technology)
        ordered[cell]=first+rest
    selected={}
    for index in range(per_cell):
        for items in ordered.values():
            if len(items)>index and len(selected)<total:
                key,claim=items[index]
                selected[key]=claim
    return selected


def materialize(data, draft, pool):
    rows, errors = [], []
    counts = Counter((r.tech_id,r.criterion_id) for r in draft.assessments)
    provided = {(r.tech_id,r.criterion_id):r for r in draft.assessments}
    for tech in data.technologies:
        for criterion in CRITERIA:
            d = provided.get((tech,criterion))
            scoped = {k:c for k,c in pool.items() if c.tech_id==tech and c.criterion_id==criterion}
            row = unknown(tech,criterion,'이번 조사에서 선정 기술 자체를 판단할 직접 근거를 확인하지 못함')
            code = None
            if not any(c.relation_to_technology=='exact' for c in scoped.values()):
                # 직접 근거가 없는 행의 판정은 모델에 맡기지 않는다.
                # 관련 정보는 아래에서 연결하고 후보의 제외 사유는 별도로 기록한다.
                row.gaps=['선정 기술 자체의 해당 시장 항목을 입증할 직접 근거 미확인']
            elif d is None or counts[tech,criterion] != 1:
                code = 'missing_or_duplicate_assessment'
            elif any(k not in scoped or scoped[k].relation_to_technology!='exact' for k in d.claim_ids):
                code = 'claim_scope_mismatch'
            elif d.basis != 'unknown' and not d.claim_ids:
                code = 'missing_claim_reference'
            elif d.basis == 'unknown':
                row.judgment, row.gaps = d.judgment, d.gaps
                row.conditions = d.conditions
            else:
                selected = [scoped[k] for k in dict.fromkeys(d.claim_ids)]
                citations = [c.citation.model_copy(deep=True) for c in selected]
                basis='inference' if any(c.basis=='inference' for c in selected) else d.basis
                row = Assessment(tech_id=tech,criterion_id=criterion,judgment=' '.join(dict.fromkeys(c.statement for c in selected)),verdict=d.verdict,
                    basis=basis,relation_to_technology='exact',evidence_ids=list(dict.fromkeys(c.evidence_id for c in citations)),
                    citations=citations,conditions=list(dict.fromkeys([*d.conditions,*(x for c in selected for x in c.conditions)])),
                    gaps=d.gaps,metric=next((c.metric for c in selected if c.metric),None))
            if code:
                errors.append(dict(stage='compose',code=code,tech_id=tech,criterion_id=criterion))
                row.gaps = ['평가 작성 결과의 근거 연결 오류로 선정 기술 결론을 보류함']
            # 평가 모델이 보조 정보 배열을 쓰는지에 의존하지 않는다.
            related = [c for c in scoped.values() if c.relation_to_technology!='exact']
            related.sort(key=lambda c:(c.basis!='fact', c.relation_to_technology!='method_family'))
            row.context_findings = [ContextFinding(statement=c.statement,basis=c.basis,
                relation_to_technology=c.relation_to_technology,citations=[c.citation.model_copy(deep=True)],
                conditions=c.conditions,metric=c.metric) for c in related[:1]]
            rows.append(row)
    for tech,criterion in counts:
        if tech not in data.technologies:
            errors.append(dict(stage='compose',code='unexpected_technology',tech_id=tech,criterion_id=criterion))
    return Analysis(assessments=rows,followup_questions=draft.followup_questions),errors


def pool_dispositions(pool, analysis):
    """포함하지 않은 근거도 이유를 남겨 조용한 소실과 구분한다."""
    dispositions = {}
    for key,claim in pool.items():
        row = next(r for r in analysis.assessments if (r.tech_id,r.criterion_id)==(claim.tech_id,claim.criterion_id))
        citations = [*row.citations,*(c for f in row.context_findings for c in f.citations)]
        used = any(c.evidence_id==claim.citation.evidence_id and normalized(c.quote)==normalized(claim.citation.quote) for c in citations)
        dispositions[key] = 'included' if used else ('related_item_limit' if claim.relation_to_technology!='exact'
            else ('not_selected_for_assessment' if row.basis!='unknown' else 'assessment_not_supported: ' + '; '.join(row.gaps)))
    return dispositions
