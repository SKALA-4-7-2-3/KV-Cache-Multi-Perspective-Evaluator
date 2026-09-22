"""LangGraph-compatible node factory."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from .agent import DomainEvaluator, create_openai_structured_model, failed_output


def _error_id(round_number: int, error: Exception) -> str:
    digest = hashlib.sha256(str(error).encode("utf-8")).hexdigest()[:10]
    return f"domain:r{round_number}:{type(error).__name__}:{digest}"


def make_domain_node(
    *,
    structured_model: Any | None = None,
    model_name: str = "gpt-4.1-mini",
    allow_demo: bool = False,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a node that writes only assessments['domain'] and errors.

    No retriever, vector store, web search, or tool is created or bound here.
    """

    evaluator: DomainEvaluator | None = None

    def domain_node(state: dict[str, Any]) -> dict[str, Any]:
        nonlocal evaluator
        round_number = int(state.get("review", {}).get("round", 0))
        try:
            if evaluator is None:
                model = structured_model or create_openai_structured_model(model_name)
                evaluator = DomainEvaluator(model, allow_demo=allow_demo)
            result = evaluator.evaluate(state)
            return {"assessments": {"domain": result.model_dump(mode="json")}}
        except Exception as exc:  # A graph node must converge with an explicit failure state.
            result = failed_output(state, str(exc))
            error_id = _error_id(round_number, exc)
            return {
                "assessments": {"domain": result.model_dump(mode="json")},
                "errors": {
                    error_id: {
                        "id": error_id,
                        "role": "domain",
                        "round": round_number,
                        "type": type(exc).__name__,
                        "retryable": type(exc).__name__ not in {"InputContractError"},
                        "message": str(exc),
                    }
                },
            }

    return domain_node
