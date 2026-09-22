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
                 mode: str = "live") -> AgentState:
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
                    mode: str = "live") -> dict:
    """Return a JSON-serializable stakeholder result, including failure diagnostics."""
    return run_detailed(input_json, request=request, as_of=as_of, run_id=run_id,
                        config=config, model=model, web=web, mode=mode)["output_json"]
