"""Reducers and a reference State schema for parallel LangGraph integration."""

from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any
from typing_extensions import TypedDict


def merge_strict_by_key(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Merge distinct keys; identical retries are idempotent; conflicts are rejected."""

    merged = deepcopy(left or {})
    for key, value in (right or {}).items():
        if key not in merged:
            merged[key] = deepcopy(value)
        elif merged[key] != value:
            raise ValueError(f"state merge conflict for key={key!r}")
    return merged


def _round_of(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    return int(value.get("round", value.get("_meta", {}).get("round", 0)))


def merge_role_assessments(
    left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    """Merge one writer per role, allowing only a strictly newer round to replace it."""

    merged = deepcopy(left or {})
    for role, result in (right or {}).items():
        if role not in merged:
            merged[role] = deepcopy(result)
            continue
        if merged[role] == result:
            continue
        old_round = _round_of(merged[role])
        new_round = _round_of(result)
        if new_round > old_round:
            merged[role] = deepcopy(result)
        else:
            raise ValueError(
                f"assessment conflict for role={role!r}: "
                f"existing round={old_round}, incoming round={new_round}"
            )
    return merged


class GraphState(TypedDict, total=False):
    config: dict[str, Any]
    documents: Annotated[dict[str, Any], merge_strict_by_key]
    evidence: Annotated[dict[str, Any], merge_strict_by_key]
    assessments: Annotated[dict[str, Any], merge_role_assessments]
    review: dict[str, Any]
    synthesis: dict[str, Any]
    report: dict[str, Any]
    errors: Annotated[dict[str, Any], merge_strict_by_key]

