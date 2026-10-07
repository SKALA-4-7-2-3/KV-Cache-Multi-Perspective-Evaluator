"""JSON-only public API; legacy Markdown support lives in ``legacy``."""

from __future__ import annotations

import json
import re
from dataclasses import replace

from .config import AgentConfig
from .contracts import InputError
from .models import AgentState


def _failure_header(data, *, run_id=None):
    """Preserve independently valid accounting even when the research body fails."""
    from .json_input import _json_data
    try:
        data = _json_data(data, "입력")
    except InputError:
        data = {}
    data = data if isinstance(data, dict) else {}
    identifier = run_id if run_id is not None else data.get("run_id")
    safe_id = identifier if isinstance(identifier, str) and re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", identifier) else "unavailable"
    number = data.get("round", 0)
    number = number if type(number) is int and number >= 0 else 0

    def counts(name):
        source = data.get(name, {})
        if not isinstance(source, dict):
            return {}
        return {key: value for key, value in source.items()
                if key in {"llm", "search", "fetch"} and type(value) is int and value >= 0}

    return {"error_run_id": safe_id, "outer_round": number,
            "initial_usage": counts("usage"), "initial_budget": counts("budget")}


def run_detailed(input_json, *, request=None, as_of=None, run_id=None,
                 config: AgentConfig | None = None, model=None, web=None,
                 mode: str = "live", scope: dict | None = None) -> AgentState:
    """Run two paper-analysis JSONs with request context, returning private diagnostics.

    ``input_json`` is an envelope, a JSON string, or a list of two paper objects.
    No source_path in the papers is opened. Input is validated before providers run.
    For the portable JSON result use ``run_stakeholder``.
    """
    from .json_input import parse_json_input
    from .json_output import render_json_output

    if mode not in ("live", "fixture"):
        raise ValueError("mode must be live or fixture")
    supplied_config = config is not None
    config = config or AgentConfig.from_env()
    normalized = None
    try:
        serialized = input_json if isinstance(input_json, str) else json.dumps(input_json, ensure_ascii=False)
        request_text = request if isinstance(request, str) else json.dumps(request, ensure_ascii=False)
        if len(serialized) + len(request_text) > config.max_input_chars:
            raise InputError("입력 JSON이 허용 크기를 넘었습니다.")
        normalized = parse_json_input(input_json, request=request, as_of=as_of, run_id=run_id)
        if scope:
            selected = set(scope.get("technology_ids", []))
            known = {item.id for item in normalized.parsed.technologies}
            if not selected or not selected <= known:
                raise InputError("scope.technology_ids must select known technologies")
            normalized.parsed.technologies = [item for item in normalized.parsed.technologies
                                              if item.id in selected]
            normalized.parsed.evidence = {key: item for key, item in normalized.parsed.evidence.items()
                                          if selected.intersection(item.tech_ids)}
            feedback = [str(item) for item in scope.get("feedback", []) if str(item).strip()]
            prior = scope.get("prior") if isinstance(scope.get("prior"), dict) else None
            if prior:
                from .models import Evidence
                for key, row in prior.get("evidence", {}).items():
                    technology_ids = row.get("technology_ids", [])
                    if key in normalized.parsed.evidence or not selected.intersection(technology_ids):
                        continue
                    normalized.parsed.evidence[key] = Evidence(
                        id=key, tech_ids=list(technology_ids), title=str(row.get("title", key)),
                        url=str(row.get("url", "")), location=str(row.get("location", "")),
                        excerpt=str(row.get("excerpt", "")), publisher=str(row.get("publisher", "미표기")),
                        published_at=str(row.get("published_at", "미표기")),
                        retrieved_at=str(row.get("retrieved_at", "미표기")),
                        source_type=str(row.get("source_type", "web")), scope=str(row.get("scope", "direct")),
                        author=str(row.get("author", "미표기")), requested_url=str(row.get("requested_url", "")),
                        metadata_provenance=dict(row.get("metadata_provenance", {})),
                        search_queries=list(row.get("search_queries", [])),
                        content_sha256=str(row.get("collected_content_sha256", "")), audit=dict(row.get("audit", {})))
                prior_cells = {tech: prior.get("result", {}).get("by_technology", {}).get(tech)
                               for tech in selected if tech in prior.get("result", {}).get("by_technology", {})}
            else:
                prior_cells = {}
            if feedback or prior_cells:
                normalized.parsed.analysis_context.additional_context = "\n".join(filter(None, (
                    normalized.parsed.analysis_context.additional_context,
                    ("선택된 기술 셀에 대한 상위 검토 feedback:\n- " + "\n- ".join(feedback)) if feedback else "",
                    ("이전 accepted 셀(JSON, 새 근거와 feedback에 따라 필요한 부분만 재평가):\n" +
                     json.dumps(prior_cells, ensure_ascii=False)) if prior_cells else "",
                )))
        # Credentials/endpoints are never loaded from upstream document data.
        if not supplied_config:
            settings = getattr(normalized, "config", {})
            allowed = ("model", "model_timeout", "tool_timeout", "repair_limit")
            config = replace(config, **{key: settings[key] for key in allowed if key in settings})
    except (InputError, TypeError, ValueError) as exc:
        message = str(exc) if isinstance(exc, InputError) else f"JSON 입력 또는 설정 오류 ({type(exc).__name__})"
        state = {"mode": mode, "status": "failed", "execution_status": "failed",
                 "errors": [message], "trace": ["prepare"], "review_succeeded": False,
                 **_failure_header(input_json, run_id=run_id)}
        state["output_json"] = render_json_output(state, normalized, config=config, mode=mode,
                                                   input_error=message)
        return state

    if mode == "fixture":
        from .demo import DemoModel, DemoWeb
        model = model or DemoModel()
        web = web or DemoWeb()
    else:
        from .providers import OpenAIModel, TavilyExtractWeb
        if model is None and config.openai_api_key:
            model = OpenAIModel(model=config.model, api_key=config.openai_api_key,
                                base_url=config.base_url, timeout=config.model_timeout)
        if web is None and config.tavily_api_key:
            web = TavilyExtractWeb(api_key=config.tavily_api_key, timeout=config.tool_timeout,
                                   max_chars=config.page_chars)
    from .graph import build_graph
    from .providers import OpenAIModel
    model_label = config.model if isinstance(model, OpenAIModel) else f"{mode}:{type(model).__name__}"
    initial = {"normalized_input": normalized, "output_format": "json", "mode": mode,
               "initial_usage": normalized.usage}
    state = build_graph(config, model, web).invoke(initial, {"recursion_limit": 20})
    state["runtime_model_id"] = model_label
    state["output_json"] = render_json_output(state, normalized, config=config, mode=mode)
    return state


def run_stakeholder(input_json, *, request=None, as_of=None, run_id=None,
                    config: AgentConfig | None = None, model=None, web=None,
                    mode: str = "live", scope: dict | None = None) -> dict:
    """Return a JSON-serializable stakeholder result, including failure diagnostics."""
    return run_detailed(input_json, request=request, as_of=as_of, run_id=run_id,
                        config=config, model=model, web=web, mode=mode, scope=scope)["output_json"]
