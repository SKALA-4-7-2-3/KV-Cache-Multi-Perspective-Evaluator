"""Replaceable model/search adapters; constructors never make network calls.

Search snippets are discovery hints only. ``fetch`` supplies independently retrieved
source text, and reports unsupported/unavailable pages instead of inventing content.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Protocol, TypeVar
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from langchain_openai import ChatOpenAI
from markdown_it import MarkdownIt
from pydantic import BaseModel

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
_BLOCKS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "table", "blockquote")
_T = TypeVar("_T", bound=BaseModel)


class ProviderError(RuntimeError):
    """A safe, user-displayable provider failure without credentials or body text."""

    def __init__(self, message: str, *, fatal: bool = False):
        super().__init__(message)
        self.fatal = fatal
        self.public_message = message


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str = ""
    published_at: str = "미표기"


@dataclass
class SourcePage:
    url: str
    title: str
    text: str
    publisher: str = "미표기"
    published_at: str = "미표기"
    location: str = "본문"
    author: str = "미표기"
    metadata_provenance: dict[str, str] = field(default_factory=dict)


class WebProvider(Protocol):
    def search(self, query: str, max_results: int = 3) -> list[SearchHit]: ...

    def fetch(self, url: str) -> SourcePage: ...


class ModelProvider(Protocol):
    def generate(self, schema: type[_T], system: str, payload: dict) -> _T: ...


class OpenAIModel:
    def __init__(self, model: str, api_key: str, base_url: str | None = None,
                 timeout: float = 60):
        if not api_key.strip():
            raise ProviderError("모델 API 키가 설정되지 않았습니다.")
        self._client = ChatOpenAI(model=model, api_key=api_key, base_url=base_url,
                                  timeout=timeout, max_retries=0)

    def generate(self, schema: type[_T], system: str, payload: dict) -> _T:
        try:
            from .models import Assessment, CatalogAssessment, OperatorReview, Review
            operator_mode = payload.get("analysis_mode") == "operator_impact"
            wire_schema = schema
            if operator_mode and schema is Assessment:
                wire_schema = CatalogAssessment
            elif operator_mode and schema is Review:
                wire_schema = OperatorReview
                expected = payload.get("review_candidate_indices")
                if (not isinstance(expected, list)
                        or any(type(index) is not int or index < 0 for index in expected)
                        or len(expected) != len(set(expected))):
                    raise ValueError("invalid_review_candidates")
            result = self._client.with_structured_output(
                wire_schema, method="json_schema", strict=True,
            ).invoke([("system", system), ("human", json.dumps(payload, ensure_ascii=False))])
            if result is None:
                raise ProviderError("모델이 구조화된 응답을 반환하지 않았습니다.")
            parsed = wire_schema.model_validate(result.model_dump() if isinstance(result, BaseModel) else result)
            if wire_schema is OperatorReview:
                received = [check.claim_index for check in parsed.checks]
                if (len(received) != len(expected) or set(received) != set(expected)
                        or len(received) != len(set(received))
                        or any(not check.reason.strip() for check in parsed.checks)):
                    raise ValueError("incomplete_claim_review")
                checks = {check.claim_index: check for check in parsed.checks}
                rejected = [index for index in expected if not checks[index].supported]
                return schema.model_validate({
                    "rejected_claim_indices": rejected,
                    "issues": [f"주장 {index}: {checks[index].reason.strip()}" for index in rejected],
                    "queries": [query.model_dump() for query in parsed.queries],
                })
            return schema.model_validate(parsed.model_dump())
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - sanitize all third-party errors at the provider boundary
            # Provider exceptions can include request bodies and credentials.
            if getattr(exc, "status_code", None) in (401, 403):
                raise ProviderError("모델 API 인증 또는 접근 권한 오류입니다. 로컬 API 키와 권한을 확인하세요.",
                                    fatal=True) from None
            raise ProviderError("모델 호출 또는 응답 검증에 실패했습니다.") from None


def _date(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "미표기"
    value = value.strip()
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        try:
            return parsedate_to_datetime(value).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            for date_format in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
                                "%d %B %Y", "%d %b %Y", "%Y.%m.%d", "%Y년 %m월 %d일"):
                try:
                    return datetime.strptime(value, date_format).date().isoformat()  # noqa: DTZ007 - date only
                except ValueError:
                    continue
            return "미표기"


def _name(value: object) -> str:
    """Read explicit author/publisher names without interpreting their identity."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return _name(value.get("name"))
    if isinstance(value, list):
        return "; ".join(filter(None, (_name(item) for item in value)))
    return ""


def _visible_markdown_lines(text: str) -> list[str]:
    """Keep line positions while excluding quoted and fenced sample metadata."""
    lines = text.splitlines()
    for token in MarkdownIt().parse(text):
        if token.type in ("blockquote_open", "fence", "code_block") and token.map:
            for index in range(token.map[0], min(token.map[1], len(lines))):
                lines[index] = ""
    return lines


def _plain_markdown(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    return value.replace("**", "").replace("__", "").strip()


def _generic_heading(value: str) -> bool:
    value = _plain_markdown(value).casefold().strip(" :|-")
    generic = {"home", "blog", "blogs", "news", "newsroom", "news & events", "press releases", "products",
               "solutions", "by type", "by industry", "by product", "by date", "categories", "menu",
               "navigation", "search", "resources", "company", "about", "investors", "contact", "markets",
               "platforms", "technology", "subscribe", "related articles", "latest posts", "latest news"}
    return value in generic or bool(re.fullmatch(r"[\w &.-]{1,50}\s+(?:blogs?|newsroom|news & events)", value))


def _metadata_lines(text: str, source: str, header_line: int | None = None,
                    require_heading: bool = False) -> tuple[dict[str, str], dict[str, str]]:
    """Only explicit bylines/date labels count; years in body/footer do not."""
    values: dict[str, str] = {}
    provenance: dict[str, str] = {}
    if require_heading and header_line is None:
        return values, provenance
    patterns = {
        "author": r"^(?:By|Written by|Author|Authors|작성자|글쓴이|저자)(?:\s*[:：]\s*|\s+)(.+)$",
        "publisher": r"^(?:Publisher|Published by|발행기관|발행처|게시기관)\s*[:：]\s*(.+)$",
        "published_at": r"^(?:Published(?: on)?|Publication date|Date published|Posted(?: on)?|게시일|발행일|작성일)"
                        r"\s*[:：]?\s*(.+)$",
    }
    lines = _visible_markdown_lines(text)
    start = header_line + 1 if header_line is not None else 0
    seen = 0
    for raw_line in lines[start:start + 24]:
        line = raw_line.strip()
        if re.search(r"©|\bcopyright\b|^#{1,6}\s+(?:footer|related|references)\b", line, re.IGNORECASE):
            break
        if not line:
            continue
        line = _plain_markdown(line)
        seen += 1
        if header_line is not None and seen == 1 and _date(line) != "미표기":
            values["published_at"] = _date(line)
            provenance["published_at"] = f"{source} 기사 제목 바로 다음 날짜: {raw_line.strip()}"
            continue
        recognized = False
        for key, pattern in patterns.items():
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if not match:
                continue
            recognized = True
            if key in values:
                continue
            value = match.group(1).strip()
            if key == "published_at":
                value = _date(re.split(r"\s+[|•]\s+", value)[0].strip())
                if value == "미표기":
                    continue
            elif key == "author":
                value = re.split(r"\s+[|•]\s+", value)[0].strip()
                if re.fullmatch(r"TYPE|INDUSTR(?:Y|IES)|PRODUCTS?|DATE|TOPICS?|CATEGOR(?:Y|IES)|SOLUTIONS?",
                                value, flags=re.IGNORECASE):
                    continue
            if value:
                values[key] = value
                provenance[key] = f"{source}: {raw_line.strip()}"
        # Metadata ends when article prose or another section begins.
        if not recognized:
            break
    return values, provenance


def _markdown_title(text: str, hint: str = "") -> tuple[str, str, int | None]:
    lines = _visible_markdown_lines(text)
    candidates: list[tuple[str, str, int, int]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,3})\s+(.+?)\s*#*\s*$", line)
        if match:
            title = _plain_markdown(match.group(2))
            level = len(match.group(1))
            if not _generic_heading(title):
                candidates.append((title, f"Markdown H{level}: {line.strip()}", index, level))
        elif index + 1 < len(lines) and line.strip() and re.fullmatch(r"={3,}\s*", lines[index + 1]):
            title = _plain_markdown(line)
            if not _generic_heading(title):
                candidates.append((title, f"Markdown H1: {line.strip()}", index + 1, 1))
    prefix = re.sub(r"(?:\.{3}|…)\s*$", "", _plain_markdown(hint)).strip().casefold()
    if prefix and not _generic_heading(prefix):
        for title, origin, index, _ in candidates:
            if title.casefold().startswith(prefix):
                return title, origin, index
        # Keep the service title when no heading confirms its truncated prefix.
        return "", "", None
    for title, origin, index, level in candidates:
        following = next((line.strip() for line in lines[index + 1:index + 5] if line.strip()), "")
        header_context = (_date(following) != "미표기" or bool(re.match(
            r"^(?:By\s+|Author\s*:|Published\b|게시일|발행일)", following, re.IGNORECASE,
        )) or (len(following) > 120 and not following.startswith(("#", "*", "-", "["))))
        if level == 1 or (len(title) >= 30 and len(title.split()) >= 4 and header_context):
            return title, origin, index
    return "", "", None


def _extracted_page(url: str, text: str, max_chars: int, metadata: dict,
                    source: str, location: str) -> SourcePage:
    values: dict[str, str] = {}
    provenance: dict[str, str] = {}
    for key, fields in (("title", ("title",)), ("author", ("author",)), ("publisher", ("publisher",)),
                        ("published_at", ("published_date", "published_at", "datePublished"))):
        for field_name in fields:
            value = metadata.get(field_name)
            cleaned = _date(value) if key == "published_at" else _name(value)
            if cleaned and cleaned != "미표기":
                values[key] = cleaned
                provenance[key] = f"{source} metadata.{field_name}: {value}"
                break
    title, title_origin, header_line = _markdown_title(text, values.get("title", ""))
    if title and ("title" not in values or _generic_heading(values["title"])
                  or re.search(r"(?:\.{3}|…)\s*$", values["title"])):
        values["title"] = title
        provenance["title"] = f"{source} {title_origin}"
    line_values, line_provenance = _metadata_lines(text, f"{source} 명시 표기", header_line,
                                                  require_heading=True)
    for key, value in line_values.items():
        if key not in values:
            values[key] = value
            provenance[key] = line_provenance[key]
    return SourcePage(url=url, title=values.get("title", "미표기"), text=text[:max_chars],
                      publisher=values.get("publisher", "미표기"),
                      published_at=values.get("published_at", "미표기"), author=values.get("author", "미표기"),
                      location=location, metadata_provenance=provenance)


def _public_url(url: str) -> str:
    """Reject private IPs, unsafe schemes, credentials, and mixed DNS answers."""
    try:
        if not isinstance(url, str) or re.search(r"[\x00-\x20\x7f\\]", url):
            raise ValueError
        parts = urlsplit(url)
        if (parts.scheme not in ("https", "http") or not parts.hostname
                or parts.username is not None or parts.password is not None):
            raise ValueError
        host = parts.hostname
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if "%" in host:
            raise ValueError
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(
                host, port, type=socket.SOCK_STREAM,
            )]
        if not addresses or not all(address.is_global for address in addresses):
            raise ValueError
    except (ValueError, OSError):
        raise ProviderError("공개 HTTP(S) 주소만 수집할 수 있습니다.") from None
    return url


def _bounded_content(response: httpx.Response) -> bytes:
    try:
        declared = int(response.headers.get("content-length", "0"))
    except ValueError:
        declared = 0
    if declared > MAX_RESPONSE_BYTES:
        raise ProviderError("원문 크기가 수집 한도(2 MiB)를 초과했습니다.")
    content = bytearray()
    for chunk in response.iter_bytes():
        content.extend(chunk)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ProviderError("원문 크기가 수집 한도(2 MiB)를 초과했습니다.")
    return bytes(content)


def _html_page(url: str, html: str, max_chars: int) -> SourcePage:
    soup = BeautifulSoup(html, "html.parser")
    values: dict[str, str] = {}
    provenance: dict[str, str] = {}

    def put(key: str, value: object, origin: str) -> None:
        cleaned = _date(value) if key == "published_at" else _name(value)
        if key not in values and cleaned and cleaned != "미표기":
            values[key] = cleaned
            provenance[key] = f"{origin}: {value}"

    def meta(key: str, *names: str) -> None:
        for name in names:
            for attribute in ("property", "name", "itemprop"):
                item = soup.find("meta", attrs={attribute: name})
                if item:
                    put(key, item.get("content"), f"HTML meta[{attribute}={name}]")

    root = soup.find("article") or soup.find("main") or soup.body or soup
    heading = root.find("h1")
    if heading and not _generic_heading(heading.get_text(" ", strip=True)):
        put("title", heading.get_text(" ", strip=True), "HTML h1")
    meta("title", "og:title", "twitter:title")
    meta("author", "author", "citation_author", "dc.creator")
    meta("publisher", "publisher", "dc.publisher", "og:site_name")
    meta("published_at", "article:published_time", "datePublished", "pubdate", "publication_date", "dc.date")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            nodes = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue
        queue = list(nodes) if isinstance(nodes, list) else [nodes]
        for node in queue:
            if not isinstance(node, dict):
                continue
            if isinstance(node.get("@graph"), list):
                queue.extend(node["@graph"])
            if isinstance(node.get("mainEntity"), dict):
                queue.append(node["mainEntity"])
            types = node.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if not isinstance(types, list) or not any(kind in types for kind in (
                "Article", "NewsArticle", "BlogPosting", "TechArticle", "ScholarlyArticle", "Report", "WebPage",
            )):
                continue
            for key, field_name in (("title", "headline"), ("author", "author"),
                                    ("publisher", "publisher"), ("published_at", "datePublished")):
                put(key, node.get(field_name), f"JSON-LD {field_name}")
    if soup.title:
        put("title", soup.title.get_text(" ", strip=True), "HTML title")
    for item in root.select('[rel="author"], [itemprop="author"], .byline, .author-name'):
        raw = item.get_text(" ", strip=True)
        cleaned = re.sub(r"^(?:By|Written by|Author|작성자|저자)\s*[:：]?\s*", "", raw, flags=re.IGNORECASE)
        put("author", cleaned, f"HTML byline ({raw})")
    for timestamp in root.select('time[itemprop="datePublished"], time[pubdate]'):
        put("published_at", timestamp.get("datetime") or timestamp.get_text(" ", strip=True),
            "HTML time[datePublished/pubdate]")
    for item in soup.select("script, style, nav, footer, aside, noscript, template, form"):
        item.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = []
    for block in root.find_all(_BLOCKS):
        if block.find_parent(_BLOCKS) is None:
            text = block.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)
    text = "\n\n".join(paragraphs) or root.get_text(" ", strip=True)
    if not text.strip():
        raise ProviderError("수집한 페이지에 읽을 수 있는 본문이 없습니다.")
    header_line = next((index for index, line in enumerate(text.splitlines())
                        if line.strip() == values.get("title")), None)
    line_values, line_provenance = _metadata_lines(text, "HTML 명시 표기", header_line)
    for key, value in line_values.items():
        if key not in values:
            values[key] = value
            provenance[key] = line_provenance[key]
    truncated = len(text) > max_chars
    return SourcePage(url=url, title=values.get("title", "미표기"),
                      text=text[:max_chars], publisher=values.get("publisher", "미표기"),
                      published_at=values.get("published_at", "미표기"), author=values.get("author", "미표기"),
                      location=f"HTML 본문 발췌(최대 {max_chars}자)" if truncated else "HTML 본문",
                      metadata_provenance=provenance)


class TavilyWeb:
    def __init__(self, api_key: str, timeout: float = 20, max_chars: int = 12_000):
        if timeout <= 0 or max_chars <= 0:
            raise ValueError("시간과 본문 길이 한도는 양수여야 합니다.")
        self._api_key = api_key
        self._timeout = timeout
        self._max_chars = max_chars

    def search(self, query: str, max_results: int = 3) -> list[SearchHit]:
        if not self._api_key.strip():
            raise ProviderError("검색 API 키가 설정되지 않았습니다.")
        if not query.strip() or not 1 <= max_results <= 20:
            raise ProviderError("검색어와 결과 개수를 확인해 주세요.")
        try:
            with (
                httpx.Client(timeout=self._timeout, follow_redirects=False, trust_env=False) as client,
                client.stream("POST", "https://api.tavily.com/search",
                              headers={"Authorization": f"Bearer {self._api_key}"},
                              json={"query": query, "max_results": max_results,
                                    "search_depth": "basic", "topic": "general",
                                    "include_answer": False, "include_raw_content": False,
                                    "include_published_date": True}) as response,
            ):
                response.raise_for_status()
                body = json.loads(_bounded_content(response))
            if not isinstance(body, dict) or not isinstance(body.get("results"), list):
                raise ProviderError("검색 응답 형식이 올바르지 않습니다.")
            hits = []
            for item in body["results"]:
                if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                    continue
                hits.append(SearchHit(url=item["url"], title=str(item.get("title") or item["url"]),
                                      snippet=str(item.get("content") or "")[:4000],
                                      published_at=_date(item.get("published_date"))))
                if len(hits) >= max_results:
                    break
            return hits
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError):
            raise ProviderError("외부 검색 요청에 실패했습니다.") from None

    def fetch(self, url: str) -> SourcePage:
        target = url
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=False, trust_env=False,
                              headers={"User-Agent": "KV-Stakeholder-Research/0.1",
                                       "Accept": "text/html, text/plain, application/xhtml+xml"}) as client:
                for hop in range(MAX_REDIRECTS + 1):
                    _public_url(target)
                    with client.stream("GET", target) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            location = response.headers.get("location")
                            if not location or hop == MAX_REDIRECTS:
                                raise ProviderError("원문 리다이렉트 한도를 초과했거나 주소가 없습니다.")
                            target = urljoin(target, location)
                            continue
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                        if content_type not in ("text/html", "application/xhtml+xml", "text/plain"):
                            raise ProviderError("HTML·텍스트 원문만 지원합니다. PDF 등은 별도 추출이 필요합니다.")
                        content = _bounded_content(response)
                        if content.lstrip().startswith(b"%PDF"):
                            raise ProviderError("PDF 원문은 별도 추출이 필요합니다.")
                        encoding = response.encoding or "utf-8"
                        decoded = content.decode(encoding, errors="replace")
                        if content_type != "text/plain":
                            return _html_page(target, decoded, self._max_chars)
                        if not decoded.strip():
                            raise ProviderError("수집한 페이지에 읽을 수 있는 본문이 없습니다.")
                        return _extracted_page(target, decoded, self._max_chars, {}, "원문 텍스트",
                                               "텍스트 본문 발췌" if len(decoded) > self._max_chars
                                               else "텍스트 본문")
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, LookupError):
            raise ProviderError("외부 원문 수집에 실패했습니다.") from None
        raise ProviderError("외부 원문 수집에 실패했습니다.")


class TavilyExtractWeb(TavilyWeb):
    """Use Tavily's external extractor, with exactly one API request per fetch.

    The direct-fetch adapter remains available separately. There is no hidden
    direct-fetch fallback or retry, so graph fetch budgets count API calls.
    """

    def fetch(self, url: str) -> SourcePage:
        if not self._api_key.strip():
            raise ProviderError("원문 추출 API 키가 설정되지 않았습니다.")
        _public_url(url)
        try:
            with (
                httpx.Client(timeout=self._timeout, follow_redirects=False, trust_env=False) as client,
                client.stream("POST", "https://api.tavily.com/extract",
                              headers={"Authorization": f"Bearer {self._api_key}"},
                              json={"urls": [url], "extract_depth": "basic", "format": "markdown",
                                    "include_images": False}) as response,
            ):
                response.raise_for_status()
                body = json.loads(_bounded_content(response))
            results = body.get("results") if isinstance(body, dict) else None
            if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
                raise ProviderError("외부 추출 서비스가 읽을 수 있는 원문을 반환하지 않았습니다.")
            item = results[0]
            text = item.get("raw_content")
            if not isinstance(text, str) or not text.strip():
                raise ProviderError("외부 추출 서비스가 읽을 수 있는 원문을 반환하지 않았습니다.")
            target = item.get("url")
            _public_url(target)
            return _extracted_page(target, text, self._max_chars, item, "Tavily Extract",
                                   f"Tavily Extract 원문 발췌(최대 {self._max_chars}자)")
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError):
            raise ProviderError("외부 원문 추출 요청에 실패했습니다.") from None
