"""Small control contracts. Paper text and role results live in artifacts."""
from __future__ import annotations

from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .research_input import CRITERIA as DOMAIN_CRITERIA
from market_agent.schemas import CRITERIA as MARKET_CRITERIA

CATALOG_VERSION = "perspectives-1.0"
CATALOG = {"domain": tuple(DOMAIN_CRITERIA), "stakeholders": ("stakeholder_impact",),
           "market": tuple(MARKET_CRITERIA)}
TECHNOLOGIES = ("SW-01", "HW-01")
Role = Literal["domain", "stakeholders", "market"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Cell(Contract):
    technology_id: Literal["SW-01", "HW-01"]
    criterion_id: str


class TaskSpec(Contract):
    task_id: str
    plan_revision: int = Field(ge=1)
    role: Role
    active_cells: list[Cell] = Field(min_length=1)
    technology_ids: list[str]
    criterion_ids: list[str]
    reason: str
    operation: Literal["assess", "reassess"]
    dependency_ids: list[str] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_scope(self):
        cells = {(c.technology_id, c.criterion_id) for c in self.active_cells}
        if len(cells) != len(self.active_cells) or any(c not in CATALOG[self.role] for _,c in cells):
            raise ValueError("Unknown or duplicated task cells")
        if set(self.technology_ids) != {t for t,c in cells} or set(self.criterion_ids) != {c for t,c in cells}:
            raise ValueError("Task scope aliases disagree")
        return self


def merge_outcomes(left, right):
    merged = dict(left or {})
    for key, value in (right or {}).items():
        if key in merged and merged[key] != value:
            raise ValueError(f"Conflicting outcome for the same task attempt: {key}")
        merged[key] = value
    return merged


class GraphState(TypedDict, total=False):
    run_id: str
    input_refs: dict
    plan_revision: int
    tasks: list[dict]
    task_outcomes: Annotated[dict, merge_outcomes]
    accepted_refs: dict
    accepted_validity: dict
    pending_cells: list[dict]
    feedback: list[dict]
    review_ref: dict
    review_input_ref: dict
    report_ref: dict
    quality_ref: dict
    quality_attempt: int
    replan_count: int
    phase: str
    termination_reason: str | None


def all_cells(roles=None):
    return [{"role": role, "technology_id": tech, "criterion_id": criterion}
            for role in (CATALOG if roles is None else roles) for tech in TECHNOLOGIES for criterion in CATALOG[role]]
