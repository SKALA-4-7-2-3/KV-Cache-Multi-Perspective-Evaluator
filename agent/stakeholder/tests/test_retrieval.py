"""Discovery must cover both technique families without spending on unrelated hits."""

import pytest

from stakeholder_agent.models import Technology
from stakeholder_agent.providers import SearchHit
from stakeholder_agent.retrieval import candidate_matches

SW = Technology("SW-01", "RDKV", "SW", "RDKV", "https://arxiv.org/abs/2605.08317v1")
HW = Technology("HW-01", "Photonic-CXL", "HW", "Photonic-CXL", "https://arxiv.org/abs/2607.27187v1")


@pytest.mark.parametrize("title,snippet", [
    ("Quantized KV Cache", "Memory savings and inference quality tradeoffs"),
    ("LLM inference memory", "Key-value cache compression requires deployment validation."),
    ("Serving long contexts", "KV-cache eviction policies affect retained context."),
    ("데이터센터 LLM 추론", "KV 캐시 양자화와 압축의 운영 부담"),
    ("키 값 캐시 제거", "운영자가 확인할 품질 조건"),
])
def test_sw_related_family_is_a_candidate(title, snippet):
    assert candidate_matches(SW, SearchHit("https://example.org/serving", title, snippet))


@pytest.mark.parametrize("title,snippet", [
    ("Browser cache compression", "Faster static web assets"),
    ("CPU cache eviction", "Hardware cache replacement policies"),
    ("LLM weight quantization", "Compressing model parameters"),
    ("KV cache tutorial", "The cache stores attention keys and values."),
    ("압축 파일 관리", "데이터센터 파일 저장과 브라우저 캐시 삭제"),
])
def test_sw_unrelated_or_non_method_hits_are_rejected(title, snippet):
    assert not candidate_matches(SW, SearchHit("https://example.org/unrelated", title, snippet))


@pytest.mark.parametrize("title,snippet", [
    ("CXL memory expansion for LLM inference", "Deployment bandwidth considerations"),
    ("KV cache offloading", "CXL memory enables larger external capacity."),
    ("Photonic memory pooling", "A fabric for AI inference servers"),
    ("CXL 메모리 풀링", "클라우드 LLM 추론 서비스 운영"),
    ("광학 메모리 확장", "언어 모델의 KV 캐시를 수용"),
])
def test_hw_related_family_is_a_candidate(title, snippet):
    assert candidate_matches(HW, SearchHit("https://example.org/memory", title, snippet))


@pytest.mark.parametrize("title,snippet", [
    ("CXL conversion training", "Marketing optimization courses"),
    ("Photonic sensor", "Detecting light in a laboratory"),
    ("CXL memory pooling", "Database storage benchmarking"),
    ("AI photonic computing", "Optical matrix multiplication"),
    ("LLM memory expansion", "A conventional host DRAM upgrade"),
])
def test_hw_unrelated_or_missing_context_hits_are_rejected(title, snippet):
    assert not candidate_matches(HW, SearchHit("https://example.org/unrelated", title, snippet))


@pytest.mark.parametrize("technology,title", [(SW, "RDKV release notes"), (HW, "Photonic CXL study")])
def test_explicit_identity_is_a_candidate(technology, title):
    assert candidate_matches(technology, SearchHit("https://example.org/discussion", title))


@pytest.mark.parametrize("url", [
    "https://arxiv.org/abs/2605.08317v2",
    "https://arxiv.org/pdf/2605.08317.pdf",
    "https://arxiv.org/html/2605.08317v1",
    "https://arxiv.org/abs/2605%2E08317",
    "https://paper-mirror.example/paper/2605.08317",
])
def test_input_paper_variants_are_not_external_candidates(url):
    assert not candidate_matches(SW, SearchHit(url, "RDKV KV cache compression"))


def test_longer_arxiv_number_is_not_the_input_paper():
    assert candidate_matches(SW, SearchHit("https://example.org/2605.083170", "RDKV review"))


def test_hardware_input_paper_is_excluded_too():
    assert not candidate_matches(HW, SearchHit("https://arxiv.org/pdf/2607.27187v3", "Photonic-CXL"))


def test_arbitrary_input_url_ignores_tracking_query():
    paper = Technology("SW-01", "ExampleMethod", "SW", "Method", "https://example.org/paper")
    assert not candidate_matches(paper, SearchHit("https://example.org/paper/?tracking=1", "ExampleMethod"))


def test_named_technology_does_not_match_an_unrelated_substring():
    assert not candidate_matches(SW, SearchHit("https://example.org/rdkvillage", "A village"))
