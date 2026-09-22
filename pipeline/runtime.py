"""Actual downstream calls with explicit inputs and portable JSON outputs."""

from dataclasses import replace
from datetime import date
import json
import os


def run_domain(state, *, model):
    from kv_domain_agent.agent import create_openai_structured_model
    from kv_domain_agent.node import make_domain_node
    provider = create_openai_structured_model(model, timeout=120, max_retries=1)
    return make_domain_node(structured_model=provider)(state)


def run_stakeholders(papers, request, *, run_id, as_of, model):
    from stakeholder_agent.agent import run_stakeholder
    from stakeholder_agent.config import AgentConfig
    defaults = AgentConfig.from_env()
    input_chars = len(json.dumps(papers, ensure_ascii=False)) + len(json.dumps(request, ensure_ascii=False))
    config = replace(defaults, model=model, model_timeout=120,
                     max_input_chars=max(defaults.max_input_chars, input_chars))
    return run_stakeholder(
        papers, request=request, run_id=run_id, as_of=as_of,
        config=config, mode="live",
    )


def run_market(papers, request, *, as_of, model):
    from market_agent.json_input import parse_paper_analyses
    from market_agent.node import parent_update, run_market as evaluate
    from market_agent.providers import OpenAIAnalyst
    from market_agent.tools import TavilyWeb
    domains = request.get("domains", [])
    domain = "; ".join(f"{d['name']}: {d.get('scenario', '')}" for d in domains)
    data = parse_paper_analyses(
        papers, as_of=date.fromisoformat(as_of), domain=domain or "클라우드 데이터센터",
    )
    web = TavilyWeb(os.environ.get("TAVILY_API_KEY", ""))
    analyst = OpenAIAnalyst(os.environ.get("OPENAI_API_KEY", ""), model, debug=False)
    try:
        state = evaluate(data, web, analyst, mode="live", auto_repair=True)
        return {
            "result": state["result"].model_dump(mode="json"),
            "evidence": {k: v.model_dump(mode="json") for k, v in state["evidence"].items()},
            "claims": {k: v.model_dump(mode="json") for k, v in state.get("claim_pool", {}).items()},
            "retained_draft_findings": state.get("retained_draft_findings", []),
            "review_notes": state.get("review_notes", []),
            "parent_update": parent_update(state),
            "queries": state["queries"], "events": state["events"],
            "model": state["model"], "token_usage": state["token_usage"],
        }
    finally:
        web.close()
        analyst.close()
