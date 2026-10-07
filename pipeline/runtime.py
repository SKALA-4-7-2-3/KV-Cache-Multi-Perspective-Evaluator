"""Actual downstream calls with explicit inputs and portable JSON outputs."""

from dataclasses import replace
from datetime import date
import json
import os


# Allow all three research levels in the upstream adaptive market engine.
MARKET_LIMITS = {"search": 18, "extract": 24, "llm": 10}


def run_domain(state, *, model, scoped=False):
    from kv_domain_agent.agent import create_openai_structured_model
    from kv_domain_agent.models import DomainAgentOutput, ScopedDomainAgentOutput
    from kv_domain_agent.node import make_domain_node
    provider = create_openai_structured_model(model, timeout=120, max_retries=0,
        output_schema=ScopedDomainAgentOutput if scoped else DomainAgentOutput)
    return make_domain_node(structured_model=provider)(state)


def run_stakeholders(papers, request, *, run_id, as_of, model, active_cells=None,
                     feedback=None, prior=None):
    from stakeholder_agent.agent import run_stakeholder
    from stakeholder_agent.config import AgentConfig
    defaults = AgentConfig.from_env()
    input_chars = len(json.dumps(papers, ensure_ascii=False)) + len(json.dumps(request, ensure_ascii=False))
    config = replace(defaults, model=model, model_timeout=120,
                     max_input_chars=max(defaults.max_input_chars, input_chars))
    payload = papers
    if prior:
        usage = prior.get("usage", {}).get("used", {})
        payload = {"schema_version": "1.0", "role": "stakeholders", "run_id": run_id,
                   "paper_analyses": papers, "request": request, "config": {"as_of": as_of},
                   "round": int(prior.get("round", 0)) + 1,
                   "budget": {"llm": defaults.llm_limit, "search": defaults.search_limit,
                              "fetch": defaults.fetch_limit}, "usage": usage}
    scope = None
    if active_cells:
        scope = {"technology_ids": sorted({t for t, _ in active_cells}), "feedback": feedback or [],
                 "prior": prior}
    return run_stakeholder(payload, request=None if isinstance(payload, dict) else request,
        run_id=None if isinstance(payload, dict) else run_id, as_of=None if isinstance(payload, dict) else as_of,
        config=config, mode="live", scope=scope)


def run_market(papers, request, *, as_of, model, active_cells=None, feedback=None, prior=None):
    from market_agent.json_input import parse_paper_analyses
    from market_agent.node import parent_update, run_market as evaluate
    from market_agent.providers import OpenAIAnalyst
    from market_agent.schemas import Limits
    from market_agent.tools import TavilyWeb
    domains = request.get("domains", [])
    domain = "; ".join(f"{d['name']}: {d.get('scenario', '')}" for d in domains)
    domain = "\n".join(part for part in (request.get("original_request"), domain) if part)
    data = parse_paper_analyses(
        papers, as_of=date.fromisoformat(as_of), domain=domain or "클라우드 데이터센터",
        limits=Limits(**MARKET_LIMITS),
    )
    web = TavilyWeb(os.environ.get("TAVILY_API_KEY", ""))
    analyst = OpenAIAnalyst(os.environ.get("OPENAI_API_KEY", ""), model, debug=False)
    try:
        previous = None
        existing_evidence = existing_claims = previous_progress = None
        if prior:
            from market_agent.schemas import Analysis, Evidence, Claim
            previous = Analysis.model_validate({"assessments": prior.get("result", {}).get("assessments", []),
                                                "followup_questions": []})
            existing_evidence = {k: Evidence.model_validate(v) for k, v in prior.get("evidence", {}).items()}
            existing_claims = {k: Claim.model_validate(v) for k, v in prior.get("claims", {}).items()}
            previous_progress = prior.get("result", {}).get("progress")
        state = evaluate(data, web, analyst, mode="live", auto_repair=True,
            # Market's internal protocol has only initial/broadened rounds. Parent
            # plan_revision remains in worker metadata and may advance further.
            round_number=min(1, int(prior.get("result", {}).get("round", 0)) + 1) if prior else 0,
            previous=previous, existing_evidence=existing_evidence,
            existing_claims=existing_claims, previous_progress=previous_progress,
            active_cells=active_cells, feedback=feedback)
        return {
            "result": state["result"].model_dump(mode="json"),
            "evidence": {k: v.model_dump(mode="json") for k, v in state["evidence"].items()},
            "sources": state.get("sources", {}),
            "claims": {k: v.model_dump(mode="json") for k, v in state.get("claim_pool", {}).items()},
            "retained_draft_findings": state.get("retained_draft_findings", []),
            "review_notes": state.get("review_notes", []),
            "parent_update": parent_update(state),
            "queries": state["queries"], "events": state["events"],
            "model": state["model"], "token_usage": state["token_usage"],
            "limits": data.limits.model_dump(mode="json"),
            "history": state.get("history", []),
        }
    finally:
        web.close()
        analyst.close()
