"""Balanced discovery of direct and related-family evidence for SW and HW.

Passing this filter only permits fetching a page. The original text must still
be audited before it can support a claim, including its direct/family scope.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

if TYPE_CHECKING:
    from .models import Technology
    from .providers import SearchHit


_ARXIV_ID = re.compile(r"(?<![\d.])\d{4}\.\d{4,5}(?!\d)")
_KV_CACHE = re.compile(r"\b(?:kv|key[\s_-]*value)[\s_-]*caches?\b|kv\s*캐시|키[\s-]*값\s*캐시")
_SW_METHOD = re.compile(r"\b(?:quanti[sz]\w*|compress\w*|evict\w*)\b|양자화|압축|삭제|제거")
_AI_CONTEXT = re.compile(r"\b(?:llms?|ai|inference|large[\s_-]+language[\s_-]+models?)\b|인공지능|추론|언어\s*모델")
_MEMORY = re.compile(r"\b(?:memory|dram|hbm)\b|메모리")
_MEMORY_OPERATION = re.compile(
    r"\b(?:expand\w*|expansion|extend\w*|extension|pool\w*|offload\w*|disaggregat\w*|tier\w*)\b"
    r"|확장|풀링|오프로딩|분리|계층"
)


def _normal(text: str) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", unquote(text).casefold()).split())


def _same_input_paper(technology: Technology, hit: SearchHit) -> bool:
    # arXiv abstract, HTML, PDF, version and mirror URLs identify the same paper.
    original_ids = set(_ARXIV_ID.findall(unquote(technology.url)))
    if original_ids.intersection(_ARXIV_ID.findall(unquote(hit.url))):
        return True
    original, candidate = urlsplit(technology.url), urlsplit(hit.url)
    return bool(original.netloc and original.path) and (
        original.netloc.casefold(), unquote(original.path).rstrip("/")
    ) == (candidate.netloc.casefold(), unquote(candidate.path).rstrip("/"))


def candidate_matches(technology: Technology, hit: SearchHit) -> bool:
    """Accept the named technology or a relevant family; reject unrelated acronyms."""
    if _same_input_paper(technology, hit):
        return False
    text = unquote(f"{hit.title} {hit.url} {hit.snippet}").casefold()
    normalized = f" {_normal(text)} "
    name = _normal(technology.name)
    if name and f" {name} " in normalized:
        return True
    # Paper titles may be used as technology names, so recognize their short names.
    if "rdkv" in name.split() and re.search(r"\brdkv\b", text):
        return True
    if "photonic cxl" in name and " photonic cxl " in normalized:
        return True
    return family_matches(technology.kind, text)


def discovery_candidate(technology: Technology, hit: SearchHit) -> bool:
    """Read search candidates before judging relevance; only omit the input paper."""
    return not _same_input_paper(technology, hit)


def family_matches(kind: str, text: str) -> bool:
    """Topic match only, not truth, source reputation or proof of paper adoption."""
    text = text.casefold()
    if kind.upper() == "SW":
        # KV cache itself supplies the model-serving context; ordinary browser,
        # CPU or database cache compression alone does not pass.
        return bool(_KV_CACHE.search(text) and _SW_METHOD.search(text))
    if kind.upper() == "HW":
        interconnect = re.search(r"\bcxl\b|\bphotonic\w*\b|광학|광자", text)
        return bool(interconnect and _MEMORY.search(text) and _MEMORY_OPERATION.search(text)
                    and (_KV_CACHE.search(text) or _AI_CONTEXT.search(text)))
    return False
