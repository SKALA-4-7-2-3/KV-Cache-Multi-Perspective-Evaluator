"""Live operator output selects source-local quotation keys without rewriting text."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from stakeholder_agent import providers
from stakeholder_agent.evidence import quote_options, resolve_support_quotes
from stakeholder_agent.graph import validate_claims
from stakeholder_agent.models import (
    Assessment,
    CatalogAssessment,
    CatalogClaim,
    CatalogSourceReview,
    Evidence,
    OperatorReview,
    Review,
)
from stakeholder_agent.providers import OpenAIModel, ProviderError
from stakeholder_agent.source_quality import assess_web_sources


def assessment_data():
    return {
        "source_reviews": [{
            "evidence_id": "E-WEB", "document_type": "supplier_publication",
            "perspective": "interested_party", "relevance": "family",
            "evidence_basis": "attributed_statement", "decision": "limited",
            "reasons": ["원문에 명시된 기술 계열 설명"], "limitations": ["공급자 자체 설명"],
            "basis_quotes": ["Q001"],
        }],
        "claims": [{
            "tech_id": "SW-01", "domain_id": "D-01", "group": "operator", "aspect": "benefit",
            "kind": "paper_report", "text": "논문은 KV cache 메모리 사용량 감소를 보고한다.",
            "condition": "논문에서 평가한 조건의 범위", "source_scope": "direct",
            "supports": [{"evidence_id": "E-PAPER", "quote": "Q001"}],
            "actor": "", "actor_relationship": "unspecified",
        }],
        "summary": [], "implications": [], "limitations": [], "follow_up": [],
    }


def sources():
    return {
        "E-PAPER": Evidence(
            id="E-PAPER", tech_ids=["SW-01"], title="Paper", url="https://example.org/paper",
            location="Section 3", excerpt="Quantization reduces the KV cache memory footprint.",
        ),
        "E-WEB": Evidence(
            id="E-WEB", tech_ids=["SW-01"], title="Vendor documentation",
            url="https://example.org/documentation", location="본문", source_type="web",
            publisher="Vendor", published_at="2026-09-01",
            excerpt="KV cache compression requires workload-specific quality evaluation.",
        ),
    }


@pytest.mark.parametrize("value", [
    "Quantization reduces memory.", "Q000", "Q081", "q001", "Q001 and Q002",
])
def test_catalog_claim_rejects_rewritten_or_invalid_quotation(value):
    data = assessment_data()
    data["claims"][0]["supports"][0]["quote"] = value
    with pytest.raises(ValidationError) as error:
        CatalogAssessment.model_validate(data)
    assert error.value.errors()[0]["type"] == "literal_error"


def test_catalog_source_review_rejects_rewritten_basis_quote():
    data = assessment_data()
    data["source_reviews"][0]["basis_quotes"] = ["The vendor says quality needs testing."]
    with pytest.raises(ValidationError) as error:
        CatalogAssessment.model_validate(data)
    assert error.value.errors()[0]["type"] == "literal_error"


def test_wire_json_schema_exposes_real_quote_enums():
    definitions = CatalogAssessment.model_json_schema()["$defs"]
    expected = [f"Q{index:03d}" for index in range(1, 81)]
    assert definitions["CatalogSupport"]["properties"]["quote"]["enum"] == expected
    assert definitions["CatalogSourceReview"]["properties"]["basis_quotes"]["items"]["enum"] == expected


def test_accepted_keys_resolve_to_their_own_source_text_and_audit():
    catalog = CatalogAssessment.model_validate(assessment_data())
    draft = Assessment.model_validate(catalog.model_dump())
    evidence = sources()
    resolve_support_quotes(draft, evidence)
    assert type(draft) is Assessment
    assert not isinstance(draft.claims[0], CatalogClaim)
    assert not isinstance(draft.source_reviews[0], CatalogSourceReview)
    assert draft.claims[0].supports[0].quote == evidence["E-PAPER"].excerpt
    audited = assess_web_sources(evidence, draft.source_reviews, "2026-09-22")
    assert audited["E-WEB"].audit["verified_quotes"] == [evidence["E-WEB"].excerpt]
    assert audited["E-WEB"].audit["decision"] == "limited"
    assert validate_claims(draft, audited, {"SW-01"}, {"D-01"}, {("D-01", "operator")}) == ([], [])


def test_catalog_key_absent_from_selected_source_is_still_rejected():
    data = assessment_data()
    data["claims"][0]["supports"][0]["quote"] = "Q080"
    draft = Assessment.model_validate(CatalogAssessment.model_validate(data).model_dump())
    evidence = sources()
    assert "Q080" not in quote_options(evidence["E-PAPER"])
    resolve_support_quotes(draft, evidence)
    rejected, _ = validate_claims(draft, evidence, {"SW-01"})
    assert rejected == [0]


@pytest.mark.parametrize("mode,expected_schema", [
    ("operator_impact", CatalogAssessment), ("stakeholder_reactions", Assessment), (None, Assessment),
])
def test_openai_wire_schema_is_mode_specific_and_returns_regular_assessment(monkeypatch, mode, expected_schema):
    captured = {}
    data = assessment_data()

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured["configuration"] = kwargs

        def with_structured_output(self, schema, **kwargs):
            captured["schema"] = schema
            captured["options"] = kwargs
            return self

        def invoke(self, messages):
            captured["messages"] = messages
            return captured["schema"].model_validate(deepcopy(data))

    monkeypatch.setattr(providers, "ChatOpenAI", FakeChatOpenAI)
    payload = {"analysis_mode": mode} if mode is not None else {}
    result = OpenAIModel("test-model", "test-only").generate(Assessment, "system prompt", payload)
    assert captured["schema"] is expected_schema
    assert captured["options"] == {"method": "json_schema", "strict": True}
    assert type(result) is Assessment
    assert result.model_dump() == data
    assert captured["configuration"]["max_retries"] == 0


def fake_review_model(monkeypatch, result):
    captured = {"invocations": 0}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, schema, **kwargs):
            captured["schema"] = schema
            captured["options"] = kwargs
            return self

        def invoke(self, messages):
            captured["invocations"] += 1
            return result

    monkeypatch.setattr(providers, "ChatOpenAI", FakeChatOpenAI)
    return OpenAIModel("test-model", "test-only"), captured


@pytest.mark.parametrize("mode", ["stakeholder_reactions", None])
def test_legacy_review_keeps_its_own_wire_schema(monkeypatch, mode):
    provider, captured = fake_review_model(
        monkeypatch, Review(rejected_claim_indices=[], issues=[], queries=[]))
    result = provider.generate(Review, "review prompt", {"analysis_mode": mode})
    assert captured["schema"] is Review
    assert type(result) is Review


def test_operator_review_requires_explicit_checks_and_returns_public_review(monkeypatch):
    query = {"tech_id": "SW-01", "group": "operator", "query": "KV cache compression overhead",
             "reason": "처리 지연을 검증할 추가 자료 필요", "domain_id": "D-01"}
    wire = OperatorReview.model_validate({"checks": [
        {"claim_index": 2, "supported": True, "reason": "인용문에 메모리 용량 확장 방식이 명시되어 있다."},
        {"claim_index": 0, "supported": False, "reason": "인용문에는 지연시간 개선 결과가 없다."},
    ], "queries": [query]})
    provider, captured = fake_review_model(monkeypatch, wire)
    result = provider.generate(Review, "review prompt", {
        "analysis_mode": "operator_impact", "review_candidate_indices": [0, 2],
    })
    assert captured["schema"] is OperatorReview
    assert captured["options"] == {"method": "json_schema", "strict": True}
    assert type(result) is Review
    assert result.model_dump() == {
        "rejected_claim_indices": [0], "issues": ["주장 0: 인용문에는 지연시간 개선 결과가 없다."],
        "queries": [query],
    }


@pytest.mark.parametrize("checks", [
    [],
    [{"claim_index": 0, "supported": True, "reason": "Supported."}],
    [{"claim_index": 0, "supported": True, "reason": "Supported."},
     {"claim_index": 0, "supported": True, "reason": "Duplicate."}],
    [{"claim_index": 0, "supported": True, "reason": "Supported."},
     {"claim_index": 1, "supported": True, "reason": "Wrong candidate."}],
    [{"claim_index": 0, "supported": True, "reason": "Supported."},
     {"claim_index": 2, "supported": True, "reason": "Supported."},
     {"claim_index": 3, "supported": True, "reason": "Extra candidate."}],
    [{"claim_index": 0, "supported": True, "reason": "  "},
     {"claim_index": 2, "supported": True, "reason": "Supported."}],
])
def test_operator_review_rejects_empty_incomplete_duplicate_or_extra_checks(monkeypatch, checks):
    provider, captured = fake_review_model(monkeypatch, {"checks": checks, "queries": []})
    with pytest.raises(ProviderError):
        provider.generate(Review, "review prompt", {
            "analysis_mode": "operator_impact", "review_candidate_indices": [0, 2],
        })
    assert captured["invocations"] == 1


def test_old_empty_generic_review_cannot_pass_operator_review(monkeypatch):
    provider, _ = fake_review_model(monkeypatch, Review(rejected_claim_indices=[], issues=[], queries=[]))
    with pytest.raises(ProviderError):
        provider.generate(Review, "review prompt", {
            "analysis_mode": "operator_impact", "review_candidate_indices": [0],
        })


def test_no_candidate_review_can_return_no_checks(monkeypatch):
    provider, _ = fake_review_model(monkeypatch, {"checks": [], "queries": []})
    result = provider.generate(Review, "review prompt", {
        "analysis_mode": "operator_impact", "review_candidate_indices": [],
    })
    assert result == Review(rejected_claim_indices=[], issues=[], queries=[])


@pytest.mark.parametrize("candidates", [None, "0", [True], [-1], [0, 0]])
def test_invalid_candidate_list_fails_before_model_call(monkeypatch, candidates):
    provider, captured = fake_review_model(monkeypatch, {"checks": [], "queries": []})
    with pytest.raises(ProviderError):
        provider.generate(Review, "review prompt", {
            "analysis_mode": "operator_impact", "review_candidate_indices": candidates,
        })
    assert captured["invocations"] == 0


@pytest.mark.parametrize("check", [
    {"claim_index": True, "supported": True, "reason": "Wrong index type."},
    {"claim_index": 0, "supported": "true", "reason": "Wrong verdict type."},
    {"claim_index": 0, "supported": True, "reason": ""},
])
def test_operator_review_verdict_has_strict_types_and_nonempty_reason(check):
    with pytest.raises(ValidationError):
        OperatorReview.model_validate({"checks": [check], "queries": []})
