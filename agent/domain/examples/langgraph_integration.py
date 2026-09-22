"""Minimal integration example. The team's full graph supplies the technical node."""

import os

from langgraph.graph import END, START, StateGraph

from kv_domain_agent.node import make_domain_node
from kv_domain_agent.state import GraphState


def build_graph():
    builder = StateGraph(GraphState)

    # In the six-agent project, connect the existing technical node here.
    builder.add_node(
        "domain",
        make_domain_node(model_name=os.getenv("DOMAIN_AGENT_MODEL", "gpt-4.1-mini")),
    )
    builder.add_edge(START, "domain")
    builder.add_edge("domain", END)
    return builder.compile()


if __name__ == "__main__":
    raise SystemExit("Import build_graph() from the team project and invoke it with shared state.")

