"""형식·참조 검사. 의미상 사실 검증은 원문 대조가 추가로 필요하다."""

import math
import re
from collections import Counter

from .schemas import Analysis, CRITERIA, unknown


def normalized(text):
    return ' '.join(text.split()).casefold()


def quantitative_claim(text):
    return bool(re.search(r'\d', text) and re.search(r'[$€₩%]|billion|million|\busd\b|달러|억|조\s*원|성장률|매출', text, re.I))


def metric_supported(metric, citations, evidence):
    if not metric or not math.isfinite(metric.value) or not all([metric.unit, metric.year, metric.market_definition, metric.geography]):
        return False
    if any(c.evidence_id not in evidence or evidence[c.evidence_id].access_status != 'full_text' for c in citations):
        return False
    for c in citations:
        text=normalized(c.quote)
        numbers=[float(n.replace(',','')) for n in re.findall(r'\d[\d,]*(?:\.\d+)?',text)]
        if metric.value not in numbers:
            continue
        if not all(normalized(v) in text for v in [metric.unit,metric.year,metric.market_definition,metric.geography]):
            continue
        if metric.currency and normalized(metric.currency) not in text:
            aliases={'USD':r'\$|us dollars?','EUR':r'€|euros?','KRW':r'₩|원'}
            if not re.search(aliases.get(metric.currency.upper(),r'(?!)'),text):
                continue
        forecast=bool(re.search(r'forecast|projected|expected|predict|전망|예상',text))
        if forecast != (metric.actual_or_forecast=='forecast'):
            continue
        return True
    return False


def valid_citations(citations, evidence, as_of):
    """원문 일치와 위치를 확인한다. 의미상 함의까지 보증하지 않는다."""
    if not citations:
        return False
    for c in citations:
        e = evidence.get(c.evidence_id)
        if not e or e.access_status in {'snippet', 'failed'} or e.content_status in {'metadata_only','identity_mismatch'} or (e.published_at and e.published_at > as_of):
            return False
        if not c.quote.strip() or not c.subject.strip() or not c.source_character.strip():
            return False
        if c.context and not any(normalized(c.context) in normalized(body)
                for body in ([s.text for s in e.segments] or [e.excerpt])):
            return False
        if normalized(c.subject) not in normalized(c.quote+' '+c.context):
            return False
        # 떨어진 문단을 이어 붙인 가상의 인용을 허용하지 않는다.
        segments = e.segments or []
        bodies = [(s.text, s.locator) for s in segments] or [(e.excerpt, e.locator)]
        match = next((loc for body, loc in bodies if normalized(c.quote) in normalized(body)), None)
        if match is None:
            return False
        if c.identity_quote and not any(normalized(c.identity_quote) in normalized(body) for body, _ in bodies):
            return False
        c.locator = match or e.locator or '인용 문구로 원문 검색'
    return True


def identity_supported(tech, citations, evidence):
    ids = re.findall(r'\d{4}\.\d{4,5}(?:v\d+)?', tech.paper)
    tokens = [tech.name, *ids]
    for c in citations:
        e = evidence[c.evidence_id]
        if not any(normalized(t) in normalized(c.subject) for t in tokens):
            return False
        text = normalized(c.identity_quote or c.quote)
        if any(normalized(t) in text for t in tokens):
            continue
        if e.access_status == 'provided_summary' and tech.id in e.tech_ids:
            continue
        return False
    return bool(citations)


def repair_context_references(finding, evidence, as_of):
    """보조 정보의 잘못된 ID만 원문 대조로 교정한다. 문구나 주장은 생성하지 않는다."""
    finding = finding.model_copy(deep=True)
    for c in finding.citations:
        if valid_citations([c], evidence, as_of):
            continue
        if len(c.quote.strip()) < 30 or normalized(c.subject) not in normalized(c.quote):
            continue
        matches = []
        for e in evidence.values():
            if e.access_status != 'full_text':
                continue
            probe = c.model_copy(update={'evidence_id': e.id})
            if valid_citations([probe], evidence, as_of):
                matches.append((e, probe))
        # 동일 문구가 제목이 다른 문서들에 나타나면 자동 선택하지 않는다.
        if not matches or len({normalized(e.title) for e, _ in matches}) != 1:
            continue
        e, corrected = min(matches, key=lambda pair: len(pair[0].url))
        c.evidence_id, c.locator = e.id, corrected.locator
        c.source_character = f'웹 발행자 설명 ({e.publisher or "발행자 미확인"}); 독립 검증 여부 미확인'
    return finding


def validate_analysis(data, analysis, evidence):
    errors, output = [], []
    counts = Counter((a.tech_id, a.criterion_id) for a in analysis.assessments)
    rows = {(a.tech_id, a.criterion_id): a for a in analysis.assessments}
    for tech_id in data.technologies:
        for criterion in CRITERIA:
            key = (tech_id, criterion)
            row = rows.get(key)
            code = None
            if row is None:
                code = "missing_assessment"
            elif counts[key] != 1:
                code = "duplicate_assessment"
            elif any(eid not in evidence for eid in row.evidence_ids):
                code = "unknown_evidence_id"
            else:
                refs = [evidence[eid] for eid in row.evidence_ids]
                web = [e for e in refs if e.access_status == "full_text"]
                if any(e.published_at and e.published_at > data.as_of for e in refs):
                    code = "source_after_as_of"
                elif row.basis != "unknown":
                    if not refs or any(e.access_status in {"snippet", "failed"} for e in refs):
                        code = "source_not_verified"
                    elif any(e.access_status == 'provided_summary' for e in refs) and not (criterion == 'business_value' and row.basis == 'inference'):
                        code = 'summary_is_not_market_fact'
                    elif not web and not (criterion == "business_value" and row.basis == "inference"):
                        code = "market_fact_requires_web_source"
                    elif criterion in {"adoption", "commercialization"} and row.basis == "fact" and row.relation_to_technology != "exact":
                        code = "family_is_not_exact_adoption"
                    elif row.relation_to_technology == "unknown":
                        code = "missing_technology_relation"
                if row.metric:
                    metric = row.metric
                    if row.basis != "fact" or not web or not math.isfinite(metric.value) or not all(
                        [metric.unit, metric.year, metric.market_definition, metric.geography]):
                        code = "unsupported_metric"
                if not code and row.basis != 'unknown':
                    if not valid_citations(row.citations, evidence, data.as_of):
                        code = 'missing_or_invalid_quote'
                    elif set(row.evidence_ids) != {c.evidence_id for c in row.citations}:
                        code = 'citation_ids_mismatch'
                    elif row.relation_to_technology != 'exact' or not identity_supported(data.technologies[tech_id], row.citations, evidence):
                        code = 'identity_unverified'
                    elif row.basis == 'inference' and not row.conditions:
                        code = 'inference_requires_conditions'
                    elif (row.metric or quantitative_claim(row.judgment)) and not metric_supported(row.metric, row.citations, evidence):
                        code = 'unsupported_metric'
                if not code and any(e.access_status == "full_text" and e.published_at is None for e in refs):
                    row = row.model_copy(update={"conditions": list(dict.fromkeys(row.conditions + ["발행일 미확인: 기준일 당시 상태 추가 확인 필요"]))})
            contexts = []
            if row:
                for finding in row.context_findings:
                    finding = repair_context_references(finding, evidence, data.as_of)
                    if (finding.basis != 'unknown' and finding.relation_to_technology in {'method_family', 'adjacent'}
                            and valid_citations(finding.citations, evidence, data.as_of)
                            and all(evidence[c.evidence_id].access_status == 'full_text' for c in finding.citations)
                            and (not quantitative_claim(finding.statement) and finding.metric is None or
                                finding.basis == 'fact' and metric_supported(finding.metric, finding.citations, evidence))):
                        if any(evidence[c.evidence_id].published_at is None for c in finding.citations):
                            finding.conditions = list(dict.fromkeys([*finding.conditions, '발행일 미확인: 기준일 당시 상태 추가 확인 필요']))
                        contexts.append(finding)
                    else:
                        errors.append({'stage': 'validate', 'code': 'invalid_context_finding', 'tech_id': tech_id, 'criterion_id': criterion})
            if code:
                errors.append({"stage": "validate", "code": code, "tech_id": tech_id, "criterion_id": criterion})
                reasons = ['insufficient_evidence']
                if row and row.relation_to_technology == 'exact' and code in {'missing_or_invalid_quote', 'identity_unverified'}:
                    reasons.append('identity_unverified')
                explanation = '해당 결론을 선정 기술에 연결하는 인용·원문 근거를 확인하지 못함'
                if code == 'summary_is_not_market_fact':
                    explanation = '전달받은 논문 요약만으로 제품화·시장 실적을 판단할 수 없음'
                elif code == 'missing_or_invalid_quote':
                    explanation = '평가 문구를 뒷받침하는 인용이 제공된 원문과 일치하지 않거나 누락됨'
                elif code == 'unsupported_metric':
                    explanation = '시장 수치의 정의·지역·연도·단위 또는 인용 근거 미확인'
                if code == 'source_after_as_of':
                    explanation = '조사 기준일 이후의 자료여서 해당 시점의 판단 근거로 사용하지 않음'
                    reasons = ['date_unverified']
                row = unknown(tech_id, criterion, f'미확인: {explanation}')
                row.unknown_reasons = reasons
            elif row.basis == "unknown":
                judgment = row.judgment
                if judgment.strip().lower() in {"", "unknown", "미확인"}:
                    judgment = "미확인: " + ("; ".join(row.gaps) or "이번 조사에서 판단 근거를 확보하지 못함")
                row = row.model_copy(update={"metric": None, "judgment": judgment, 'verdict': 'unknown',
                    'citations': [], 'evidence_ids': [], 'unknown_reasons': row.unknown_reasons or ['insufficient_evidence']})
            # 입력에 정량 목표가 없으므로 무조건적 긍정·부정은 확정하지 않는다.
            if row.verdict in {'favorable', 'unfavorable'}:
                row.verdict = 'conditional' if row.conditions and row.basis != 'unknown' else 'unknown'
                row.conditions = list(dict.fromkeys(row.conditions + ['조직의 비용·품질·운영 목표가 미정이므로 도입 적합성은 조건부']))
            if row.verdict == 'not_applicable' and (row.basis == 'unknown' or not row.conditions):
                row.verdict = 'unknown'
            row.context_findings = contexts
            output.append(row)
    for tech_id, criterion in counts:
        if tech_id not in data.technologies:
            errors.append({"stage": "validate", "code": "unexpected_technology", "tech_id": tech_id})
    questions, seen = [], set()
    for q in analysis.followup_questions:
        key = (q.tech_id, q.query.strip())
        if q.tech_id in data.technologies and q.query.strip() and len(q.query) <= 400 and key not in seen:
            questions.append(q)
            seen.add(key)
    return Analysis(assessments=output, followup_questions=questions[:2]), errors
