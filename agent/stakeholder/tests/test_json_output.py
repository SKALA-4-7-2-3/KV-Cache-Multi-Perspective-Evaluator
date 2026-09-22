"""Offline checks of publication gates and source-preserving JSON handoff."""

from copy import deepcopy
from hashlib import sha256

import pytest
from pydantic import ValidationError

from stakeholder_agent.config import AgentConfig
from stakeholder_agent.json_input import NormalizedInput
from stakeholder_agent.json_output import StakeholderOutput, render_json_output
from stakeholder_agent.models import (
    AnalysisContext,
    Assessment,
    Budget,
    Claim,
    Domain,
    Evidence,
    Insight,
    ParsedInput,
    ResearchPlan,
    Review,
    StakeholderTarget,
    Support,
    Technology,
)

PAPER_QUOTE = "The paper evaluates memory reduction in a controlled research setting."
WEB_QUOTE = "The named provider describes deployment validation for this technology."


@pytest.fixture
def ready():
    technologies = [Technology("SW-01", "RDKV", "SW", "RDKV paper", "https://example.org/sw"),
                    Technology("HW-01", "Photonic-CXL", "HW", "Photonic-CXL paper", "https://example.org/hw")]
    paper = Evidence(id="E-ORIGINAL-SW", tech_ids=["SW-01"], title="RDKV paper",
                     url="https://example.org/sw", location="p. 2", excerpt=PAPER_QUOTE)
    parsed = ParsedInput(run_id="run-json-test", as_of="2026-09-22", technologies=technologies,
                         evidence={paper.id: paper}, summary="Provided technical summary",
                         analysis_context=AnalysisContext(
                             original_request="클라우드 데이터센터의 이해관계자를 조사해줘.",
                             domains=[Domain("D-CLOUD", "클라우드 데이터센터", "LLM 추론 서비스 운영")]))
    raw_evidence = {"evidence_id": paper.id, "document_id": "original-paper", "snippet": PAPER_QUOTE,
                    "chunk_id": "original-chunk", "content_hash": "upstream-full-chunk-hash", "page": 2}
    normalized = NormalizedInput(
        parsed=parsed, request={"original_request": parsed.analysis_context.original_request,
                                "domains": [{"id": "D-CLOUD", "name": "클라우드 데이터센터"}],
                                "additional_context": {"priority": "integration"}},
        papers=[{"evidence_registry": [raw_evidence]}],
        provenance=[{"kind": "paper_analysis", "status": "succeeded"}], round=0,
        budget={"llm": 5, "search": 6, "fetch": 10}, usage={"llm": 0, "search": 0, "fetch": 0},
        schema_version="1.0", config={"as_of": "2026-09-22"})
    claim = Claim(tech_id="SW-01", domain_id="D-CLOUD", group="operator", kind="paper_report",
                  aspect="benefit", text="실험 조건에서 메모리 감소를 평가했다고 논문이 보고합니다.",
                  condition="논문 실험 조건", source_scope="direct",
                  supports=[Support(evidence_id=paper.id, quote=PAPER_QUOTE)])
    draft = Assessment(claims=[claim], summary=[Insight(text="검증된 요약", claim_indices=[0])],
                       implications=[], limitations=["추가로 검토할 한계"], follow_up=["실제 운영 조건 확인"])
    state = {
        "parsed": parsed, "draft": draft, "evidence": dict(parsed.evidence),
        "plan": ResearchPlan(questions=[], stakeholders=[StakeholderTarget(
            id="operator", domain_id="D-CLOUD", name="운영자", reason="운영 환경 검토", priority="core")]),
        "review": Review(rejected_claim_indices=[], issues=[], queries=[]), "review_succeeded": True,
        "rejected": [], "errors": [], "gaps": [], "round": 0, "status": "completed",
        "execution_status": "completed", "evidence_status": "direct_available",
        "selection_origin": "model", "trace": ["prepare", "analyze", "validate", "render"],
        "budget": Budget({"llm": 5, "search": 6, "fetch": 10}, {"llm": 3, "search": 2, "fetch": 1}),
        "coverage": [{"this_is": "stale and deliberately ignored"}], "research_log": [],
    }
    return state, normalized


def export(ready, **kwargs):
    state, normalized = ready
    return render_json_output(state, normalized, config=AgentConfig(), **kwargs)


def add_statement(state, *, tech_id="SW-01", group="operator", scope="direct", decision="use"):
    identifier = f"WEB-{tech_id}-{group}"
    source = Evidence(id=identifier, tech_ids=[tech_id], title=f"{tech_id} deployment statement",
                      url=f"https://example.org/{identifier}", location="Deployment paragraph",
                      excerpt=WEB_QUOTE + " " + "Additional public source context. " * 3,
                      source_type="web", scope=scope, publisher="Named provider", published_at="2026-09-01",
                      audit={"decision": decision, "relevance": scope,
                             "direct_tech_ids": [tech_id] if scope == "direct" else [],
                             "verified_quotes": [WEB_QUOTE]})
    state["evidence"][identifier] = source
    claim = Claim(tech_id=tech_id, domain_id="D-CLOUD", group=group, kind="statement", aspect="evaluation",
                  text=f"{tech_id}에 대한 공급자의 배포 검증 설명", condition="공급자의 자체 설명 범위",
                  source_scope=scope, actor="Named provider", actor_relationship="provider",
                  supports=[Support(evidence_id=identifier, quote=WEB_QUOTE)])
    state["draft"].claims.append(claim)
    return source, claim


def test_output_preserves_original_evidence_ids_hashes_and_request(ready):
    result = export(ready)
    StakeholderOutput.model_validate(result)
    record = result["evidence"]["E-ORIGINAL-SW"]
    assert record["upstream"]["content_hash"] == "upstream-full-chunk-hash"
    assert record["upstream"]["chunk_id"] == "original-chunk"
    assert record["excerpt"] == PAPER_QUOTE
    assert record["excerpt_sha256"] == sha256(PAPER_QUOTE.encode()).hexdigest()
    assert result["result"]["details"]["request"] == ready[1].request
    assert {r["evidence_id"] for r in result["references"]} == {"E-ORIGINAL-SW"}
    assert result["new_evidence"] == {}


@pytest.mark.parametrize("rejection_source", ["state", "review", "deterministic"])
def test_rejections_remove_claims_and_dependent_insights(ready, rejection_source):
    state, _ = ready
    state["draft"].claims.append(state["draft"].claims[0].model_copy(deep=True, update={"text": "별도의 유효한 보고"}))
    state["draft"].summary = [Insight(text="REJECTED_SUMMARY", claim_indices=[0]),
                              Insight(text="MIXED_SUMMARY", claim_indices=[0, 1]),
                              Insight(text="KEPT_SUMMARY", claim_indices=[1])]
    state["draft"].implications = [Insight(text="REJECTED_IMPLICATION", claim_indices=[0, 1])]
    if rejection_source == "state":
        state["rejected"] = [0]
    elif rejection_source == "review":
        state["review"].rejected_claim_indices = [0]
    else:
        state["draft"].claims[0].supports[0].quote = "Fabricated quote absent from the actual source."
    result = export(ready)
    details = result["result"]["details"]
    assert [row["text"] for row in details["summary"]] == ["KEPT_SUMMARY"]
    assert details["implications"] == []
    assert result["result"]["by_technology"]["SW-01"]["claims"][0]["id"].endswith("C002")
    assert details["coverage"][0]["claim_ids"] == ["STK-run-json-test-R0-C002"]


@pytest.mark.parametrize("source_problem", ["hold", "exclude", "identity", "family", "missing_actor"])
def test_export_reapplies_web_source_guards(ready, source_problem):
    state, _ = ready
    source, claim = add_statement(state)
    if source_problem in {"hold", "exclude"}:
        source.audit["decision"] = source_problem
    elif source_problem == "identity":
        source.audit["direct_tech_ids"] = []
    elif source_problem == "family":
        source.audit["relevance"] = "family"
    else:
        claim.actor = ""
    result = export(ready)
    assert not result["result"]["details"]["observations"]
    assert source.id not in {r["evidence_id"] for r in result["references"]}
    assert result["new_evidence"][source.id]["cited"] is False


def test_failed_semantic_review_publishes_no_claims_or_insights(ready):
    state, _ = ready
    state["review_succeeded"] = False
    result = export(ready)
    assert result["execution_status"] == result["status"] == "failed"
    assert result["evidence_status"] == "unavailable"
    assert all(not row["claims"] for row in result["result"]["by_technology"].values())
    assert result["result"]["details"]["summary"] == []
    assert result["result"]["details"]["implications"] == []
    assert result["references"] == []
    assert result["errors"]


def test_unknown_claim_never_becomes_a_cited_finding(ready):
    state, _ = ready
    state["draft"].claims[0] = state["draft"].claims[0].model_copy(
        update={"kind": "unknown", "supports": [], "text": "Unverified invented information"})
    result = export(ready)
    assert result["references"] == []
    assert result["result"]["details"]["summary"] == []
    assert any("근거를 확보하지 못했습니다" in gap for gap in result["gaps"])


def test_sufficient_requires_every_core_target_for_both_technologies(ready):
    state, _ = ready
    add_statement(state, tech_id="SW-01")
    result = export(ready)
    assert result["evidence_status"] == "limited"
    add_statement(state, tech_id="HW-01")
    assert export(ready)["evidence_status"] == "sufficient"
    state["plan"].stakeholders.append(StakeholderTarget(
        id="developer", domain_id="D-CLOUD", name="개발자", reason="통합 작업", priority="core"))
    assert export(ready)["evidence_status"] == "limited"


def test_source_excerpts_are_full_bounded_handoff_data_and_references_are_cited_only(ready):
    state, _ = ready
    source, _ = add_statement(state)
    result = export(ready)
    record = result["new_evidence"][source.id]
    assert record["excerpt"] == source.excerpt
    assert record["excerpt_sha256"] == sha256(source.excerpt.encode()).hexdigest()
    assert record == result["evidence"][source.id]
    assert {r["evidence_id"] for r in result["references"]} == {"E-ORIGINAL-SW", source.id}
    assert "excerpt" not in result["references"][0]


def test_usage_is_cumulative_and_round_ids_are_outer_round(ready):
    state, normalized = ready
    normalized.usage = {"llm": 2, "search": 2, "fetch": 1}
    normalized.round = 1
    state["round"] = 0
    result = export(ready)
    assert result["round"] == 1
    assert result["usage"]["used"] == {"llm": 3, "search": 2, "fetch": 1}
    assert result["usage"]["delta"] == {"llm": 1, "search": 0, "fetch": 0}
    assert result["usage"]["remaining"] == {"llm": 2, "search": 4, "fetch": 9}
    assert result["result"]["by_technology"]["SW-01"]["claims"][0]["id"] == "STK-run-json-test-R1-C001"
    assert result["result"]["details"]["runtime"]["internal_repair_round"] == 0


def test_benefit_does_not_invent_favorable_judgment_and_fixture_is_explicit(ready):
    result = export(ready, mode="fixture")
    assert result["mode"] == "fixture"
    assert result["result"]["by_technology"]["SW-01"]["criteria"][0]["judgment"] == "unknown"
    assert set(result["result"]["by_technology"]) == {"SW-01", "HW-01"}
    assert result["result"]["by_technology"]["HW-01"]["claims"] == []


def test_input_failure_has_valid_two_technology_shell_and_no_environment_secrets():
    config = AgentConfig(openai_api_key="SECRET-OPENAI", tavily_api_key="SECRET-TAVILY")
    result = render_json_output({}, None, config=config, input_error="입력 규격 오류")
    assert result["execution_status"] == result["status"] == "failed"
    assert set(result["result"]["by_technology"]) == {"SW-01", "HW-01"}
    assert result["errors"][0]["code"] == "invalid_input"
    assert "SECRET-" not in str(result)
    StakeholderOutput.model_validate(result)


def test_json_schema_and_integrity_validation(ready):
    schema = StakeholderOutput.model_json_schema()
    assert "Finding" in schema["$defs"] and "EvidenceRecord" in schema["$defs"]
    result = export(ready)
    result["references"] = []
    with pytest.raises(ValidationError, match="exactly the cited evidence"):
        StakeholderOutput.model_validate(result)


def test_export_does_not_mutate_graph_state_or_input(ready):
    before = deepcopy(ready)
    export(ready)
    assert ready == before


@pytest.mark.parametrize("tamper", ["phantom", "missing", "duplicate", "different_text", "wrong_partition"])
def test_detail_partitions_cannot_add_remove_or_relabel_canonical_claims(ready, tamper):
    result = export(ready)
    details = result["result"]["details"]
    claim = details["paper_and_inference_findings"][0]
    if tamper == "phantom":
        phantom = deepcopy(claim)
        phantom.update(id="NONEXISTENT", evidence_ids=["UNREGISTERED"], kind="statement")
        details["observations"].append(phantom)
    elif tamper == "missing":
        details["paper_and_inference_findings"] = []
    elif tamper == "duplicate":
        details["paper_and_inference_findings"].append(deepcopy(claim))
    elif tamper == "different_text":
        claim["text"] = "Canonical claim did not make this assertion."
    else:
        details["observations"].append(details["paper_and_inference_findings"].pop())
    with pytest.raises(ValidationError, match="partitions must exactly match"):
        StakeholderOutput.model_validate(result)


@pytest.mark.parametrize("field,value", [
    ("technology_id", "HW-01"), ("domain_id", "OTHER-DOMAIN"), ("stakeholder_id", "another-group"),
])
def test_coverage_must_retain_canonical_claim_scope(ready, field, value):
    result = export(ready)
    row = next(row for row in result["result"]["details"]["coverage"] if row["claim_ids"])
    row[field] = value
    with pytest.raises(ValidationError, match="Coverage scope"):
        StakeholderOutput.model_validate(result)


@pytest.mark.parametrize("field,value", [("technology_ids", ["HW-01"]), ("domain_ids", ["OTHER-DOMAIN"])])
def test_insight_scope_must_match_its_accepted_claims(ready, field, value):
    result = export(ready)
    result["result"]["details"]["summary"][0][field] = value
    with pytest.raises(ValidationError, match="Insight scope"):
        StakeholderOutput.model_validate(result)


@pytest.mark.parametrize("counter", ["llm", "search", "fetch"])
@pytest.mark.parametrize("field", ["remaining", "delta"])
def test_inconsistent_usage_counters_are_rejected(ready, counter, field):
    result = export(ready)
    result["usage"][field][counter] = result["usage"]["used"][counter] + 100
    with pytest.raises(ValidationError, match="remaining must equal|delta cannot exceed"):
        StakeholderOutput.model_validate(result)


def test_previously_exhausted_budget_may_exceed_limit_with_zero_remaining(ready):
    state, normalized = ready
    normalized.usage["llm"] = 7
    state["budget"].used["llm"] = 7
    result = export(ready)
    assert result["usage"]["used"]["llm"] == 7
    assert result["usage"]["remaining"]["llm"] == 0
    assert result["usage"]["delta"]["llm"] == 0
    StakeholderOutput.model_validate(result)
