"""Web-source restrictions are provenance checks, not truth or popularity scores."""

from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from stakeholder_agent.models import Claim, Evidence, Support, Technology, WebSourceReview
from stakeholder_agent.source_quality import assess_web_sources, pending_web_source_ids, web_source_issue

AS_OF = "2026-09-21"
TEXT = "The researchers describe their methods and measured results in this document."
TECHNOLOGIES = [
    Technology(id="SW-01", name="RDKV", kind="SW",
               paper="Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache, "
                     "arXiv:2605.08317v1, https://arxiv.org/abs/2605.08317v1",
               url="https://arxiv.org/abs/2605.08317v1"),
    Technology(id="HW-01", name="Photonic-CXL", kind="HW",
               paper="A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference, "
                     "arXiv:2607.27187v1, https://arxiv.org/abs/2607.27187v1",
               url="https://arxiv.org/abs/2607.27187v1"),
]


def source(**changes):
    fields = {"id": "WEB-ONE", "tech_ids": ["HW-01"], "title": "Measured research results",
              "url": "https://research.example.org/results", "location": "Methods and results",
              "excerpt": TEXT, "publisher": "Independent research group", "published_at": "2026-09-01",
              "source_type": "web", "metadata_provenance": {"publisher": "page metadata"}}
    fields.update(changes)
    return Evidence(**fields)


def review(identifier="WEB-ONE", **changes):
    fields = {"evidence_id": identifier, "document_type": "research", "perspective": "independent_author",
              "relevance": "direct", "evidence_basis": "methods_and_results", "decision": "use",
              "reasons": ["수집 본문의 방법과 결과를 검토함"], "limitations": [], "basis_quotes": ["Q001"]}
    fields.update(changes)
    return WebSourceReview(**fields)


def supported_claim(kind="inference", scope="direct"):
    return Claim(tech_id="HW-01", group="supplier", aspect="benefit", kind=kind,
                 text="자료에 근거한 검토 내용", condition="해당 자료의 범위", source_scope=scope,
                 supports=[Support(evidence_id="WEB-ONE", quote=TEXT)])


def audited(record=None, source_review=None):
    record = record or source()
    source_review = source_review or review(record.id)
    return assess_web_sources({record.id: record}, [source_review], AS_OF)[record.id]


def test_only_web_sources_are_copied_and_audited_without_mutating_upstream_papers():
    paper = source(id="PAPER-ONE", source_type="paper", audit={"upstream": "leave unchanged"},
                   requested_url="https://arxiv.org/abs/example", author="Original author",
                   search_queries=["original query"], content_sha256="original-digest")
    web = source()
    before = deepcopy(asdict(paper))
    incoming = {paper.id: paper, web.id: web}
    result = assess_web_sources(incoming, [review(paper.id, decision="exclude"), review(web.id)], AS_OF)
    assert result is not incoming
    assert result[paper.id] is paper
    assert asdict(paper) == before
    assert result[web.id] is not web
    assert web.audit == {}
    assert result[web.id].audit["decision"] == "use"
    assert result[web.id].metadata_provenance == web.metadata_provenance


@pytest.mark.parametrize("quotes", [["Q001"], [TEXT]])
def test_source_review_requires_exact_source_local_catalog_choice_or_literal_span(quotes):
    result = audited(source_review=review(basis_quotes=quotes))
    assert result.audit["decision"] == "use"
    assert result.audit["verified_quotes"] == [TEXT]


@pytest.mark.parametrize("quotes", [[], ["Q999"], [" Q001"], ["번역해서 새로 작성한 연구 결과 설명"],
                                     ["Q001", "원문에 없는 두 번째 분류 근거 문장"]])
def test_missing_or_rewritten_classification_basis_holds_source(quotes):
    result = audited(source_review=review(basis_quotes=quotes))
    assert result.audit["decision"] == "hold"
    assert web_source_issue(result, supported_claim("statement"))


@pytest.mark.parametrize("path_length", [40, 600])
@pytest.mark.parametrize("basis", ["literal", "catalog"])
def test_navigation_link_destination_cannot_authorize_a_web_source_review(path_length, basis):
    raw_link = "[IR](https://example.org/" + "x" * path_length + ")"
    record = source(excerpt=raw_link)
    result = audited(record, review(basis_quotes=[raw_link if basis == "literal" else "Q001"]))
    assert result.audit["decision"] == "hold"
    assert result.audit["verified_quotes"] == []
    assert web_source_issue(result, supported_claim("statement"))


def test_quote_key_from_another_sources_catalog_does_not_validate_this_source():
    one = source()
    two = source(id="WEB-TWO", excerpt=TEXT + "\nA second sentence is available only in the other source.")
    result = assess_web_sources({one.id: one, two.id: two},
                                [review(one.id, basis_quotes=["Q002"]), review(two.id, basis_quotes=["Q002"])],
                                AS_OF)
    assert result[one.id].audit["decision"] == "hold"
    assert result[two.id].audit["decision"] == "use"


@pytest.mark.parametrize("reviews", [[], [review(), review()]])
def test_missing_or_duplicate_reviews_cannot_authorize_citation(reviews):
    record = source()
    result = assess_web_sources({record.id: record}, reviews, AS_OF)[record.id]
    assert result.audit["decision"] == "hold"
    assert web_source_issue(result, supported_claim("statement"))
    assert web_source_issue(result, supported_claim("inference"))


@pytest.mark.parametrize(("source_changes", "review_changes"), [
    ({}, {"document_type": "supplier_publication"}),
    ({}, {"perspective": "interested_party"}),
    ({}, {"perspective": "unknown"}),
    ({"publisher": "미표기"}, {}),
    ({"published_at": "미표기"}, {}),
    ({}, {"evidence_basis": "attributed_statement"}),
    ({}, {"evidence_basis": "opinion"}),
    ({}, {"document_type": "commentary"}),
    ({}, {"document_type": "republication"}),
])
def test_limited_sources_only_support_attributed_statements(source_changes, review_changes):
    result = audited(source(**source_changes), review(**review_changes))
    assert result.audit["decision"] == "limited"
    assert result.audit["limitations"]
    assert web_source_issue(result, supported_claim("inference"))
    assert web_source_issue(result, supported_claim("paper_report"))
    assert web_source_issue(result, supported_claim("statement")) == ""
    if review_changes.get("document_type") == "supplier_publication":
        assert result.audit["perspective"] == "interested_party"


@pytest.mark.parametrize("relevance", ["family", "unknown"])
def test_family_or_unknown_relevance_cannot_be_cited_as_direct(relevance):
    result = audited(source_review=review(relevance=relevance))
    assert result.audit["decision"] == "limited"
    assert web_source_issue(result, supported_claim("statement", "direct"))
    assert web_source_issue(result, supported_claim("statement", "family")) == ""


@pytest.mark.parametrize("changes", [{"relevance": "background"}, {"relevance": "unrelated"},
                                    {"decision": "exclude"}])
def test_irrelevant_or_excluded_sources_are_not_citable(changes):
    result = audited(source_review=review(**changes))
    assert result.audit["decision"] == "exclude"
    assert web_source_issue(result, supported_claim("statement"))


@pytest.mark.parametrize("record", [source(published_at="2026-09-22"), source(excerpt="  ")])
def test_future_or_empty_sources_are_excluded_even_with_a_positive_review(record):
    result = audited(record)
    assert result.audit["decision"] == "exclude"
    assert web_source_issue(result, supported_claim("statement"))


def test_multiple_domains_do_not_certify_independent_corroboration_or_create_scores():
    one = source(url="https://first.example.org/results")
    two = replace(one, id="WEB-TWO", url="https://second.example.org/results")
    records = assess_web_sources({one.id: one, two.id: two}, [review(one.id), review(two.id)], AS_OF)
    for record in records.values():
        assert record.audit["decision"] == "use"
        assert record.audit["checks"]["교차검증"].startswith("미확인")
        assert "독립 검증을 인정하지 않음" in record.audit["checks"]["교차검증"]
        assert "보증하지 않음" in " ".join(record.audit["reasons"])
        assert not {"score", "confidence", "trust_score", "corroborated"} & record.audit.keys()


def test_papers_bypass_web_use_restrictions_even_with_unrelated_upstream_audit():
    paper = source(source_type="paper", audit={"decision": "hold"})
    assert web_source_issue(paper, supported_claim()) == ""


def identity_audited(record, source_review=None, technologies=None):
    return assess_web_sources({record.id: record}, [source_review or review(record.id)], AS_OF,
                              technologies=TECHNOLOGIES if technologies is None else technologies)[record.id]


def test_generic_cxl_paper_cannot_be_upgraded_to_photonic_cxl_by_model_classification():
    record = source(title="Exploring CXL-based KV Cache Storage for LLM Serving",
                    published_at="2024-08-01", excerpt=TEXT + " We evaluate CXL memory for LLM serving.")
    result = identity_audited(record)
    assert result.audit["direct_tech_ids"] == []
    assert result.audit["relevance"] == "unknown"
    assert result.audit["decision"] == "limited"
    assert "확인하지 못함" in result.audit["checks"]["직접 기술 식별"]
    assert "충분조건이 아님" in result.audit["checks"]["직접 관련성 최소 조건"]
    assert any("공통 계열 용어" in item for item in result.audit["limitations"])
    assert web_source_issue(result, supported_claim("statement", "direct"))
    assert web_source_issue(result, supported_claim("inference", "direct"))
    assert web_source_issue(result, supported_claim("statement", "family")) == ""


@pytest.mark.parametrize("name", ["Photonic-CXL", "PHOTONIC CXL", "photonic–cxl", "PhotonicCXL",
                                  "Photonic\n CXL"])
@pytest.mark.parametrize("location", ["title", "excerpt"])
def test_real_technology_name_accepts_spacing_hyphen_and_case_variants(name, location):
    fields = {location: f"A study of {name} and its deployment requirements."}
    if location == "excerpt":
        fields[location] = TEXT + " " + fields[location]
    result = identity_audited(source(**fields))
    assert result.audit["direct_tech_ids"] == ["HW-01"]
    assert result.audit["relevance"] == "direct"
    assert result.audit["decision"] == "use"
    assert web_source_issue(result, supported_claim("statement")) == ""


def test_identifying_one_technology_does_not_authorize_a_direct_claim_for_another():
    result = identity_audited(source(title="RDKV implementation report", tech_ids=["SW-01", "HW-01"]))
    assert result.audit["direct_tech_ids"] == ["SW-01"]
    assert result.audit["relevance"] == "direct"
    assert result.audit["decision"] == "use"
    assert web_source_issue(result, supported_claim("statement"))
    own_claim = supported_claim("statement").model_copy(update={"tech_id": "SW-01"})
    assert web_source_issue(result, own_claim) == ""


@pytest.mark.parametrize("identity", [
    "Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache",
    "The experiment uses arXiv:2605.08317v1.",
    "The implementation evaluates https://arxiv.org/abs/2605.08317v2 in detail.",
])
def test_paper_title_or_arxiv_identity_can_identify_a_technology_without_its_short_name(identity):
    result = identity_audited(source(excerpt=TEXT + " " + identity, tech_ids=["SW-01"]))
    assert result.audit["direct_tech_ids"] == ["SW-01"]
    assert result.audit["decision"] == "use"


@pytest.mark.parametrize("misleading_name", ["CXL", "Photonic Fabric", "NotPhotonicCXL", "RDKV2",
                                             "arXiv:2607.271871", "arXiv:2605.08318"])
def test_generic_related_terms_and_partial_identifiers_are_not_exact_technology_identities(misleading_name):
    result = identity_audited(source(title=misleading_name))
    assert result.audit["direct_tech_ids"] == []
    assert result.audit["relevance"] == "unknown"


def test_query_association_or_url_path_cannot_supply_identity_missing_from_collected_content():
    record = source(url="https://example.org/Photonic-CXL/2607.27187",
                    requested_url="https://example.org/RDKV/2605.08317",
                    search_queries=["RDKV Photonic-CXL arXiv:2607.27187"], tech_ids=["SW-01", "HW-01"])
    result = identity_audited(record)
    assert result.audit["direct_tech_ids"] == []
    assert web_source_issue(result, supported_claim("statement"))


@pytest.mark.parametrize("review_changes", [{"relevance": "family"}, {"decision": "exclude"},
                                          {"basis_quotes": []}])
def test_identity_mention_does_not_override_source_review_or_missing_review_basis(review_changes):
    result = identity_audited(source(title="Photonic-CXL study"), review(**review_changes))
    assert result.audit["direct_tech_ids"] == ["HW-01"]
    assert web_source_issue(result, supported_claim("statement", "direct"))


def test_identity_check_does_not_weaken_exclusion_when_model_says_direct_without_identity():
    result = identity_audited(source(), review(decision="exclude"))
    assert result.audit["direct_tech_ids"] == []
    assert result.audit["decision"] == "exclude"
    assert web_source_issue(result, supported_claim("statement", "family"))


def test_identity_guard_preserves_legacy_calls_and_original_paper_objects():
    generic = source()
    legacy = assess_web_sources({generic.id: generic}, [review()], AS_OF)[generic.id]
    explicit_none = assess_web_sources({generic.id: generic}, [review()], AS_OF, technologies=None)[generic.id]
    assert legacy.audit == explicit_none.audit
    assert legacy.audit["decision"] == "use"
    assert "direct_tech_ids" not in legacy.audit
    assert web_source_issue(legacy, supported_claim("statement")) == ""
    paper = source(id="PAPER-ONE", source_type="paper", audit={"upstream": "preserved"})
    before = deepcopy(asdict(paper))
    result = assess_web_sources({paper.id: paper, generic.id: generic}, [review()], AS_OF,
                                technologies=TECHNOLOGIES)
    assert result[paper.id] is paper
    assert asdict(paper) == before
    assert generic.audit == {}
    assert result[generic.id].audit["direct_tech_ids"] == []


@pytest.mark.parametrize("decision", ["use", "limited", "exclude"])
def test_completed_audit_survives_omission_only_when_preservation_is_requested(decision):
    first = audited(source_review=review(decision=decision))
    previous = deepcopy(first.audit)
    retained = assess_web_sources({first.id: first}, [], AS_OF, preserve_existing=True)[first.id]
    assert retained is first
    assert retained.audit == previous
    assert retained.audit["context_fingerprint"].startswith("sha256:")
    default = assess_web_sources({first.id: first}, [], AS_OF)[first.id]
    assert default.audit["decision"] == "hold"
    assert first.audit == previous


def test_preservation_keeps_limited_citation_restrictions():
    first = audited(source_review=review(document_type="supplier_publication", relevance="family"))
    retained = assess_web_sources({first.id: first}, [], AS_OF, preserve_existing=True)[first.id]
    assert retained.audit["decision"] == "limited"
    assert web_source_issue(retained, supported_claim("inference", "family"))
    assert web_source_issue(retained, supported_claim("statement", "direct"))
    assert web_source_issue(retained, supported_claim("statement", "family")) == ""


@pytest.mark.parametrize("changes", [
    {"excerpt": TEXT + " A newly collected passage."},
    {"title": "Revised title"},
    {"url": "https://other.example.org/results"},
    {"publisher": "Different publisher"},
    {"published_at": "2026-09-02"},
    {"metadata_provenance": {"publisher": "search result"}},
    {"retrieved_at": "2026-09-21T12:00:00Z"},
    {"tech_ids": ["SW-01"]},
])
def test_changed_source_material_or_metadata_invalidates_prior_audit(changes):
    first = audited()
    revised = replace(first, **changes)
    result = assess_web_sources({revised.id: revised}, [], AS_OF, preserve_existing=True)[revised.id]
    assert result.audit["decision"] == "hold"
    assert result.audit["context_fingerprint"] != first.audit["context_fingerprint"]


def test_changed_as_of_requires_review_and_reapplies_future_date_exclusion():
    first = audited()
    later = assess_web_sources({first.id: first}, [], "2026-09-22", preserve_existing=True)[first.id]
    assert later.audit["decision"] == "hold"
    before_publication = assess_web_sources(
        {first.id: first}, [], "2026-08-31", preserve_existing=True)[first.id]
    assert before_publication.audit["decision"] == "exclude"
    assert "조사 기준일 이후" in before_publication.audit["reasons"][0]


def test_technology_identity_context_is_required_for_preserving_direct_source_review():
    first = identity_audited(source(title="Photonic-CXL study"))
    same = assess_web_sources({first.id: first}, [], AS_OF, technologies=deepcopy(TECHNOLOGIES),
                              preserve_existing=True)[first.id]
    assert same is first
    changed = [replace(TECHNOLOGIES[0], name="Different software"), TECHNOLOGIES[1]]
    for identities in (changed, None, []):
        result = assess_web_sources({first.id: first}, [], AS_OF, technologies=identities,
                                    preserve_existing=True)[first.id]
        assert result.audit["decision"] == "hold"


@pytest.mark.parametrize("fingerprint", [None, "sha256:unverified"])
def test_existing_external_audit_without_matching_local_context_is_not_preserved(fingerprint):
    audit = {"decision": "use", "relevance": "direct"}
    if fingerprint:
        audit["context_fingerprint"] = fingerprint
    record = source(audit=audit)
    result = assess_web_sources({record.id: record}, [], AS_OF, preserve_existing=True)[record.id]
    assert result.audit["decision"] == "hold"


def test_new_review_replaces_prior_completed_review_even_with_preservation_enabled():
    first = audited()
    result = assess_web_sources({first.id: first}, [review(decision="exclude")], AS_OF,
                                preserve_existing=True)[first.id]
    assert result.audit["decision"] == "exclude"
    assert result is not first
    assert first.audit["decision"] == "use"


def test_duplicate_reviews_hold_source_instead_of_reusing_prior_successful_audit():
    first = audited()
    result = assess_web_sources({first.id: first}, [review(), review()], AS_OF,
                                preserve_existing=True)[first.id]
    assert result.audit["decision"] == "hold"
    assert "중복 평가" in result.audit["reasons"][0]


def test_hold_audit_is_re_evaluated_when_new_review_is_supplied():
    record = source()
    first = assess_web_sources({record.id: record}, [], AS_OF)[record.id]
    assert first.audit["decision"] == "hold"
    second = assess_web_sources({first.id: first}, [review()], AS_OF,
                                preserve_existing=True)[first.id]
    assert second.audit["decision"] == "use"


def test_pending_web_sources_include_missing_and_hold_but_not_papers_or_completed_reviews():
    records = {
        "PAPER": source(id="PAPER", source_type="paper"),
        "MISSING": source(id="MISSING"),
        "HOLD": source(id="HOLD", audit={"decision": "hold"}),
        "USE": source(id="USE", audit={"decision": "use"}),
        "LIMITED": source(id="LIMITED", audit={"decision": "limited"}),
        "EXCLUDED": source(id="EXCLUDED", audit={"decision": "exclude"}),
    }
    assert pending_web_source_ids(records) == ["MISSING", "HOLD"]
