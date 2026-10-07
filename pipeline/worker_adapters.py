"""Scoped worker boundaries for the root orchestrator.

Workers receive one validated task and return portable role output.  Only the
single-writer aggregator calls :func:`merge_role_result`.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


ROLE_CRITERIA = {
    "domain": {"capacity", "quality", "latency_predictability", "throughput",
               "gpu_compatibility", "dedicated_hardware_dependency",
               "deployment_complexity", "maturity", "customer_value", "domain_fit"},
    "market": {"market_size_growth", "commercialization", "adoption",
               "ecosystem_support", "standardization", "business_value"},
    "stakeholders": {"stakeholder_impact"},
}


def _cells(task: dict) -> list[tuple[str, str]]:
    role = task.get("role")
    if role not in ROLE_CRITERIA:
        raise ValueError("unknown worker role")
    rows = task.get("active_cells") or []
    cells = [(row.get("technology_id"), row.get("criterion_id")) for row in rows]
    if not cells or len(cells) != len(set(cells)):
        raise ValueError("active_cells must be a non-empty unique list")
    technologies = set(task.get("technology_ids") or [])
    criteria = set(task.get("criterion_ids") or [])
    for technology, criterion in cells:
        if technology not in {"SW-01", "HW-01"} or criterion not in ROLE_CRITERIA[role]:
            raise ValueError("active_cells contains an unsupported cell")
        if technologies and technology not in technologies:
            raise ValueError("active_cells is outside technology_ids")
        if criteria and criterion not in criteria:
            raise ValueError("active_cells is outside criterion_ids")
    return cells


def _usage(output: dict, prior: dict | None = None) -> dict:
    if isinstance(output.get("usage"), dict) and "used" in output["usage"]:
        return output["usage"]
    result = output.get("result", {})
    used = result.get("usage", {}) if isinstance(result, dict) else {}
    previous = (prior or {}).get("result", {}).get("usage", {})
    return {"used": deepcopy(used),
            "delta": {key: max(0, value - previous.get(key, 0)) for key, value in used.items()}}


def _governance_snapshot() -> tuple[object | None, set[str]]:
    try:
        from . import governance
        ledger = governance._ledger
        return ledger, set(ledger.snapshot()["calls"]) if ledger is not None else set()
    except (ImportError, KeyError):
        return None, set()


def _governance_delta(ledger: object, before: set[str], task_id: str) -> dict:
    snapshot = ledger.snapshot()
    calls = [call for call_id, call in snapshot["calls"].items()
             if call_id not in before and call.get("task_id") == task_id]
    delta = {kind: sum(call.get("kind") == kind for call in calls)
             for kind in ("llm", "search", "extract", "fetch")}
    tokens = sum(call.get("actual_tokens") if call.get("actual_tokens") is not None
                 else call.get("reserved_tokens", 0) for call in calls if call.get("kind") == "llm")
    return {"delta": delta, "tokens": tokens,
            "unconfirmed_calls": sum(call.get("status") == "unconfirmed" for call in calls)}


def _assert_cells_present(role: str, output: dict,
                          cells: set[tuple[str, str]]) -> None:
    """Reject a worker result that silently omits any assigned cell."""
    try:
        if role == "domain":
            rows = output["assessments"]["domain"]["assessments"]
            present = {(row["technology_id"], criterion["criterion_id"])
                       for row in rows for criterion in row["criteria"]}
        elif role == "market":
            present = {(row["tech_id"], row["criterion_id"])
                       for row in output["result"]["assessments"]}
        else:
            present = {(technology, "stakeholder_impact")
                       for technology in output["result"]["by_technology"]}
    except (KeyError, TypeError) as exc:
        raise ValueError(f"invalid {role} worker result") from exc
    missing = cells - present
    if missing:
        raise ValueError(f"incoming {role} result omitted requested cells: {sorted(missing)}")


def _refresh_domain_status(output: dict) -> None:
    """Derive aggregate status after replacing a subset of domain criteria."""
    for technology in output["assessments"]:
        judgments = [criterion.get("judgment") for criterion in technology["criteria"]]
        if judgments and all(judgment is not None for judgment in judgments):
            technology["status"] = (
                "unknown" if all(judgment in {"unknown", "not_applicable"}
                                 for judgment in judgments) else "completed"
            )
    output["status"] = (
        "unknown" if output["assessments"] and
        all(row.get("status") == "unknown" for row in output["assessments"])
        else "completed"
    )


def execute_worker(task: dict, bundle: dict, request: dict, *, run_id: str,
                   as_of: str, model: str, prior: dict | None = None) -> dict:
    """Execute only the requested cells and attach task correlation metadata."""
    cells = _cells(task)
    feedback = [str(item) for item in task.get("feedback", [])]
    role = task["role"]
    ledger, calls_before = _governance_snapshot()
    from .runtime import run_domain, run_market, run_stakeholders
    if role == "domain":
        from .research_input import to_domain_state
        state = to_domain_state(bundle, request, run_id=run_id, as_of=as_of)
        prior_domain = ((prior or {}).get("assessments", {}).get("domain", {}))
        prior_by_technology = {row.get("technology_id"): row
                               for row in prior_domain.get("assessments", [])}
        prior_cells = {}
        for technology, criterion in cells:
            row = prior_by_technology.get(technology, {})
            match = next((item for item in row.get("criteria", [])
                          if item.get("criterion_id") == criterion), None)
            if match is not None:
                prior_cells[f"{technology}/{criterion}"] = deepcopy(match)
        state.setdefault("review", {})["round"] = int(prior_domain.get("round", -1)) + 1 if prior else 0
        state["worker_scope"] = {"active_cells": [dict(technology_id=t, criterion_id=c)
                                                   for t, c in cells], "feedback": feedback,
                                 "prior_cells": prior_cells}
        output = run_domain(state, model=model, scoped=True)
        try:
            domain_output = output["assessments"]["domain"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("domain worker returned an invalid state delta") from exc
        if domain_output.get("status") == "failed":
            raise RuntimeError("domain worker execution failed")
    elif role == "stakeholders":
        output = run_stakeholders(bundle["papers"], request, run_id=run_id, as_of=as_of,
                                  model=model, active_cells=cells, feedback=feedback, prior=prior)
    else:
        output = run_market(bundle["papers"], request, as_of=as_of, model=model,
                            active_cells=cells, feedback=feedback, prior=prior)
    result = deepcopy(output)
    usage = (_governance_delta(ledger, calls_before, task["task_id"])
             if ledger is not None else _usage(output, prior))
    result["worker"] = {
        "task_id": task["task_id"], "plan_revision": task["plan_revision"],
        "role": role, "operation": task.get("operation", "assess"),
        "active_cells": [dict(technology_id=t, criterion_id=c) for t, c in cells],
        "usage": usage,
    }
    return result


def merge_role_result(role: str, prior: dict | None, incoming: dict,
                      active_cells: list[dict]) -> dict:
    """Replace requested cells while retaining every untouched prior cell verbatim."""
    cells = {(row["technology_id"], row["criterion_id"]) for row in active_cells}
    if role not in ROLE_CRITERIA or not cells:
        raise ValueError("invalid merge scope")
    _assert_cells_present(role, incoming, cells)
    if prior is None:
        return deepcopy(incoming)
    merged = deepcopy(prior)
    if role == "domain":
        try:
            old_output = merged["assessments"]["domain"]
            new_output = incoming["assessments"]["domain"]
        except (KeyError, TypeError) as exc:
            raise ValueError("domain results must use the portable state-delta wrapper") from exc
        old = {row["technology_id"]: row for row in old_output["assessments"]}
        new = {row["technology_id"]: row for row in new_output["assessments"]}
        for tech in {t for t, _ in cells}:
            target = old[tech]
            replacements = {row["criterion_id"]: row for row in new[tech]["criteria"]}
            target["criteria"] = [deepcopy(replacements.get(row["criterion_id"], row))
                                  if (tech, row["criterion_id"]) in cells else row
                                  for row in target["criteria"]]
        _refresh_domain_status(old_output)
    elif role == "market":
        old_rows = {(row["tech_id"], row["criterion_id"]): row
                    for row in merged["result"]["assessments"]}
        new_rows = {(row["tech_id"], row["criterion_id"]): row
                    for row in incoming["result"]["assessments"]}
        for cell in cells:
            old_rows[cell] = deepcopy(new_rows[cell])
        merged["result"]["assessments"] = list(old_rows.values())
    else:
        old = merged["result"]["by_technology"]
        new = incoming["result"]["by_technology"]
        for tech, criterion in cells:
            old[tech] = deepcopy(new[tech])
    for key in ("evidence", "new_evidence", "sources", "claims"):
        if isinstance(incoming.get(key), dict):
            merged[key] = {**merged.get(key, {}), **deepcopy(incoming[key])}
    if "worker" in incoming:
        merged["worker"] = deepcopy(incoming["worker"])
    return merged
