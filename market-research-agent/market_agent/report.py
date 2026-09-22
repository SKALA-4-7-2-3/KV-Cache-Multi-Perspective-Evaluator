"""통합 평가보고서에 들어갈 시장성 항목과 실제 인용 근거만 직렬화한다."""

import html
import re
from urllib.parse import quote

from .schemas import CRITERIA
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
    cited = {}
    for tech in data.technologies.values():
        lines += [f'## {esc(tech.id)} · {esc(tech.name)}', '',
            '| 항목 ID·항목 | 평가 내용 | 판정 | 근거 성격·범위 | 적용 조건·미확인 | 근거 ID |',
            '| --- | --- | --- | --- | --- | --- |']
        for criterion, label in CRITERIA.items():
            r = rows[tech.id, criterion]
            text = esc(r.judgment)
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
            limits = '; '.join(dict.fromkeys([*r.conditions, *r.gaps])) or '기록된 추가 조건·공백 없음'
            citations = row_citations(r)
            for c in citations:
                cited.setdefault(c.evidence_id, []).append(c)
            ids = ', '.join(dict.fromkeys(c.evidence_id for c in citations)) or '없음'
            nature = f'{r.basis} / {r.relation_to_technology}'
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
        quote_words = {}
        for eid, citations in cited.items():
            e = state['evidence'][eid]
            url = f'[원문](<{quote(e.url, safe=":/?&=#%") }>)' if public_url(e.url) else '공개 URL 미확인'
            locations = '; '.join(dict.fromkeys(c.locator or e.locator or '인용 문구로 검색' for c in citations))
            characters = '; '.join(dict.fromkeys(c.source_character for c in citations))
            words = citations[0].quote.split()
            remaining = max(0, 25 - quote_words.get(e.url, 0))
            short = ' '.join(words[:remaining]) + (' …' if remaining and len(words) > remaining else '')
            quote_words[e.url] = quote_words.get(e.url, 0) + min(len(words), remaining)
            lines.append(f'| {esc(eid)} | {esc(e.title)} / {esc(e.publisher or "미확인")} | {e.published_at or "미확인"} / {esc(e.retrieved_at or "입력에 없음")} | {url}<br>{esc(locations)} | {esc(e.access_scope)} / {e.access_status}; {esc(characters)} | {esc(short or "같은 URL의 위 발췌 및 원문 위치 참조")} |')
    return '\n'.join(lines).rstrip() + '\n'
