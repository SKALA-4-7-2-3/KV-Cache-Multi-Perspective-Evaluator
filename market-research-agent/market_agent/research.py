"""실행 사실로부터 항목별 조사 상태를 계산한다. 모델의 상태 추측은 덮어쓴다."""
from .sources import TERMS
from .search_plan import SUFFIXES

REASONS = {
    'content_insufficient': '관련 페이지의 본문을 충분히 확보하지 못함',
    'processing_error': '근거 추출·평가의 처리 오류가 남아 있어 결론을 보류함',
    'not_searched': '이 항목을 직접 조사하거나 관련 원문을 검토하지 못함',
    'no_relevant_source': '이번 검색에서 관련 자료를 확보하지 못함',
    'source_inaccessible': '관련 후보의 원문에 접근하지 못함',
    'budget_exhausted': '배정된 호출 한도 안에서 추가 확인을 완료하지 못함',
    'insufficient_evidence': '확보 자료로 해당 결론을 뒷받침하기 어려움',
    'identity_unverified': '선정 논문과 제품·구현의 동일성 미확인',
    'conflicting_sources': '자료의 주장·조건이 충돌하여 판단 보류',
    'date_unverified': '기준일 당시 상태를 확인할 날짜 근거 부족',
}


def error_applies(error, row, evidence):
    if error.get('scope') == 'global':
        return True
    if error.get('tech_id'):
        return error['tech_id'] == row.tech_id and error.get('criterion_id') in {None,row.criterion_id}
    source = evidence.get(error.get('evidence_id'))
    return bool(source and row.tech_id in source.tech_ids)


def annotate(analysis, data, evidence, queries, errors, budget, model_ran, *, reviewed=None):
    rows = []
    for original in analysis.assessments:
        row = original.model_copy(deep=True)
        row.gaps = [g for g in row.gaps if g not in REASONS.values()]
        relevant_queries = [q for q in queries if q['tech_id'] == row.tech_id and row.criterion_id in q['criteria']]
        row.search_ids = [q['id'] for q in relevant_queries]
        scoped = [e for e in evidence.values() if row.tech_id in e.tech_ids and e.access_status == 'full_text'
            and any(term in e.excerpt.casefold() for term in TERMS[row.criterion_id])]
        cited = row.evidence_ids + [c.evidence_id for f in row.context_findings for c in f.citations]
        row.reviewed_evidence_ids = list(dict.fromkeys([*(reviewed.get((row.tech_id,row.criterion_id),[]) if reviewed is not None else (e.id for e in scoped)), *cited])) if model_ran else []
        row.research_status = 'reviewed' if row.reviewed_evidence_ids else ('searched' if row.search_ids else 'not_started')
        row.unknown_reasons = [r for r in row.unknown_reasons if r in {'identity_unverified', 'conflicting_sources', 'date_unverified'}]
        if row.basis == 'unknown':
            if any(row.tech_id in e.tech_ids and e.content_status in {'metadata_only','identity_mismatch'} for e in evidence.values()):
                row.unknown_reasons.append('content_insufficient')
            if any(e['stage'] in {'claims','compose','validate','llm_extract','llm_compose'} and error_applies(e,row,evidence) for e in errors):
                row.unknown_reasons.append('processing_error')
            if row.research_status == 'not_started':
                row.unknown_reasons.append('not_searched')
            if relevant_queries and not scoped:
                row.unknown_reasons.append('no_relevant_source')
            failures = [e for e in errors if e.get('tech_id') == row.tech_id and e.get('criterion_id') in {None, row.criterion_id}]
            if any(e['stage'] == 'extract' and not e['code'].startswith('budget_') for e in failures):
                row.unknown_reasons.append('source_inaccessible')
            if any(e['code'].startswith('budget_') for e in failures) or not budget.remaining('llm') or (not scoped and (not budget.remaining('search') or not budget.remaining('extract'))):
                row.unknown_reasons.append('budget_exhausted')
            if row.reviewed_evidence_ids:
                row.unknown_reasons.append('insufficient_evidence')
            row.unknown_reasons = list(dict.fromkeys(row.unknown_reasons or ['insufficient_evidence']))
            row.gaps = list(dict.fromkeys([*row.gaps, *(REASONS[r] for r in row.unknown_reasons)]))
            if row.judgment in {'미확인: 아직 시장 근거가 없습니다', '미확인'}:
                row.judgment = '미확인: ' + REASONS[row.unknown_reasons[0]]
        row.next_action = f'{data.technologies[row.tech_id].name} {SUFFIXES[row.criterion_id]}' if row.gaps else ''
        rows.append(row)
    return analysis.model_copy(update={'assessments': rows})
