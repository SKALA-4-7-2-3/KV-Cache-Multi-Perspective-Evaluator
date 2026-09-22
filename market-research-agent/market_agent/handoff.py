"""다른 에이전트에 전달하는 시장성 평가 JSON. 내부 실행 상태와 원문은 제외한다."""
import json

from .delivery import delivery_coverage
from .schemas import CRITERIA
from .tools import public_url

HANDOFF_SCHEMA_VERSION = '1.0.0'
HANDOFF_FILENAME = 'market_handoff.json'

ROW_FIELDS = ('tech_id', 'criterion_id', 'observation', 'judgment', 'verdict', 'basis',
    'relation_to_technology', 'evaluation_mode', 'generation_method', 'evaluation_level',
    'confidence', 'conditions', 'gaps', 'metric', 'research_status', 'unknown_reasons')


def build_handoff(state):
    data, result = state['data'], state['result']
    expected = {(t, c) for t in data.technologies for c in CRITERIA}
    rows = {(r.tech_id, r.criterion_id): r for r in result.assessments}
    if set(rows) != expected or len(rows) != len(result.assessments):
        raise ValueError('handoff_assessment_coverage: 기술별 6개 평가가 필요합니다')
    sources, quote_words = {}, {}

    def reference(ref, tech_id, fields):
        evidence = state['evidence'].get(ref.evidence_id)
        if evidence is None or tech_id not in evidence.tech_ids:
            raise ValueError('handoff_source_reference: 출처가 없거나 기술 소유 관계가 다릅니다')
        if evidence.id not in sources:
            url = evidence.url if public_url(evidence.url) else None
            identity = url or evidence.id
            words = ref.quote.split()
            remaining = max(0, 25 - quote_words.get(identity, 0))
            excerpt = ' '.join(words[:remaining]) or None
            quote_words[identity] = quote_words.get(identity, 0) + min(len(words), remaining)
            sources[evidence.id] = dict(evidence_id=evidence.id, title=evidence.title, url=url,
                publisher=evidence.publisher or None,
                published_at=str(evidence.published_at) if evidence.published_at else None,
                retrieved_at=evidence.retrieved_at or None, access_status=evidence.access_status,
                access_scope=evidence.access_scope, content_status=evidence.content_status,
                quote_excerpt=excerpt, quote_truncated=len(words)>remaining)
        value = ref.model_dump(mode='json', include=set(fields))
        value['locator'] = ref.locator or evidence.locator
        return value

    def citations(items, tech_id):
        return [reference(c, tech_id, ('evidence_id', 'subject', 'source_character', 'locator')) for c in items]

    assessments = []
    for tech_id in data.technologies:
        for criterion, label in CRITERIA.items():
            row = rows[tech_id, criterion]
            item = row.model_dump(mode='json', include=set(ROW_FIELDS))
            item['criterion_name'] = label
            # v1.4에 없던 생성 방식 필드를 모델 생성으로 잘못 소급하지 않는다.
            if result.output_schema_version == '0.5':
                item['generation_method'] = 'verified_claim' if row.evaluation_mode == 'grounded' else 'deterministic_fallback'
                item['evaluation_level'] = None
            item['citations'] = citations(row.citations, tech_id)
            item['supporting_materials'] = [reference(m, tech_id,
                ('evidence_id', 'locator', 'review_status', 'reason')) for m in row.supporting_materials]
            item['context_findings'] = [dict(
                finding.model_dump(mode='json', exclude={'citations'}),
                citations=citations(finding.citations, tech_id)) for finding in row.context_findings]
            assessments.append(item)
    errors = []
    for error in result.errors:
        item = {k: v for k, v in error.items() if k in {'stage', 'code', 'tech_id', 'criterion_id', 'scope', 'round'}}
        if public_url(error.get('url', '')):
            item['url'] = error['url']
        errors.append(item)
    warnings = list(data.warnings)
    if result.mode == 'fixture':
        warnings.insert(0, 'fixture 모드의 가상 테스트 결과입니다. 실제 시장조사 결과가 아닙니다.')
    return dict(schema_version=HANDOFF_SCHEMA_VERSION, role='market', run_id=data.run_id,
        as_of=str(data.as_of), domain=data.domain, mode=result.mode, status=result.status,
        execution_status=result.execution_status,
        provenance=dict(input_hash=data.input_hash, model=state['model'],
            result_schema_version=result.output_schema_version),
        coverage=dict(expected=len(expected), provided=len(assessments), **delivery_coverage(result)),
        technologies=[dict(tech_id=t.id, name=t.name, approach=t.approach, paper=t.paper,
            paper_url=t.url if public_url(t.url) else None, status=result.technology_status[t.id])
            for t in data.technologies.values()],
        assessments=assessments, sources=sources, errors=errors, warnings=warnings)


def render_handoff(state):
    return json.dumps(build_handoff(state), ensure_ascii=False, indent=2, allow_nan=False) + '\n'
