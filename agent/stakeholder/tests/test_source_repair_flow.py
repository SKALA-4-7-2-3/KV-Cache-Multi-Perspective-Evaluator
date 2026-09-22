"""A missing source review triggers bounded repair without discarding useful paper facts."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from stakeholder_agent.agent import run_detailed
from stakeholder_agent.config import AgentConfig
from stakeholder_agent.json_output import StakeholderOutput
from stakeholder_agent.models import (
    Assessment,
    Claim,
    ResearchPlan,
    Review,
    SearchQuestion,
    Support,
    WebSourceReview,
)
from stakeholder_agent.providers import SearchHit, SourcePage

ROOT = Path(__file__).resolve().parents[1]
WEB_TEXT = "RDKV and Photonic-CXL require workload-specific deployment validation in data centers."


@pytest.fixture
def input_payload():
    return {
        "schema_version": "1.0", "run_id": "source-repair", "role": "stakeholders",
        "paper_analyses": [json.loads((ROOT / f"examples/papers/{name}.json").read_text())
                           for name in ("rdkv", "photonic-cxl")],
        "request": json.loads((ROOT / "examples/request.json").read_text()),
        "config": {"as_of": "2026-09-22"}, "round": 0,
        "budget": {"llm": 5, "search": 6, "fetch": 10},
        "usage": {"llm": 0, "search": 0, "fetch": 0},
    }


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Source repair tests must not make HTTP requests")

    monkeypatch.setattr("httpx.Client.request", blocked)
    monkeypatch.setattr("httpx.Client.stream", blocked)


class TwoPageWeb:
    def __init__(self):
        self.search_calls = []
        self.fetch_calls = []

    def search(self, query, max_results=3):
        self.search_calls.append(query)
        return [SearchHit(url=f"https://research.example.org/{len(self.search_calls)}",
                          title="RDKV and Photonic-CXL deployment research")]

    def fetch(self, url):
        self.fetch_calls.append(url)
        return SourcePage(url=url, title="RDKV and Photonic-CXL deployment research",
                          text=WEB_TEXT, publisher="Independent research group",
                          published_at="2026-09-01")


class SourceRepairModel:
    def __init__(self, *, resolve_pending=True, request_search=False):
        self.resolve_pending = resolve_pending
        self.request_search = request_search
        self.calls = []
        self.analysis_payloads = []

    def generate(self, schema, system, payload):
        self.calls.append(schema.__name__)
        if schema is ResearchPlan:
            return ResearchPlan(questions=[])
        if schema is Review:
            queries = []
            if self.request_search:
                queries = [SearchQuestion(
                    tech_id="SW-01", domain_id=payload["analysis_context"]["domains"][0]["id"],
                    group="operator", query="RDKV additional deployment evidence",
                    reason="Reviewer requests additional evidence")]
            return Review(rejected_claim_indices=[], issues=[], queries=queries)
        assert schema is Assessment
        self.analysis_payloads.append(deepcopy(payload))
        web = [item for item in payload["evidence"] if item["source_type"] == "web"]
        if len(self.analysis_payloads) == 1:
            reviewed = web[:1]  # Deliberately omit the second collected document.
        elif self.resolve_pending:
            reviewed = [item for item in web if item["id"] in payload["required_source_review_ids"]]
        else:
            reviewed = []
        reviews = [WebSourceReview(
            evidence_id=item["id"], document_type="research", perspective="independent_author",
            relevance="direct", evidence_basis="methods_and_results", decision="use",
            reasons=["Reviewed the collected passage"], limitations=[], basis_quotes=["Q001"])
            for item in reviewed]
        paper = next(item for item in payload["evidence"]
                     if item["source_type"] == "paper" and "SW-01" in item["tech_ids"])
        quote = paper["quote_options"]["Q001"]
        claim = Claim(
            tech_id="SW-01", domain_id=payload["analysis_context"]["domains"][0]["id"],
            group="operator", aspect="benefit", kind="paper_report", text=quote,
            condition="Limited to the supplied paper evidence", source_scope="direct",
            supports=[Support(evidence_id=paper["id"], quote=quote)])
        return Assessment(source_reviews=reviews, claims=[claim], summary=[], implications=[],
                          limitations=[], follow_up=[])


def execute(payload, **model_options):
    model = SourceRepairModel(**model_options)
    web = TwoPageWeb()
    state = run_detailed(payload, config=AgentConfig(repair_limit=1), model=model, web=web)
    StakeholderOutput.model_validate(state["output_json"])
    return state, model, web


def test_missing_source_review_alone_triggers_repair_and_supplies_exact_pending_ids(input_payload):
    state, model, web = execute(input_payload)
    first, second = model.analysis_payloads
    web_ids = [item["id"] for item in first["evidence"] if item["source_type"] == "web"]
    assert len(web_ids) == 2
    assert first["required_source_review_ids"] == web_ids
    assert second["required_source_review_ids"] == [web_ids[1]]
    assert second["mechanical_rejections"] == []
    assert second["feedback"]["rejected_claim_indices"] == []
    assert second["feedback"]["queries"] == []
    assert state["round"] == 1
    assert model.calls == ["ResearchPlan", "Assessment", "Review", "Assessment", "Review"]
    assert state["budget"].used == {"llm": 5, "search": 2, "fetch": 2}
    assert len(web.search_calls) == 2
    assert state["pending_source_ids"] == []
    assert not any(gap.startswith("출처 검토 미완료:") for gap in state["gaps"])


def test_pending_review_repair_skips_new_web_search_requested_by_reviewer(input_payload):
    state, model, web = execute(input_payload, request_search=True)
    assert model.analysis_payloads[1]["feedback"]["queries"]
    assert len(web.search_calls) == len(web.fetch_calls) == 2
    assert not any("additional deployment" in query for query in web.search_calls)
    assert state["budget"].used["llm"] == 5


def test_previous_completed_source_audit_survives_omission_from_repair_response(input_payload):
    state, model, _ = execute(input_payload)
    repair_sources = [item for item in model.analysis_payloads[1]["evidence"]
                      if item["source_type"] == "web"]
    earlier, pending = repair_sources
    assert earlier["audit"]["decision"] == "use"
    assert pending["audit"]["decision"] == "hold"
    assert [review.evidence_id for review in state["draft"].source_reviews] == [pending["id"]]
    assert state["evidence"][earlier["id"]].audit == earlier["audit"]
    assert state["evidence"][pending["id"]].audit["decision"] == "use"


def test_unresolved_review_stays_partial_after_five_calls_without_dropping_valid_paper_claim(input_payload):
    state, model, _ = execute(input_payload, resolve_pending=False, request_search=True)
    assert len(model.analysis_payloads) == 2
    assert state["round"] == 1
    assert state["budget"].used["llm"] == 5
    assert state["execution_status"] == state["status"] == "partial"
    assert state["review_succeeded"] is True
    assert state["rejected"] == []
    assert len(state["pending_source_ids"]) == 1
    pending = state["pending_source_ids"][0]
    assert any(pending in gap and gap.startswith("출처 검토 미완료:") for gap in state["gaps"])
    output = state["output_json"]
    # The shared contract separates pipeline completion from evidence completeness.
    assert output["execution_status"] == "completed"
    assert output["status"] == "partial"
    assert any(pending in json.dumps(error, ensure_ascii=False) for error in output["errors"])
    claims = output["result"]["by_technology"]["SW-01"]["claims"]
    assert len(claims) == 1
    assert claims[0]["kind"] == "paper_report"
    assert all(reference["evidence_id"] != pending for reference in output["references"])


@pytest.mark.parametrize("llm_limit", [3, 4])
def test_repair_is_not_started_without_budget_for_both_analysis_and_final_review(input_payload, llm_limit):
    input_payload["budget"]["llm"] = llm_limit
    state, model, web = execute(input_payload)
    assert len(model.analysis_payloads) == 1
    assert state["round"] == 0
    assert state["budget"].used["llm"] == 3
    assert state["pending_source_ids"]
    assert state["execution_status"] == "partial"
    assert len(web.search_calls) == 2
