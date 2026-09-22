"""Legacy Markdown compatibility API. New integrations use stakeholder_agent.run_stakeholder."""

from .config import AgentConfig
from .models import AgentState


def run_detailed(input_md: str, *, config: AgentConfig | None = None,
                 model=None, web=None, mode: str = "live") -> AgentState:
    """Run with optional injected providers; expose diagnostics for tests and local debugging."""
    if not isinstance(input_md, str):
        raise TypeError("input_md must be a Markdown string")
    if mode not in ("live", "fixture"):
        raise ValueError("mode must be live or fixture")
    config = config or AgentConfig.from_env()
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
    graph = build_graph(config, model, web)
    return graph.invoke({"input_md": input_md, "mode": mode}, {"recursion_limit": 20})


def run_stakeholder(input_md: str, *, config: AgentConfig | None = None,
                    model=None, web=None, mode: str = "live") -> str:
    """Return one self-contained Markdown report; operational failures are reported in its status."""
    return run_detailed(input_md, config=config, model=model, web=web, mode=mode)["output_md"]
