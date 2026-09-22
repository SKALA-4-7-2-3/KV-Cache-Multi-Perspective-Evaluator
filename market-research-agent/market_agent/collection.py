"""한 회차의 검색·원문 수집. 원문 재시도도 예약 예산에 포함한다."""
import hashlib
from datetime import datetime, timezone
from itertools import zip_longest
from urllib.parse import urlsplit

from .schemas import Evidence
from .sources import rank_candidates, select_segments, content_fallback, content_quality, publication_date
from .tools import ProviderError, canonical_url, public_url


def collect_sources(state, data, web, budget, questions, relevant_candidate):
    errors, evidence = list(state['errors']), dict(state['evidence'])
    sources, queries, groups = dict(state['sources']), list(state['queries']), []
    fatal = state['fatal']
    round_number = state['round']
    cap = min(budget.limits['extract'], 6) if round_number == 0 else budget.limits['extract']
    # 작은 할당량에서도 가능한 범위로 보완분을 남긴다.
    if round_number == 0 and budget.limits['extract'] < 10:
        cap = max(1, (budget.limits['extract'] * 3) // 5) if budget.limits['extract'] else 0
    level=state.get('research_level',round_number)
    if level == 1:
        cap=min(cap, max(6, (budget.limits['extract']*3)//5))
    for q in questions[:(2 if level==0 else 6)]:
        if not budget.remaining('search') or fatal:
            break
        log = dict(id=f'SEARCH-{len(queries)+1}', **q.model_dump(), round=round_number, research_level=level, candidates=[])
        queries.append(log)
        try:
            candidates = budget.call('search', lambda: web.search(q.query, data.as_of))
            selected = [(r, relevant_candidate(r, data.technologies[q.tech_id])) for r in candidates]
            log['candidates'] = [dict(url=r.get('url', ''), title=r.get('title', ''), selected=keep,
                reason='대상·항목 관련성 검토' if keep else 'no_topic_match') for r, keep in selected]
            ranked = rank_candidates([r for r, keep in selected if keep], data.technologies[q.tech_id], q.criteria)
            groups.append([(q.tech_id, q.criterion_id, q.criteria, r) for r in ranked[:3]])
        except ProviderError as exc:
            errors.append(dict(stage='search', code=exc.code, tech_id=q.tech_id, criterion_id=q.criterion_id, round=str(round_number)))
            fatal |= exc.fatal
    candidates = [item for group in zip_longest(*groups) for item in group if item]
    if not fatal:
        papers = [(t.id, 'commercialization', ['commercialization', 'ecosystem_support', 'business_value'],
            dict(url=t.url, title=t.paper, content='', published_at=None)) for t in data.technologies.values() if public_url(t.url)]
        # 원문이 남은 기존 후보도 보완 회차에서 회수한다.
        pending = [(t, 'commercialization', ['commercialization', 'ecosystem_support'],
            dict(url=e.url, title=e.title, content=e.excerpt, published_at=e.published_at))
            for e in evidence.values() if e.access_status == 'snippet' for t in e.tech_ids if t in data.technologies]
        candidates = (papers + candidates) if round_number == 0 else (candidates + pending + papers)
    by_url = {canonical_url(e.url): e.id for e in evidence.values() if public_url(e.url)}
    by_url.update({canonical_url(e.requested_url): e.id for e in evidence.values() if public_url(e.requested_url)})
    by_content = {e.content_hash: e.id for e in evidence.values() if e.content_hash and e.access_status == 'full_text'}
    attempted = set()
    for tech_id, criterion, criteria, row in candidates:
        if fatal:
            break
        url = row.get('url', '')
        if not public_url(url):
            continue
        url = canonical_url(url)
        requested_url = url
        prior = evidence.get(by_url.get(url))
        if prior and prior.access_status == 'full_text':
            prior.tech_ids = list(dict.fromkeys([*prior.tech_ids, tech_id]))
            prior.criteria = list(dict.fromkeys([*prior.criteria,*criteria]))
            raw=sources.get(prior.doc_id)
            if raw:
                extra=select_segments(raw,data.technologies[tech_id],prior.criteria)
                windows={(s.start,s.end):s for s in [*prior.segments,*extra]}
                prior.segments=list(windows.values())
                prior.excerpt='\n\n'.join(s.text for s in prior.segments)
            continue
        if url in attempted:
            continue
        attempted.add(url)
        published = row.get('published_at')
        if published and published > data.as_of:
            errors.append(dict(stage='collect', code='source_after_as_of', tech_id=tech_id, criterion_id=criterion, url=url))
            continue
        raw, access = row.get('content', ''), 'snippet'
        quality, quality_reason = 'unchecked', ''
        room = min(budget.remaining('extract'), max(0, cap-budget.used['extract']))
        if room:
            try:
                raw = budget.call('extract', lambda: web.extract(url), max_attempts=min(2, room))
                access = 'full_text'
                quality, quality_reason = content_quality(raw, url, data.technologies[tech_id])
            except ProviderError as exc:
                errors.append(dict(stage='extract', code=exc.code, tech_id=tech_id, criterion_id=criterion, url=url, round=str(round_number)))
                fatal |= exc.fatal
            alternative = content_fallback(url)
            if quality != 'substantive' and not fatal and alternative and budget.used['extract'] < cap and budget.remaining('extract'):
                try:
                    fallback_raw = budget.call('extract', lambda: web.extract(alternative), max_attempts=1)
                    quality, quality_reason = content_quality(fallback_raw, alternative, data.technologies[tech_id])
                    raw, url, access = fallback_raw, alternative, 'full_text'
                except ProviderError as fallback_error:
                    errors.append(dict(stage='extract', code=fallback_error.code, tech_id=tech_id, criterion_id=criterion, url=alternative, round=str(round_number)))
                    fatal |= fallback_error.fatal
        else:
            # 미선택 후보는 snippet으로 남긴다. 실제 실패/미검토 상태와 구분한다.
            quality_reason='candidate_deferred: 원문 조회 한도 또는 보완 예약'
        content_hash = hashlib.sha256(raw.encode()).hexdigest()
        if access=='full_text' and published is None:
            published=publication_date(raw)
        if access == 'full_text' and content_hash in by_content:
            old = evidence[by_content[content_hash]]
            old.tech_ids = list(dict.fromkeys([*old.tech_ids, tech_id]))
            old.criteria = list(dict.fromkeys([*old.criteria,*criteria]))
            by_url[url] = old.id
            errors = [e for e in errors if not (e['stage'] == 'extract' and e.get('url') == url)]
            continue
        suffix = hashlib.sha256((url+'\n'+raw).encode()).hexdigest()[:16]
        eid, doc_id = f'MKT-{suffix}', f'WEB-{suffix}'
        segments = select_segments(raw, data.technologies[tech_id], list(dict.fromkeys(criteria))) if access == 'full_text' else []
        scope = 'Abstract 페이지' if urlsplit(url).hostname == 'arxiv.org' and '/abs/' in url else ('추출 본문' if access == 'full_text' else '검색 발췌')
        evidence[eid] = Evidence(id=eid, doc_id=doc_id, title=row.get('title', url), url=url,
            publisher=urlsplit(url).hostname or '', published_at=published, retrieved_at=datetime.now(timezone.utc).isoformat(),
            locator='; '.join(s.locator for s in segments) or '검색 발췌',
            excerpt='\n\n'.join(s.text for s in segments) if segments else raw[:12000], segments=segments,
            access_scope=scope, content_hash=content_hash, source_type='발행 도메인 확인; 주장 성격은 인용별 표시', access_status=access, tech_ids=[tech_id],
            content_status=quality, content_reason=quality_reason, requested_url=requested_url,criteria=criteria)
        by_url[url] = eid
        by_url[requested_url] = eid
        if access == 'full_text':
            sources[doc_id] = raw
            by_content[content_hash] = eid
            errors = [e for e in errors if not (e['stage'] == 'extract' and e.get('url') in {url, row.get('url')})]
    return dict(evidence=evidence, sources=sources, queries=queries, errors=errors, fatal=fatal,
        history=state['history']+['collect'])
