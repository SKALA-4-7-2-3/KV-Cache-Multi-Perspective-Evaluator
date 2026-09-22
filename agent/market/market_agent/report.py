"""통합 평가보고서에 들어갈 시장성 항목과 실제 인용 근거만 직렬화한다."""

import html
import re
from urllib.parse import quote

from .schemas import CRITERIA
from .delivery import delivery_coverage
from .research import REASONS
from .tools import public_url


def esc(value):
    text = html.escape(' '.join(str(value).splitlines()), quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+.!|>])', r'\\\1', text)


def row_citations(row):
    return [*row.citations, *(c for f in row.context_findings for c in f.citations)]


def metric_text(m):
    return esc(f'{m.value:g} {m.unit}; {m.currency or "해당 없음"}; {m.year}; {m.geography}; {m.market_definition}; {m.actual_or_forecast}')


def render_report(state):
    data, result = state['data'], state['result']
    lines = ['# 시장성 평가', '', f'평가 기준일: {data.as_of} · 적용 도메인: {esc(data.domain)}', '']
    if result.mode == 'fixture':
        lines += ['fixture 모드의 가상 테스트 결과입니다. 실제 시장조사 결과가 아닙니다.', '']
    rows = {(r.tech_id, r.criterion_id): r for r in result.assessments}
    cited, materials = {}, {}
    counts=delivery_coverage(result)
    lines += [f"평가 제공: {len(result.assessments)}/{len(data.technologies)*len(CRITERIA)}개 · 근거 기반 {counts['grounded']} · 잠정평가 {counts['provisional']} · 기술 시나리오 {counts['scenario']} · 조사 계획 {counts['research_plan']}", '',
        '잠정평가는 관련 자료를 활용한 도입 판단입니다. 기술 시나리오는 입력의 기술 전제에 따른 판단입니다. 두 경우 모두 선정 기술의 시장 실적을 확정하지 않습니다.', '']
    execution={'completed':'완료','partial':'일부 단계 미완료','failed':'처리 실패'}[result.execution_status]
    lines += [f'조사 처리 상태: {execution}.', '']
    if result.errors:
        lines += [f'남은 처리 문제: {len(result.errors)}건. 해당 항목의 자료 한계와 참고자료 검토 사유를 확인하세요.', '']
    quote_words = {}
    def short_quote(url, text):
        words=text.split();remaining=max(0,25-quote_words.get(url,0))
        quote_words[url]=quote_words.get(url,0)+min(len(words),remaining)
        return ' '.join(words[:remaining])+(' …' if remaining and len(words)>remaining else '')
    for tech in data.technologies.values():
        lines += [f'## {esc(tech.id)} · {esc(tech.name)}', '',
            '| 항목 ID·항목 | 평가 내용 | 판정 | 근거 성격·범위 | 적용 조건·추가 확인 | 인용·참고자료 ID |',
            '| --- | --- | --- | --- | --- | --- |']
        for criterion, label in CRITERIA.items():
            r = rows[tech.id, criterion]
            text = (esc('자료 관찰: '+r.observation)+'<br>' if r.observation else '') + esc('평가: '+r.judgment if r.observation else r.judgment)
            for f in r.context_findings:
                subjects = ', '.join(dict.fromkeys(c.subject for c in f.citations))
                refs = ', '.join(dict.fromkeys(c.evidence_id for c in f.citations))
                text += '<br>' + esc(f'관련 정보 [{f.basis}/{f.relation_to_technology}; 대상: {subjects}; 근거: {refs}]: {f.statement}')
                if f.conditions:
                    text += '<br>' + esc('관련 정보 조건: ' + '; '.join(f.conditions))
                if f.metric:
                    text += '<br>' + metric_text(f.metric)
            if r.metric:
                text += '<br>' + metric_text(r.metric)
            gaps=list(r.gaps) if r.evaluation_mode=='grounded' or r.generation_method=='model_synthesis' else []
            gaps.extend(REASONS[key] for key in r.unknown_reasons if key in REASONS)
            limits = '; '.join(dict.fromkeys([*r.conditions, *gaps])) or '기록된 추가 조건·공백 없음'
            citations = row_citations(r)
            for c in citations:
                cited.setdefault(c.evidence_id, []).append(c)
            for m in r.supporting_materials:
                materials.setdefault(m.evidence_id, []).append(m)
            refs=[c.evidence_id for c in citations]+[m.evidence_id+' (참고)' for m in r.supporting_materials]
            ids=', '.join(dict.fromkeys(refs)) or '기술 설명 기반'
            mode={'grounded':'근거 기반','provisional':'관련 자료 잠정평가','scenario':'기술 시나리오','research_plan':'조사 계획'}[r.evaluation_mode]
            confidence={'high':'높음','medium':'보통','low':'낮음'}[r.confidence]
            generation={'model_synthesis':'자료 종합 생성','verified_claim':'검증 주장 기반','deterministic_fallback':'정형 비상 출력'}[r.generation_method]
            nature = f'{mode}; {generation}; 신뢰도 {confidence}; {r.basis} / {r.relation_to_technology}'
            characters = list(dict.fromkeys(c.source_character for c in r.citations))
            if characters:
                nature += '; ' + '; '.join(characters)
            lines.append(f'| `{criterion}` · {label} | {text} | {r.verdict} | {esc(nature)} | {esc(limits)} | {esc(ids)} |')
        lines.append('')
    lines += ['## 인용 근거', '']
    if not cited:
        lines.append('인용한 근거 없음.')
    else:
        lines += ['| 근거 ID | 제목·발행자 | 발행일·조회일 | URL·원문 위치 | 접근 범위·발행 성격 | 짧은 발췌 |',
            '| --- | --- | --- | --- | --- | --- |']
        for eid, citations in cited.items():
            e = state['evidence'][eid]
            url = f'[원문](<{quote(e.url, safe=":/?&=#%") }>)' if public_url(e.url) else '공개 URL 미확인'
            locations = '; '.join(dict.fromkeys(c.locator or e.locator or '인용 문구로 검색' for c in citations))
            characters = '; '.join(dict.fromkeys(c.source_character for c in citations))
            short = short_quote(e.url,citations[0].quote)
            lines.append(f'| {esc(eid)} | {esc(e.title)} / {esc(e.publisher or "미확인")} | {e.published_at or "미확인"} / {esc(e.retrieved_at or "입력에 없음")} | {url}<br>{esc(locations)} | {esc(e.access_scope)} / {e.access_status}; {esc(characters)} | {esc(short or "같은 URL의 위 발췌 및 원문 위치 참조")} |')
    if materials:
        lines += ['', '## 평가 참고자료', '',
            '아래 자료는 검증 인용과 구분하여 제공합니다. 원문 발췌·기술 요약·검색 발췌와 검토 한계를 보존하여 통합 에이전트가 재검토할 수 있습니다.', '',
            '| 자료 ID | 제목·URL | 자료 상태·활용 한계 | 위치·짧은 발췌 |', '| --- | --- | --- | --- |']
        labels={'reference_only':'원문 참고','provided_context':'기술 입력 요약','search_excerpt':'검색 발췌','excluded':'추적용·판정 제외'}
        for eid, refs in materials.items():
            e=state['evidence'][eid]
            url=f'[원문](<{quote(e.url,safe=":/?&=#%") }>)' if public_url(e.url) else '입력 자료'
            reason='; '.join(dict.fromkeys(labels[m.review_status]+': '+m.reason for m in refs))
            excerpt=short_quote(e.url,refs[0].quote) or '위 인용 발췌 또는 원문 위치 참조'
            locations='; '.join(dict.fromkeys(m.locator for m in refs if m.locator))
            lines.append(f'| {esc(eid)} | {esc(e.title)}<br>{url} | {esc(reason)} | {esc(locations)}<br>{esc(excerpt)} |')
    return '\n'.join(lines).rstrip() + '\n'
