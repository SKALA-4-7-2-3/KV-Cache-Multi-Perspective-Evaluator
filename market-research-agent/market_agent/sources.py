"""후보 우선순위와 원문 문단 선택. 검색 순위는 사실성 판정이 아니다."""
import re
from urllib.parse import urlsplit

from .schemas import Segment

TERMS = {
    'market_size_growth': ['market size', 'forecast', 'billion', 'cagr', '시장', 'growth'],
    'commercialization': ['product', 'license', 'release', 'available', 'implementation', '제품', 'commercial'],
    'adoption': ['customer', 'production', 'deploy', 'pilot', '고객', 'adopt'],
    'ecosystem_support': ['support', 'integration', 'compatible', 'framework', '지원'],
    'standardization': ['standard', 'cxl', 'pcie', 'specification', '표준'],
    'business_value': ['cost', 'memory', 'efficiency', 'price', '비용', 'latency'],
}


def relevance(text, tech, criteria):
    lower = text.casefold()
    direct = 12 if tech.name.casefold() in lower else 0
    topical = 2 * len(re.findall(r'kv[\s_-]*cache|\bcxl\b|photonic|llm|메모리', lower))
    purpose = sum(3 for c in criteria for term in TERMS[c] if term in lower)
    return direct + min(topical, 8) + purpose


def rank_candidates(rows, tech, criteria):
    def score(row):
        host = (urlsplit(row.get('url', '')).hostname or '').lower()
        first_party = host in {'arxiv.org', 'github.com', 'docs.vllm.ai', 'marvell.com', 'www.marvell.com', 'computeexpresslink.org'}
        direct = tech.name.casefold() in f"{row.get('title', '')} {row.get('content', '')}".casefold()
        body = f"{row.get('title', '')} {row.get('content', '')}".casefold()
        purpose = any(term in body for c in criteria for term in TERMS[c])
        return (direct, purpose, first_party, relevance(body, tech, criteria))
    return sorted(rows, key=score, reverse=True)


def select_segments(raw, tech, criteria, limit=12000):
    candidates = []
    # 긴 단일 문단도 제한된 크기로 나누되 원문 오프셋은 유지한다.
    for match in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', raw):
        for start in range(match.start(), match.end(), 1400):
            end = min(start + 1400, match.end())
            value = relevance(raw[start:end], tech, criteria)
            if value:
                candidates.append((value, max(0, start - 500), min(len(raw), end + 500)))
    if not candidates:
        candidates = [(0, 0, min(len(raw), limit))]
    windows = []
    for _, start, end in sorted(candidates, key=lambda item: (-item[0], item[1])):
        trial = sorted(windows + [(start, end)])
        merged = []
        for a, b in trial:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        if sum(b-a for a, b in merged) <= limit:
            windows = merged
    result = []
    for start, end in windows:
        headers = re.findall(r'^#{1,6}\s+(.+)$', raw[:start], re.M)
        loc = f'{headers[-1][:140] if headers else "본문"}; 추출 텍스트 문자 {start}:{end}'
        result.append(Segment(text=raw[start:end], start=start, end=end, locator=loc))
    return result


def fallback_url(url):
    p = urlsplit(url)
    if p.hostname == 'arxiv.org' and re.fullmatch(r'/pdf/\d{4}\.\d{4,5}(v\d+)?(\.pdf)?', p.path):
        return 'https://arxiv.org/abs/' + p.path.split('/')[-1].removesuffix('.pdf')
    return None
