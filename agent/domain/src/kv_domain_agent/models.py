"""Validated input and output contracts for the domain agent."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Judgment(str, Enum):
    FAVORABLE = "favorable"
    CONDITIONAL = "conditional"
    UNFAVORABLE = "unfavorable"
    UNKNOWN = "unknown"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class TargetAlignment(str, Enum):
    MATCHED = "matched"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class Basis(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    MIXED = "mixed"
    NONE = "none"


class RoleStatus(str, Enum):
    COMPLETED = "completed"
    UNKNOWN = "unknown"
    FAILED = "failed"


class DomainCriterion(str, Enum):
    CAPACITY = "capacity"
    QUALITY = "quality"
    LATENCY_PREDICTABILITY = "latency_predictability"
    THROUGHPUT = "throughput"
    GPU_COMPATIBILITY = "gpu_compatibility"
    DEDICATED_HARDWARE_DEPENDENCY = "dedicated_hardware_dependency"
    DEPLOYMENT_COMPLEXITY = "deployment_complexity"
    MATURITY = "maturity"
    CUSTOMER_VALUE = "customer_value"
    DOMAIN_FIT = "domain_fit"


REQUIRED_CRITERIA: tuple[DomainCriterion, ...] = tuple(DomainCriterion)


class DomainRequirement(StrictModel):
    criterion_id: DomainCriterion
    target: str = Field(min_length=1)
    priority: Literal["must", "should", "could"] = "should"
    rationale: str = ""


class DomainConfig(StrictModel):
    name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    target_users: list[str] = Field(min_length=1)
    requirements: list[DomainRequirement]
    shared_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_requirements(self) -> "DomainConfig":
        ids = [item.criterion_id for item in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("domain requirements contain duplicate criterion_id")
        missing = set(REQUIRED_CRITERIA) - set(ids)
        extra = set(ids) - set(REQUIRED_CRITERIA)
        if missing or extra:
            raise ValueError(
                "domain requirements must contain all 10 criteria exactly once; "
                f"missing={sorted(x.value for x in missing)}, "
                f"extra={sorted(x.value for x in extra)}"
            )
        return self


class Evidence(StrictModel):
    id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    location: str | None = None
    url: str | None = None
    conditions: list[str] = Field(default_factory=list)
    criterion_ids: list[DomainCriterion] = Field(default_factory=list)
    basis: Literal["direct", "inference"] = "direct"
    collected_at: str | None = None
    is_demo: bool = False


class TechnologyTechnicalSummary(StrictModel):
    technology_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    approach: Literal["SW", "HW"]
    summary: str = Field(min_length=1)
    experimental_conditions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class TechnicalAssessment(StrictModel):
    status: RoleStatus
    technologies: list[TechnologyTechnicalSummary]

    @model_validator(mode="after")
    def validate_technologies(self) -> "TechnicalAssessment":
        ids = [item.technology_id for item in self.technologies]
        if len(ids) != 2 or len(set(ids)) != 2:
            raise ValueError("technical assessment must contain two distinct technologies")
        return self


class CriterionAssessment(StrictModel):
    criterion_id: DomainCriterion
    judgment: Judgment
    target_alignment: TargetAlignment
    conclusion: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    conditions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    basis: Basis
    gaps: list[str] = Field(default_factory=list)
    need_more: list[str] = Field(default_factory=list)


class TechnologyDomainAssessment(StrictModel):
    technology_id: str = Field(min_length=1)
    technology_name: str = Field(min_length=1)
    status: RoleStatus
    criteria: list[CriterionAssessment]
    overall_summary: str = Field(min_length=1)
    key_tradeoffs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_criteria(self) -> "TechnologyDomainAssessment":
        ids = [item.criterion_id for item in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.technology_id}: duplicate criterion_id")
        missing = set(REQUIRED_CRITERIA) - set(ids)
        extra = set(ids) - set(REQUIRED_CRITERIA)
        if missing or extra:
            raise ValueError(
                f"{self.technology_id}: criteria must contain all 10 items exactly once; "
                f"missing={sorted(x.value for x in missing)}, "
                f"extra={sorted(x.value for x in extra)}"
            )
        return self


class DomainAgentOutput(StrictModel):
    role: Literal["domain"] = "domain"
    round: int = Field(default=0, ge=0)
    status: RoleStatus
    domain_name: str = Field(min_length=1)
    assessments: list[TechnologyDomainAssessment]
    cross_technology_tradeoffs: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    disclaimer: str = Field(min_length=1)


class DomainStateInput(StrictModel):
    """The state slice consumed by this agent, independent of LangGraph itself."""

    # The six-agent graph owns additional channels (documents, errors, report, ...).
    # This role validates its required slice and deliberately ignores the rest.
    model_config = ConfigDict(extra="ignore")

    config: dict[str, Any]
    evidence: dict[str, Any]
    assessments: dict[str, Any]
    review: dict[str, Any] = Field(default_factory=dict)
