"""Network-free integration tests for evidence integrity and bounded execution."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest

from stakeholder_agent.config import AgentConfig
from stakeholder_agent.legacy import run_detailed, run_stakeholder
from stakeholder_agent.models import (
    OUTPUT_SECTIONS,
    Assessment,
    Claim,
    Insight,
    ResearchPlan,
    Review,
    SearchQuestion,
    Support,
    WebSourceReview,
)
from stakeholder_agent.providers import SearchHit, SourcePage

SW_QUOTE = "제거와 양자화를 함께 최적화하고 prefill 뒤 비트 할당을 적용한다."
HW_QUOTE = "Photonic-CXL 메모리 어플라이언스를 제안하고 구조·서빙 효과를 에뮬레이션과 시뮬레이션으로 보고한다."


@pytest.fixture
def input_md():
    package = Path(__file__).resolve().parents[1]
    return (package / "tests" / "fixtures" / "legacy-input.md").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    """An accidental default-provider call must fail, never use real credentials."""
    def blocked(*args, **kwargs):
        raise AssertionError("Unit tests must not make HTTP requests")

    monkeypatch.setattr("httpx.Client.request", blocked)
    monkeypatch.setattr("httpx.Client.stream", blocked)


def question(index=0, tech_id="SW-01"):
    return SearchQuestion(tech_id=tech_id, group="operator",
                          query=f"RDKV Photonic-CXL 운영 근거 {index}",
                          reason="실제 운영자의 근거를 확인한다.")


def claim(*, evidence_id="E-SW-001", quote=SW_QUOTE, tech_id="SW-01",
          text="논문은 prefill 이후 비트 할당을 적용한다고 보고한다", kind="paper_report"):
    return Claim(tech_id=tech_id, group="operator", aspect="benefit", kind=kind,
                 text=text, condition="입력 논문 요약의 범위에 한정한다.",
                 actor="Example vendor" if kind == "statement" else "",
                 actor_relationship="provider" if kind == "statement" else "unspecified",
                 source_scope="direct", supports=[Support(evidence_id=evidence_id, quote=quote)])


def assessment(claims=None, *, summary=None, implications=None):
    return Assessment(claims=claims or [], summary=summary or [], implications=implications or [],
                      limitations=["실제 고객의 도입 여부는 확인하지 못했다."],
                      follow_up=["고객의 실제 도입 발표를 확인한다."])


class FakeModel:
    def __init__(self, *, plan=None, draft=None, review=None):
        self.plan = plan or ResearchPlan(questions=[])
        self.draft = draft or assessment()
        self.review = review or Review(rejected_claim_indices=[], issues=[], queries=[])
        self.calls = []

    def generate(self, schema, system, payload):
        self.calls.append((schema.__name__, deepcopy(payload)))
        responses = {ResearchPlan: self.plan, Assessment: self.draft, Review: self.review}
        assert schema in responses, f"Unexpected structured-model contract: {schema}"
        return responses[schema].model_copy(deep=True)


class FakeWeb:
    def __init__(self, *, empty=True):
        self.empty = empty
        self.search_calls = []
        self.fetch_calls = []

    def search(self, query, max_results=3):
        self.search_calls.append((query, max_results))
        if self.empty:
            return []
        index = len(self.search_calls)
        return [SearchHit(url=f"https://example.org/source/{index}/{hit}",
                          title=f"RDKV Photonic-CXL source {index}/{hit}",
                          snippet="원문을 조회하기 전에는 근거로 사용할 수 없는 검색 요약")
                for hit in range(max_results)]

    def fetch(self, url):
        self.fetch_calls.append(url)
        return SourcePage(url=url, title="RDKV Photonic-CXL 운영 자료",
                          text="RDKV and Photonic-CXL require deployment validation. "
                               "The developer reports a research implementation.",
                          publisher="Example research lab", published_at="2026-09-01")


def config(**overrides):
    return AgentConfig(**{"search_limit": 2, "fetch_limit": 2,
                          "llm_limit": 5, "repair_limit": 0, **overrides})


@pytest.mark.parametrize("invalid", ["", "평가해 주세요", "# 입력\n\n## 기술 목록\n\nSW만 있습니다."])
def test_invalid_input_uses_no_model_or_search(invalid):
    model, web = FakeModel(), FakeWeb(empty=False)
    state = run_detailed(invalid, config=config(), model=model, web=web)
    assert model.calls == []
    assert web.search_calls == []
    assert web.fetch_calls == []
    assert state.get("parsed") is None
    assert isinstance(state["output_md"], str)
    assert state["output_md"].strip()
    assert state["errors"]


def test_public_function_returns_markdown_with_all_sections_and_reference_last(input_md):
    model = FakeModel(draft=assessment([claim()]))
    output = run_stakeholder(input_md, config=config(), model=model, web=FakeWeb())
    assert isinstance(output, str)
    headings = re.findall(r"^## (.+)$", output, re.MULTILINE)
    assert headings == OUTPUT_SECTIONS
    assert headings[-1] == "REFERENCE"
    reference = output.split("## REFERENCE", 1)[1]
    assert "E-SW-001" in reference
    assert "E-HW-001" not in reference, "Unused input sources must not become references"


def test_source_local_quote_key_is_resolved_and_validated_through_the_real_graph(input_md):
    hw_claim = claim(evidence_id="E-HW-001", tech_id="HW-01", quote="Q001",
                     text="하드웨어논문에서보고된공유메모리구조")
    model = FakeModel(draft=assessment([hw_claim]))
    state = run_detailed(input_md, config=config(), model=model, web=FakeWeb())
    analysis_payload = next(payload for schema, payload in model.calls if schema == "Assessment")
    offered = next(item for item in analysis_payload["evidence"] if item["id"] == "E-HW-001")
    expected_quote = offered["quote_options"]["Q001"]
    assert len(expected_quote) >= 12
    assert expected_quote in state["evidence"]["E-HW-001"].excerpt
    assert state["draft"].claims[0].supports[0].quote == expected_quote
    review_payload = next(payload for schema, payload in model.calls if schema == "Review")
    assert review_payload["draft"]["claims"][0]["supports"][0]["quote"] == expected_quote
    assert state["rejected"] == []
    assert hw_claim.text in state["output_md"]
    assert "### E-HW-001" in state["output_md"].split("## REFERENCE", 1)[1]


@pytest.mark.parametrize("broken", [
    claim(evidence_id="E-NOT-FOUND", text="잘못된근거ID주장"),
    claim(evidence_id="E-HW-001", quote=HW_QUOTE, text="다른기술근거주장"),
    claim(quote="실제 클라우드 고객 모두가 이미 도입했다.", text="원문에없는발췌주장"),
    claim(quote="", text="빈발췌주장"),
])
def test_unsupported_claims_and_their_summaries_never_reach_report(input_md, broken):
    draft = assessment([claim(), broken],
                       summary=[Insight(text="유효한요약표식", claim_indices=[0]),
                                Insight(text="잘못된요약표식", claim_indices=[1])],
                       implications=[Insight(text="잘못된시사점표식", claim_indices=[1])])
    state = run_detailed(input_md, config=config(), model=FakeModel(draft=draft), web=FakeWeb())
    output = state["output_md"]
    assert claim().text in output
    assert broken.text not in output
    assert "잘못된요약표식" not in output
    assert "잘못된시사점표식" not in output
    assert "유효한요약표식" in output


def test_reviewer_rejection_also_removes_dependent_summary_and_implication(input_md):
    rejected = claim(text="리뷰에서제외할주장")
    kept = claim(text="리뷰에서유지할주장")
    draft = assessment([rejected, kept],
                       summary=[Insight(text="제외할요약", claim_indices=[0]),
                                Insight(text="유지할요약", claim_indices=[1]),
                                Insight(text="부분근거거절시제외할요약", claim_indices=[0, 1])],
                       implications=[Insight(text="제외할시사점", claim_indices=[0]),
                                     Insight(text="유지할시사점", claim_indices=[1])])
    model = FakeModel(draft=draft,
                      review=Review(rejected_claim_indices=[0], issues=["의미적 근거 부족"], queries=[]))
    output = run_stakeholder(input_md, config=config(), model=model, web=FakeWeb())
    assert rejected.text not in output
    assert "제외할요약" not in output
    assert "제외할시사점" not in output
    assert "부분근거거절시제외할요약" not in output
    assert kept.text in output
    assert "유지할요약" in output
    assert "유지할시사점" in output


def test_semantic_review_explicitly_identifies_claims_surviving_mechanical_checks(input_md):
    draft = assessment([claim(text="첫번째후보"), claim(evidence_id="MISSING", text="기계검사거절"),
                        claim(text="두번째후보")])
    model = FakeModel(draft=draft)
    state = run_detailed(input_md, config=config(), model=model, web=FakeWeb())
    payload = next(payload for schema, payload in model.calls if schema == "Review")
    assert payload["review_candidate_indices"] == [0, 2]
    assert [item["claim_index"] for item in payload["draft"]["claims"]] == [0, 1, 2]
    assert 1 in state["rejected"]


def test_no_external_results_is_partial_and_not_negative_stakeholder_opinion(input_md):
    model = FakeModel(plan=ResearchPlan(questions=[question()]), draft=assessment([claim()]))
    state = run_detailed(input_md, config=config(), model=model, web=FakeWeb())
    assert state["status"] == "partial"
    assert "미확인" in state["output_md"]
    assert claim().text in state["output_md"]


@pytest.mark.parametrize("kind", ["statement", "inference"])
def test_paper_findings_cannot_be_reported_as_an_operators_actual_reaction(input_md, kind):
    reaction = claim(text="운영자들이이기술을공식적으로지지한다", kind=kind)
    reaction = reaction.model_copy(update={"aspect": "reaction"})
    draft = assessment([reaction], summary=[Insight(text="실제지지요약", claim_indices=[0])])
    output = run_stakeholder(input_md, config=config(), model=FakeModel(draft=draft), web=FakeWeb())
    assert reaction.text not in output
    assert "실제지지요약" not in output


@pytest.mark.parametrize(("scope", "kind", "allowed"), [
    ("context", "inference", False),
    ("family", "inference", False),
    ("family", "statement", True),
])
def test_generic_cxl_source_does_not_establish_photonic_cxl_adoption_conditions(input_md, scope, kind, allowed):
    source_url = "https://example.org/cxl-4-0-overview"
    source_text = "공급자는 CXL 4.0 기술 계열의 메모리 공유 기능을 소개한다."
    claim_text = ("공급자는 관련 CXL 기술 계열의 메모리 공유 기능을 소개한다" if allowed
                  else "Photonic-CXL 도입에는 CXL 4.0 장비가 반드시 필요하다")

    class GenericCxlWeb(FakeWeb):
        def search(self, query, max_results=3):
            self.search_calls.append((query, max_results))
            if "Photonic-CXL" not in query:
                return []
            return [SearchHit(url=source_url, title="CXL 4.0 기술 개요",
                              snippet="LLM inference memory pooling architecture")]

        def fetch(self, url):
            self.fetch_calls.append(url)
            return SourcePage(url=url, title="CXL 4.0 기술 개요", text=source_text,
                              publisher="Example supplier", published_at="2026-09-01")

    class ScopedModel(FakeModel):
        def generate(self, schema, system, payload):
            if schema is Assessment:
                source = next(item for item in payload["evidence"] if item["url"] == source_url)
                scoped_claim = Claim(
                    tech_id="HW-01", group="supplier" if allowed else "operator",
                    aspect="reaction" if allowed else "adoption_condition", kind=kind,
                    actor="Example supplier" if kind == "statement" else "",
                    actor_relationship="provider" if kind == "statement" else "unspecified",
                    text=claim_text, condition="자료가 다루는 기술 범위에 한정한다",
                    source_scope=scope, supports=[Support(evidence_id=source["id"], quote=source_text)],
                )
                self.draft = assessment([scoped_claim],
                                        summary=[Insight(text="계열자료요약표식", claim_indices=[0])],
                                        implications=[Insight(text="계열자료시사점표식", claim_indices=[0])])
                self.draft.source_reviews = [WebSourceReview(
                    evidence_id=source["id"], document_type="supplier_publication",
                    perspective="interested_party", relevance="family", evidence_basis="attributed_statement",
                    decision="limited", reasons=["공급자의 기술 계열 설명"], limitations=[],
                    basis_quotes=[source_text],
                )]
            return super().generate(schema, system, payload)

    state = run_detailed(input_md, config=config(), model=ScopedModel(), web=GenericCxlWeb())
    output = state["output_md"]
    source_id = next(key for key, source in state["evidence"].items() if source.url == source_url)
    # The literal quote and HW association are valid, so exclusion must follow the scope rule.
    assert "HW-01" in state["evidence"][source_id].tech_ids
    assert state["draft"].claims[0].supports[0].quote == source_text
    assert (0 not in state["rejected"]) is allowed
    for fragment in [claim_text, "계열자료요약표식", "계열자료시사점표식"]:
        assert (fragment in output.replace("\\", "")) is allowed
    assert (source_id in output.split("## REFERENCE", 1)[1]) is allowed


@pytest.mark.parametrize(("kind", "include_review", "allowed"), [
    ("inference", True, False), ("statement", True, True), ("statement", False, False),
])
def test_graph_enforces_vendor_source_limits_and_blocks_unaudited_web_claims(input_md, kind,
                                                                         include_review, allowed):
    vendor_url = "https://vendor.example.org/rdkv-research"
    vendor_text = "The vendor reports an RDKV research implementation in this announcement."
    claim_text = "공급자에게귀속한연구구현발언" if kind == "statement" else "운영현장에서독립적으로검증된효과"

    class VendorWeb(FakeWeb):
        def search(self, query, max_results=3):
            self.search_calls.append((query, max_results))
            return ([SearchHit(url=vendor_url, title="RDKV research announcement")]
                    if "RDKV" in query else [])

        def fetch(self, url):
            self.fetch_calls.append(url)
            return SourcePage(url=url, title="RDKV research announcement", text=vendor_text,
                              publisher="Example vendor", published_at="2026-09-01")

    class VendorModel(FakeModel):
        def generate(self, schema, system, payload):
            if schema is Assessment:
                record = next(item for item in payload["evidence"] if item["url"] == vendor_url)
                vendor_claim = claim(evidence_id=record["id"], quote="Q001", text=claim_text,
                                     kind=kind).model_copy(update={"group": "supplier"})
                self.draft = assessment([vendor_claim],
                                        summary=[Insight(text="공급자자료요약표식", claim_indices=[0])])
                if include_review:
                    self.draft.source_reviews = [WebSourceReview(
                        evidence_id=record["id"], document_type="supplier_publication",
                        perspective="independent_author", relevance="direct", evidence_basis="methods_and_results",
                        decision="use", reasons=["공급자의 구현 발표"], limitations=[], basis_quotes=["Q001"],
                    )]
            return super().generate(schema, system, payload)

    state = run_detailed(input_md, config=config(), model=VendorModel(), web=VendorWeb())
    record = next(item for item in state["evidence"].values() if item.url == vendor_url)
    assert record.audit["decision"] == ("limited" if include_review else "hold")
    if include_review:
        assert record.audit["perspective"] == "interested_party"
    assert (0 not in state["rejected"]) is allowed
    assert (claim_text in state["output_md"]) is allowed
    assert ("공급자자료요약표식" in state["output_md"]) is allowed
    assert (record.id in state["output_md"].split("## REFERENCE", 1)[1]) is allowed


def test_unknown_claim_is_normalized_and_cannot_support_summary_or_implications(input_md):
    invented_text = "모든 클라우드 운영자가 이 기술을 이미 채택했다"
    invented_condition = "모든 고객의 공식 도입이 확인됨"
    unknown = claim(text=invented_text, kind="unknown").model_copy(
        update={"supports": [], "condition": invented_condition},
    )
    draft = assessment(
        [unknown, claim()],
        summary=[Insight(text="미확인주장만의요약", claim_indices=[0]),
                 Insight(text="미확인주장혼합요약", claim_indices=[0, 1]),
                 Insight(text="검증된주장의요약", claim_indices=[1])],
        implications=[Insight(text="미확인주장만의시사점", claim_indices=[0]),
                      Insight(text="미확인주장혼합시사점", claim_indices=[0, 1]),
                      Insight(text="검증된주장의시사점", claim_indices=[1])],
    )
    model = FakeModel(draft=draft)
    state = run_detailed(input_md, config=config(), model=model, web=FakeWeb())
    normalized = state["draft"].claims[0]
    assert normalized.kind == "unknown"
    assert normalized.text == "미확인 — 편익의 근거를 이번 조사에서 확보하지 못했습니다."
    assert normalized.condition == "입력과 조회 범위에 한정하며 공개 자료 전체의 부재를 의미하지 않습니다."
    review_payload = next(payload for schema, payload in model.calls if schema == "Review")
    assert review_payload["draft"]["claims"][0]["text"] == normalized.text
    for fragment in [invented_text, invented_condition, "미확인주장만의요약", "미확인주장혼합요약",
                     "미확인주장만의시사점", "미확인주장혼합시사점"]:
        assert fragment not in state["output_md"]
    for fragment in ["미확인 — 편익의 근거를 이번 조사에서 확보하지 못했습니다",
                     "검증된주장의요약", "검증된주장의시사점"]:
        assert fragment in state["output_md"]


def test_search_fetch_llm_and_repair_are_bounded_even_if_model_keeps_requesting_more(input_md):
    questions = [question(index) for index in range(20)]
    model = FakeModel(plan=ResearchPlan(questions=questions), draft=assessment([claim()]),
                      review=Review(rejected_claim_indices=[], issues=["외부 자료 보완 필요"],
                                    queries=questions))
    web = FakeWeb(empty=False)
    limits = config(search_limit=3, fetch_limit=2, llm_limit=5, repair_limit=1)
    state = run_detailed(input_md, config=limits, model=model, web=web)
    assert 0 < len(web.search_calls) <= limits.search_limit
    assert 0 < len(web.fetch_calls) <= limits.fetch_limit
    assert len(model.calls) <= limits.llm_limit
    assert state.get("round", 0) <= 1
    assert sum(name == "Assessment" for name, _ in model.calls) <= 2
    assert sum(name == "Review" for name, _ in model.calls) <= 2
    for kind, actual in [("search", len(web.search_calls)), ("fetch", len(web.fetch_calls)),
                         ("llm", len(model.calls))]:
        assert state["budget"].used[kind] == actual
        assert state["budget"].remaining(kind) >= 0


def test_persistent_rejection_triggers_exactly_one_repair(input_md):
    model = FakeModel(draft=assessment([claim(text="지속적으로거절되는주장")]),
                      review=Review(rejected_claim_indices=[0], issues=["다시 검토해도 근거 부족"],
                                    queries=[question()]))
    web = FakeWeb()
    state = run_detailed(input_md,
                         config=config(search_limit=0, fetch_limit=0, llm_limit=5, repair_limit=1),
                         model=model, web=web)
    assert state["round"] == 1
    assert [name for name, _ in model.calls] == ["ResearchPlan", "Assessment", "Review", "Assessment", "Review"]
    assert state["trace"].count("validate") == 2
    assert state["trace"][-1] == "render"
    assert "지속적으로거절되는주장" not in state["output_md"]
    assert web.search_calls == []


def test_search_result_cannot_reassign_an_upstream_paper_to_the_other_technology(input_md):
    class PaperEchoWeb(FakeWeb):
        def search(self, query, max_results=3):
            self.search_calls.append((query, max_results))
            # A search engine may return an unrelated paper for the HW query.
            return [SearchHit(url="https://arxiv.org/abs/2605.08317v1", title="RDKV")]

    wrong = claim(tech_id="HW-01", text="검색결과가논문귀속을바꾼잘못된주장")
    model = FakeModel(draft=assessment([wrong]))
    state = run_detailed(input_md, config=config(), model=model, web=PaperEchoWeb())
    assert state["evidence"]["E-SW-001"].tech_ids == ["SW-01"]
    assert wrong.text not in state["output_md"]


def test_requested_remaining_budgets_can_only_reduce_local_limits(input_md):
    limited = input_md.replace("| 남은 검색 요청 한도 | 6 |", "| 남은 검색 요청 한도 | 1 |")
    limited = limited.replace("| 남은 원문 조회 한도 | 10 |", "| 남은 원문 조회 한도 | 1 |")
    limited = limited.replace("| 남은 LLM 시도 한도 | 5 |", "| 남은 LLM 시도 한도 | 2 |")
    model = FakeModel(plan=ResearchPlan(questions=[question(index) for index in range(10)]),
                      draft=assessment([claim()]))
    web = FakeWeb(empty=False)
    state = run_detailed(limited, config=config(search_limit=6, fetch_limit=10), model=model, web=web)
    assert len(web.search_calls) <= 1
    assert len(web.fetch_calls) <= 1
    assert len(model.calls) <= 2
    assert state["budget"].limits == {"search": 1, "fetch": 1, "llm": 2}


def test_concurrent_runs_do_not_share_evidence_budgets_or_output(input_md):
    def execute(suffix):
        evidence_id = f"E-SW-{suffix}"
        document = input_md.replace("| run_id | demo |", f"| run_id | run-{suffix} |")
        document = document.replace("E-SW-001", evidence_id)
        model = FakeModel(draft=assessment([claim(evidence_id=evidence_id,
                                                text=f"실행별독립주장{suffix}")]))
        return run_detailed(document, config=config(), model=model, web=FakeWeb())

    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = list(pool.map(execute, ["ALPHA", "BETA"]))
    for state, own, other in [(left, "ALPHA", "BETA"), (right, "BETA", "ALPHA")]:
        assert f"실행별독립주장{own}" in state["output_md"]
        assert f"실행별독립주장{other}" not in state["output_md"]
        assert f"E-SW-{own}" in state["evidence"]
        assert f"E-SW-{other}" not in state["evidence"]
    assert left["budget"] is not right["budget"]
    assert left["evidence"] is not right["evidence"]
    before = right["budget"].used["search"]
    left["budget"].take("search")
    assert right["budget"].used["search"] == before


def test_repair_limit_cannot_exceed_one():
    with pytest.raises(ValueError, match="최대 1회"):
        AgentConfig(repair_limit=2)
