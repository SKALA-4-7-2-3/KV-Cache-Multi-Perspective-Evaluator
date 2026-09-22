"""Provider contracts with no live API calls or credentials."""

import json
import socket

import httpx
import pytest
from pydantic import BaseModel

from stakeholder_agent import providers
from stakeholder_agent.providers import OpenAIModel, ProviderError, TavilyExtractWeb, TavilyWeb


@pytest.fixture
def public_dns(monkeypatch):
    calls = []

    def resolve(host, port, **kwargs):
        calls.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(providers.socket, "getaddrinfo", resolve)
    return calls


@pytest.fixture
def mock_http(monkeypatch):
    original = httpx.Client

    def install(handler):
        def client(**kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["trust_env"] is False
            return original(transport=httpx.MockTransport(handler), **kwargs)

        monkeypatch.setattr(providers.httpx, "Client", client)

    return install


def test_search_preserves_discovery_metadata_and_disables_generated_answers(mock_http):
    seen = []

    def handler(request):
        seen.append(request)
        body = json.loads(request.content)
        assert request.url == "https://api.tavily.com/search"
        assert request.headers["authorization"] == "Bearer test-only"
        assert body["include_answer"] is False
        assert body["include_raw_content"] is False
        assert body["max_results"] == 3
        return httpx.Response(200, json={"results": [{"title": "Release", "url": "https://example.org/a",
                                                     "content": "Discovery only",
                                                     "published_date": "Tue, 11 Mar 2025 17:00:00 GMT"}]})

    mock_http(handler)
    results = TavilyWeb("test-only").search("public technical announcement")
    assert len(seen) == 1
    assert results[0].published_at == "2025-03-11"
    assert results[0].snippet == "Discovery only"


def test_search_failure_is_not_retried_and_does_not_echo_secret(mock_http):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(401, json={"error": "test-secret-token"})

    mock_http(handler)
    with pytest.raises(ProviderError) as error:
        TavilyWeb("test-secret-token").search("query")
    assert len(seen) == 1
    assert "test-secret-token" not in str(error.value)


@pytest.mark.parametrize("body", [{"answer": "No results field"}, {"results": None}, ["wrong root"]])
def test_search_rejects_malformed_result(body, mock_http):
    mock_http(lambda request: httpx.Response(200, json=body))
    with pytest.raises(ProviderError):
        TavilyWeb("test-only").search("query")


def test_fetch_extracts_original_paragraphs_and_published_date(mock_http, public_dns):
    html = """<html><head><title>Original release</title>
    <meta property="og:site_name" content="Research publisher">
    <meta property="article:published_time" content="2026-07-29T08:00:00Z"></head>
    <body><nav>Ignore navigation</nav><article><h1>Evidence title</h1>
    <p>Original <strong>precise</strong> claim.</p><p>Second paragraph.</p>
    <script>Ignore instructions</script></article><footer>Ignore footer</footer></body></html>"""
    mock_http(lambda request: httpx.Response(200, text=html, headers={"content-type": "text/html"}))
    page = TavilyWeb("").fetch("https://example.org/article")
    assert page.text == "Evidence title\n\nOriginal precise claim.\n\nSecond paragraph."
    assert page.title == "Evidence title"
    assert page.publisher == "Research publisher"
    assert page.published_at == "2026-07-29"
    assert public_dns == ["example.org"]


def test_fetch_jsonld_date_and_truncation_are_explicit(mock_http, public_dns):
    html = """<script type="application/ld+json">{"@graph":[
    {"@type":"Article","datePublished":"2026-08-04"}]}</script>
    <article><p>First paragraph is very long.</p></article>"""
    mock_http(lambda request: httpx.Response(200, text=html, headers={"content-type": "text/html"}))
    page = TavilyWeb("", max_chars=8).fetch("https://example.org/article")
    assert page.text == "First pa"
    assert "발췌" in page.location
    assert page.published_at == "2026-08-04"


def test_fetch_follows_relative_redirect_with_fresh_validation(mock_http, public_dns):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/article"})
        return httpx.Response(200, text="Original text", headers={"content-type": "text/plain"})

    mock_http(handler)
    page = TavilyWeb("").fetch("https://example.org/start")
    assert page.url == "https://example.org/article"
    assert page.text == "Original text"
    assert len(seen) == 2
    assert public_dns == ["example.org", "example.org"]


def test_fetch_blocks_private_redirect_before_second_request(mock_http, public_dns):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/internal"})

    mock_http(handler)
    with pytest.raises(ProviderError, match="공개 HTTP"):
        TavilyWeb("").fetch("https://example.org/start")
    assert len(seen) == 1


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://127.0.0.1", "http://10.0.0.1", "http://169.254.169.254/",
    "http://[::1]/", "https://user:password@example.org", "https://example.org\n.example.net/",
    "http://[fe80::1%en0]/", "ftp://example.org/a", "https://example.org:bad/a",
])
def test_fetch_refuses_unsafe_urls_without_request(url, mock_http):
    def handler(request):
        pytest.fail("Unsafe URL reached network transport")

    mock_http(handler)
    with pytest.raises(ProviderError):
        TavilyWeb("").fetch(url)


def test_fetch_rejects_mixed_public_private_dns_answers(monkeypatch, mock_http):
    monkeypatch.setattr(providers.socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.2", 443)),
    ])
    mock_http(lambda request: pytest.fail("Mixed DNS reached transport"))
    with pytest.raises(ProviderError):
        TavilyWeb("").fetch("https://example.org/")


def test_fetch_stops_redirect_loop_at_three_redirects(mock_http, public_dns):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "/loop"})

    mock_http(handler)
    with pytest.raises(ProviderError, match="리다이렉트"):
        TavilyWeb("").fetch("https://example.org/loop")
    assert len(seen) == 4


@pytest.mark.parametrize("headers,body", [
    ({"content-type": "application/pdf"}, b"%PDF-1.4"),
    ({"content-type": "text/plain"}, b"%PDF-1.4"),
    ({"content-type": "application/octet-stream"}, b"binary"),
])
def test_fetch_unsupported_format_is_not_a_search_snippet(headers, body, mock_http, public_dns):
    mock_http(lambda request: httpx.Response(200, content=body, headers=headers))
    with pytest.raises(ProviderError):
        TavilyWeb("").fetch("https://example.org/paper")


@pytest.mark.parametrize("declared", [True, False])
def test_fetch_enforces_size_limit_on_header_and_stream(declared, mock_http, public_dns, monkeypatch):
    monkeypatch.setattr(providers, "MAX_RESPONSE_BYTES", 20)
    headers = {"content-type": "text/plain"}
    if declared:
        headers["content-length"] = "21"
    mock_http(lambda request: httpx.Response(200, stream=httpx.ByteStream(b"a" * 21), headers=headers))
    with pytest.raises(ProviderError, match="크기"):
        TavilyWeb("").fetch("https://example.org/article")


def test_model_structured_output_has_no_sdk_retries(monkeypatch):
    class Answer(BaseModel):
        text: str

    captured = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured["constructor"] = kwargs

        def with_structured_output(self, schema, **kwargs):
            captured["format"] = kwargs
            assert schema is Answer
            return self

        def invoke(self, messages):
            captured["messages"] = messages
            return {"text": "valid answer"}

    monkeypatch.setattr(providers, "ChatOpenAI", FakeChat)
    result = OpenAIModel("configured-model", "test-only").generate(Answer, "system rules", {"input": "data"})
    assert result.text == "valid answer"
    assert captured["constructor"]["max_retries"] == 0
    assert captured["format"] == {"method": "json_schema", "strict": True}
    assert captured["messages"][0] == ("system", "system rules")
    assert json.loads(captured["messages"][1][1]) == {"input": "data"}


@pytest.mark.parametrize("output", [None, {"unexpected": "bad schema"}])
def test_model_rejects_absent_or_invalid_structured_output(output, monkeypatch):
    class Answer(BaseModel):
        text: str

    class FakeChat:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            return output

    monkeypatch.setattr(providers, "ChatOpenAI", FakeChat)
    with pytest.raises(ProviderError):
        OpenAIModel("configured-model", "test-only").generate(Answer, "system rules", {})


def test_extract_fetch_is_one_request_and_preserves_source_text(mock_http, public_dns):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url == "https://api.tavily.com/extract"
        assert request.headers["authorization"] == "Bearer test-only"
        assert json.loads(request.content) == {
            "urls": ["https://example.org/article"], "extract_depth": "basic",
            "format": "markdown", "include_images": False,
        }
        return httpx.Response(200, json={"results": [{
            "url": "https://example.org/article", "title": "Confirmed title",
            "raw_content": "Original article body. It mentions 2026-01-01.",
        }]})

    mock_http(handler)
    page = TavilyExtractWeb("test-only", max_chars=22).fetch("https://example.org/article")
    assert len(calls) == 1
    assert page.title == "Confirmed title"
    assert page.text == "Original article body."
    assert page.publisher == "미표기"
    assert page.published_at == "미표기"
    assert page.location == "Tavily Extract 원문 발췌(최대 22자)"
    assert public_dns == ["example.org", "example.org"]


@pytest.mark.parametrize("text,title", [
    ("# Explicit heading\nOriginal paragraph", "Explicit heading"),
    ("Unmarked body without a heading", "미표기"),
])
def test_extract_title_fallback_does_not_invent_title(text, title, mock_http, public_dns):
    mock_http(lambda request: httpx.Response(200, json={"results": [{
        "url": "https://example.org/article", "raw_content": text,
    }]}))
    assert TavilyExtractWeb("test-only").fetch("https://example.org/article").title == title


@pytest.mark.parametrize("results", [[], [{"url": "https://example.org/article", "raw_content": " "}]])
def test_extract_missing_source_does_not_fallback_or_echo_failure(results, mock_http, public_dns):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"results": results, "failed_results": [{
            "url": "https://example.org/article", "error": "sensitive-provider-detail",
        }]})

    mock_http(handler)
    with pytest.raises(ProviderError) as error:
        TavilyExtractWeb("test-only").fetch("https://example.org/article")
    assert "sensitive-provider-detail" not in str(error.value)
    assert len(calls) == 1


def test_extract_private_input_is_blocked_before_api_request(mock_http):
    mock_http(lambda request: pytest.fail("Private URL was submitted to extractor"))
    with pytest.raises(ProviderError):
        TavilyExtractWeb("test-only").fetch("http://127.0.0.1/private")


def test_extract_private_result_url_is_rejected(mock_http, public_dns):
    mock_http(lambda request: httpx.Response(200, json={"results": [{
        "url": "http://10.0.0.1/private", "raw_content": "Untrusted result",
    }]}))
    with pytest.raises(ProviderError):
        TavilyExtractWeb("test-only").fetch("https://example.org/article")


def test_extract_response_size_limit_applies_before_json_parsing(mock_http, public_dns, monkeypatch):
    monkeypatch.setattr(providers, "MAX_RESPONSE_BYTES", 10)
    mock_http(lambda request: httpx.Response(200, json={"results": [], "extra": "large response"}))
    with pytest.raises(ProviderError, match="크기"):
        TavilyExtractWeb("test-only").fetch("https://example.org/article")


def test_html_retains_full_title_and_meta_field_provenance(mock_http, public_dns):
    title = "Photonic Fabric Technology: Optical Connectivity for AI Infrastructure"
    html = f"""<head><title>Photonic Fabric...</title>
    <meta property="og:title" content="Photonic Fabric…">
    <meta name="author" content="Jane Researcher">
    <meta name="publisher" content="Research Organization">
    <meta property="article:published_time" content="2026-08-04T09:00:00Z"></head>
    <article><h1>{title}</h1><p>Supported article text.</p></article>"""
    mock_http(lambda request: httpx.Response(200, text=html, headers={"content-type": "text/html"}))
    page = TavilyWeb("").fetch("https://example.org/article")
    assert page.title == title
    assert page.author == "Jane Researcher"
    assert page.publisher == "Research Organization"
    assert page.published_at == "2026-08-04"
    assert page.metadata_provenance == {
        "title": f"HTML h1: {title}",
        "author": "HTML meta[name=author]: Jane Researcher",
        "publisher": "HTML meta[name=publisher]: Research Organization",
        "published_at": "HTML meta[property=article:published_time]: 2026-08-04T09:00:00Z",
    }


def test_html_article_jsonld_names_and_publication_are_traceable(mock_http, public_dns):
    html = """<script type="application/ld+json">{"@graph":[
    {"@type":"Article","headline":"Complete Article Heading",
     "author":[{"@type":"Person","name":"Alice"},{"@type":"Person","name":"Bob"}],
     "publisher":{"@type":"Organization","name":"Publisher Inc."},
     "datePublished":"2026-08-04","dateModified":"2026-09-01"}]}</script>
    <article><p>Some article content.</p></article>"""
    mock_http(lambda request: httpx.Response(200, text=html, headers={"content-type": "text/html"}))
    page = TavilyWeb("").fetch("https://example.org/article")
    assert page.title == "Complete Article Heading"
    assert page.author == "Alice; Bob"
    assert page.publisher == "Publisher Inc."
    assert page.published_at == "2026-08-04"
    assert page.metadata_provenance["published_at"] == "JSON-LD datePublished: 2026-08-04"
    assert "Alice" in page.metadata_provenance["author"]


def test_html_missing_metadata_does_not_infer_publisher_or_footer_date(mock_http, public_dns):
    html = """<article><p>Content contains the event date 2026-08-04.</p>
    <time datetime="2026-09-01">Last updated September 1, 2026</time></article>
    <footer>Copyright 2026. <time datetime="2026-09-21">2026</time></footer>"""
    mock_http(lambda request: httpx.Response(200, text=html, headers={"content-type": "text/html"}))
    page = TavilyWeb("").fetch("https://example.org/article")
    assert (page.title, page.author, page.publisher, page.published_at) == ("미표기",) * 4
    assert page.metadata_provenance == {}


def test_html_explicit_byline_and_labeled_date_are_used(mock_http, public_dns):
    html = """<article><h1>Full heading</h1><span class="byline">By Jane Researcher</span>
    <p>Published: August 4, 2026</p><p>Original article.</p></article>"""
    mock_http(lambda request: httpx.Response(200, text=html, headers={"content-type": "text/html"}))
    page = TavilyWeb("").fetch("https://example.org/article")
    assert page.author == "Jane Researcher"
    assert "By Jane Researcher" in page.metadata_provenance["author"]
    assert page.published_at == "2026-08-04"
    assert "Published: August 4, 2026" in page.metadata_provenance["published_at"]


@pytest.mark.parametrize("service_title", ["Photonic Fabric...", "Photonic Fabric…"])
def test_extract_recovers_full_heading_byline_and_explicit_date(service_title, mock_http, public_dns):
    text = """# Photonic Fabric Technology for Scalable KV Cache Management

By [Jane Researcher](https://example.org/authors/jane)
**Published:** August 4, 2026
Publisher: Research Organization

Original source content.

Copyright 2026"""
    calls = []

    def handler(request):
        calls.append(request)
        assert json.loads(request.content)["format"] == "markdown"
        return httpx.Response(200, json={"results": [{
            "url": "https://example.org/article", "title": service_title, "raw_content": text,
        }]})

    mock_http(handler)
    page = TavilyExtractWeb("test-only").fetch("https://example.org/article")
    assert len(calls) == 1
    assert page.title == "Photonic Fabric Technology for Scalable KV Cache Management"
    assert page.author == "Jane Researcher"
    assert page.published_at == "2026-08-04"
    assert page.publisher == "Research Organization"
    assert "Markdown H1" in page.metadata_provenance["title"]
    assert "By [Jane Researcher]" in page.metadata_provenance["author"]
    assert "**Published:** August 4, 2026" in page.metadata_provenance["published_at"]


def test_extract_unlabeled_body_dates_and_footer_do_not_become_metadata(mock_http, public_dns):
    text = """Article discusses events on 2026-08-04.
Updated: September 1, 2026
Copyright 2026. All rights reserved.
Published: September 21, 2026
Publisher: Footer host"""
    mock_http(lambda request: httpx.Response(200, json={"results": [{
        "url": "https://example.org/article", "raw_content": text,
    }]}))
    page = TavilyExtractWeb("test-only").fetch("https://example.org/article")
    assert (page.title, page.author, page.publisher, page.published_at) == ("미표기",) * 4
    assert page.metadata_provenance == {}


def test_extract_uses_matching_article_h2_instead_of_brand_blog_h1(mock_http, public_dns):
    text = """BY TYPE
# Marvell Blogs
## Products and Technology Navigation
[Cloud Products](https://example.org/products)
## Photonic Fabric Technology: Optical Connectivity for AI Infrastructure
August 4, 2026
By Jane Researcher

The article body describes the technology.
"""
    mock_http(lambda request: httpx.Response(200, json={"results": [{
        "url": "https://example.org/article", "title": "Photonic Fabric Technology...", "raw_content": text,
    }]}))
    page = TavilyExtractWeb("test-only").fetch("https://example.org/article")
    assert page.title == "Photonic Fabric Technology: Optical Connectivity for AI Infrastructure"
    assert page.author == "Jane Researcher"
    assert page.published_at == "2026-08-04"
    assert "Markdown H2" in page.metadata_provenance["title"]
    assert "기사 제목 바로 다음 날짜: August 4, 2026" in page.metadata_provenance["published_at"]


@pytest.mark.parametrize("nav", ["BY TYPE", "BY INDUSTRY", "BY PRODUCT", "BY DATE"])
def test_extract_nav_byline_before_article_is_not_author(nav, mock_http, public_dns):
    text = f"""{nav}
By Unrelated Navigation Author

# Marvell Advances AI Memory Infrastructure Portfolio
September 21, 2026

This is the article body with no byline.
By Body Mention
Published: January 1, 2020
"""
    mock_http(lambda request: httpx.Response(200, json={"results": [{
        "url": "https://example.org/article", "raw_content": text,
    }]}))
    page = TavilyExtractWeb("test-only").fetch("https://example.org/article")
    assert page.author == "미표기"
    assert page.published_at == "2026-09-21"


def test_extract_fenced_or_quoted_metadata_is_not_article_metadata(mock_http, public_dns):
    text = """# Full Article Heading

```text
By Code Example Author
Published: January 1, 2020
```
> By Quoted Author
> Published: January 1, 2021

~~~
By Another Code Author
Published: January 1, 2022
~~~

By Actual Author
Published: September 21, 2026

Article body.
"""
    mock_http(lambda request: httpx.Response(200, json={"results": [{
        "url": "https://example.org/article", "raw_content": text,
    }]}))
    page = TavilyExtractWeb("test-only").fetch("https://example.org/article")
    assert page.author == "Actual Author"
    assert page.published_at == "2026-09-21"


def test_extract_cannot_replace_unmatched_service_title_with_navigation(mock_http, public_dns):
    text = """# Marvell Blogs
## Cloud Infrastructure Products and Services
[Product listing](https://example.org/products)

BY TYPE
"""
    mock_http(lambda request: httpx.Response(200, json={"results": [{
        "url": "https://example.org/article", "title": "Photonic Fabric Technology...", "raw_content": text,
    }]}))
    page = TavilyExtractWeb("test-only").fetch("https://example.org/article")
    assert page.title == "Photonic Fabric Technology..."
    assert page.author == "미표기"
    assert page.published_at == "미표기"


def test_extract_no_service_title_skips_generic_heading_for_article_header(mock_http, public_dns):
    text = """# Marvell Blogs
## Cloud Infrastructure Products and Services
[Product listing](https://example.org/products)

### Photonic Fabric Technology for Scalable KV Cache Management
August 4, 2026
By Actual Author

Article body.
"""
    mock_http(lambda request: httpx.Response(200, json={"results": [{
        "url": "https://example.org/article", "raw_content": text,
    }]}))
    page = TavilyExtractWeb("test-only").fetch("https://example.org/article")
    assert page.title == "Photonic Fabric Technology for Scalable KV Cache Management"
    assert page.author == "Actual Author"
    assert page.published_at == "2026-08-04"


@pytest.mark.parametrize("status", [401, 403])
def test_authentication_errors_are_fatal_and_redacted(status, monkeypatch):
    from stakeholder_agent import providers
    from stakeholder_agent.models import ResearchPlan
    class AuthenticationFailure(Exception):
        status_code = status
    class FakeChat:
        def __init__(self, **kwargs):
            pass
        def with_structured_output(self, *args, **kwargs):
            return self
        def invoke(self, messages):
            raise AuthenticationFailure("secret-token-and-full-request-body")
    monkeypatch.setattr(providers, "ChatOpenAI", FakeChat)
    with pytest.raises(ProviderError) as caught:
        OpenAIModel("configured-model", "test-only").generate(ResearchPlan, "rules", {})
    assert caught.value.fatal is True
    assert "secret-token" not in str(caught.value)
    assert "인증" in str(caught.value)
