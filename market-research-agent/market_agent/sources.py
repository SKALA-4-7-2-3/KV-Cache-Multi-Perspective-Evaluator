"""후보 우선순위와 원문 문단 선택. 검색 순위는 사실성 판정이 아니다."""
import re
from datetime import date, datetime
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


def publication_date(raw):
    """명시된 발행 표기·보도자료 dateline만 읽는다. 행사·저작권 날짜는 제외한다."""
    months=r'January|February|March|April|May|June|July|August|September|October|November|December'
    for line in raw[:16000].splitlines():
        explicit=re.search(r'\b(?:published|posted|submitted)(?:\s+(?:on|date))?\s*[:：]?\s*(\d{4}-\d{2}-\d{2})',line,re.I)
        if explicit:
            try:return date.fromisoformat(explicit[1])
            except ValueError:continue
        dateline=re.search(r'[–—]\s*('+months+r')\s+(\d{1,2}),\s*(\d{4})\s*[–—]',line)
        if dateline and re.search(r'today announced',line,re.I):
            try:return datetime.strptime(' '.join(dateline.groups()),'%B %d %Y').date()
            except ValueError:continue
    return None


def content_quality(raw, url, tech):
    """접근 성공과 내용 확보를 구분한다. 의미상 주장의 진실성 검사는 아니다."""
    paper = urlsplit(url).hostname == 'arxiv.org'
    title = re.search(r'^#+\s*Title:\s*(.+)$', raw, re.M | re.I)
    if paper and title and tech.name.casefold() not in title[1].casefold():
        return 'identity_mismatch', '요청한 논문과 추출 제목이 다름'
    body = re.split(r'^#+\s*(?:Bibliographic|arXivLabs|References & Citations)', raw, maxsplit=1, flags=re.M)[0]
    paragraphs = []
    for block in re.split(r'\n\s*\n', body):
        text = re.sub(r'^#{1,6}[^\n]*', '', block, flags=re.M)
        text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text).strip()
        if not text or text.startswith(('#', '|')):
            continue
        if re.match(r'^(arXivLabs|Both individuals|Have an idea|Watch the latest|Navigation)', text, re.I):
            continue
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
        if len(re.findall(r'\w+', text)) >= 6 and re.search(r'[.!?。]|다[.\s]', text):
            paragraphs.append(text)
    if not paragraphs:
        return 'metadata_only', '제목·메뉴 외에 분석 가능한 본문을 확보하지 못함'
    return 'substantive', '문장 형태의 본문 확보; 주장별 검증은 별도'


def content_fallback(url):
    p = urlsplit(url)
    match = re.fullmatch(r'/abs/(\d{4}\.\d{4,5}(?:v\d+)?)', p.path)
    if p.hostname == 'arxiv.org' and match:
        return 'https://arxiv.org/html/' + match[1]
    return fallback_url(url)


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
        return (direct, first_party, purpose, relevance(body, tech, criteria))
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
