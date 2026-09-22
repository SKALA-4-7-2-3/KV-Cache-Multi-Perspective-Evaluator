"""Core evaluator with strict evidence-bound post-validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError

from .models import (
    Basis,
    CriterionAssessment,
    DomainAgentOutput,
    DomainConfig,
    DomainCriterion,
    DomainStateInput,
    Evidence,
    Judgment,
    REQUIRED_CRITERIA,
    RoleStatus,
    TargetAlignment,
    TechnicalAssessment,
    TechnologyDomainAssessment,
)
from .prompt import SYSTEM_PROMPT


class DomainAgentError(RuntimeError):
    """Base error for predictable agent failures."""


class InputContractError(DomainAgentError):
    """The shared state does not satisfy the documented input contract."""


class OutputContractError(DomainAgentError):
    """The model returned structurally valid but evidence-invalid output."""


class Invokable(Protocol):
    def invoke(self, input: Any) -> Any: ...


@dataclass(frozen=True)
class PreparedInput:
    domain: DomainConfig
    technical: TechnicalAssessment
    evidence: dict[str, Evidence]
    missing_evidence_ids: tuple[str, ...]
    round: int

    @property
    def technology_ids(self) -> tuple[str, ...]:
        return tuple(item.technology_id for item in self.technical.technologies)

    def as_payload(self) -> dict[str, Any]:
        shared_ids = set(self.domain.shared_evidence_ids) & set(self.evidence)
        allowed_by_technology = {
            technology.technology_id: sorted(
                (set(technology.evidence_ids) | shared_ids) & set(self.evidence)
            )
            for technology in self.technical.technologies
        }
        return {
            "domain": self.domain.model_dump(mode="json"),
            "technical": self.technical.model_dump(mode="json"),
            "evidence": {
                key: value.model_dump(mode="json") for key, value in self.evidence.items()
            },
            "allowed_evidence_ids": sorted(self.evidence),
            "allowed_evidence_ids_by_technology": allowed_by_technology,
            "missing_evidence_ids": list(self.missing_evidence_ids),
            "round": self.round,
        }


def _alias_evidence_payload(prepared: PreparedInput) -> tuple[dict[str, Any], dict[str, str]]:
    """Expose short, reversible IDs to the model without changing source records."""
    prefix = "SRC"
    while any(evidence_id.startswith(prefix) for evidence_id in prepared.evidence):
        prefix = "_" + prefix
    aliases = {evidence_id: f"{prefix}{index:04d}"
               for index, evidence_id in enumerate(sorted(prepared.evidence), 1)}

    def replace(value: Any) -> Any:
        if isinstance(value, str):
            # Experimental conditions can contain serialized JSON references.
            for original in sorted(aliases, key=len, reverse=True):
                value = value.replace(original, aliases[original])
            return value
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {aliases.get(key, key): replace(item) for key, item in value.items()}
        return value

    return replace(prepared.as_payload()), {alias: original for original, alias in aliases.items()}


def _prepare_state(raw_state: dict[str, Any]) -> PreparedInput:
    try:
        state = DomainStateInput.model_validate(raw_state)
        raw_domain = state.config.get("domain")
        if not isinstance(raw_domain, dict):
            raise InputContractError("config.domain must be an object")
        domain = DomainConfig.model_validate(raw_domain)

        raw_technical = state.assessments.get("technical")
        if not isinstance(raw_technical, dict):
            raise InputContractError("assessments.technical must be an object")
        technical = TechnicalAssessment.model_validate(raw_technical)

        registry: dict[str, Evidence] = {}
        for key, raw_item in state.evidence.items():
            item = Evidence.model_validate(raw_item)
            if key != item.id:
                raise InputContractError(
                    f"evidence registry key {key!r} does not match item.id {item.id!r}"
                )
            registry[key] = item
    except InputContractError:
        raise
    except (ValidationError, TypeError, ValueError) as exc:
        raise InputContractError(str(exc)) from exc

    requested_ids: set[str] = set(domain.shared_evidence_ids)
    for technology in technical.technologies:
        requested_ids.update(technology.evidence_ids)

    selected = {key: registry[key] for key in sorted(requested_ids) if key in registry}
    missing = tuple(sorted(requested_ids - set(registry)))
    round_number = int(state.review.get("round", 0))
    return PreparedInput(domain, technical, selected, missing, round_number)


def _unknown_output(prepared: PreparedInput, reason: str) -> DomainAgentOutput:
    requirements = {item.criterion_id: item for item in prepared.domain.requirements}
    assessments: list[TechnologyDomainAssessment] = []
    for technology in prepared.technical.technologies:
        criteria = [
            CriterionAssessment(
                criterion_id=criterion,
                judgment=Judgment.UNKNOWN,
                target_alignment=TargetAlignment.UNKNOWN,
                conclusion="공유된 근거만으로 판단할 수 없습니다.",
                rationale=reason,
                conditions=[requirements[criterion].target],
                evidence_ids=[],
                basis=Basis.NONE,
                gaps=[reason],
                need_more=[f"{criterion.value} 목표와 동일 조건의 측정 근거"],
            )
            for criterion in REQUIRED_CRITERIA
        ]
        assessments.append(
            TechnologyDomainAssessment(
                technology_id=technology.technology_id,
                technology_name=technology.name,
                status=RoleStatus.UNKNOWN,
                criteria=criteria,
                overall_summary="근거 부족으로 도메인 적합성을 판단 보류합니다.",
                key_tradeoffs=[],
            )
        )
    return DomainAgentOutput(
        round=prepared.round,
        status=RoleStatus.UNKNOWN,
        domain_name=prepared.domain.name,
        assessments=assessments,
        unresolved_questions=[reason],
        disclaimer="공개·공유 근거 기반의 조건부 평가이며 실제 배포 검증이 아닙니다.",
    )


def failed_output(raw_state: dict[str, Any], message: str) -> DomainAgentOutput:
    """Create a schema-valid failure result without claiming a technical failure."""

    config = raw_state.get("config", {}) if isinstance(raw_state, dict) else {}
    domain = config.get("domain", {}) if isinstance(config, dict) else {}
    domain_name = domain.get("name", "장문맥 문서 QA 데이터센터·클라우드 서빙")
    technical = raw_state.get("assessments", {}).get("technical", {}) if isinstance(raw_state, dict) else {}
    raw_technologies = technical.get("technologies", []) if isinstance(technical, dict) else []
    technologies: list[tuple[str, str]] = []
    for item in raw_technologies:
        if isinstance(item, dict) and item.get("technology_id"):
            technologies.append((str(item["technology_id"]), str(item.get("name", item["technology_id"]))))
    if not technologies:
        technologies = [("SW-01", "RDKV"), ("HW-01", "Photonic-CXL")]

    criteria = [
        CriterionAssessment(
            criterion_id=criterion,
            judgment=Judgment.FAILED,
            target_alignment=TargetAlignment.UNKNOWN,
            conclusion="도메인 평가 에이전트 실행에 실패했습니다.",
            rationale=message,
            evidence_ids=[],
            basis=Basis.NONE,
            gaps=[message],
            need_more=[],
        )
        for criterion in REQUIRED_CRITERIA
    ]
    return DomainAgentOutput(
        status=RoleStatus.FAILED,
        domain_name=str(domain_name),
        assessments=[
            TechnologyDomainAssessment(
                technology_id=technology_id,
                technology_name=name,
                status=RoleStatus.FAILED,
                criteria=[item.model_copy(deep=True) for item in criteria],
                overall_summary="실행 실패와 기술 평가 결과를 구분해야 합니다.",
                key_tradeoffs=[],
            )
            for technology_id, name in technologies
        ],
        unresolved_questions=[message],
        disclaimer="에이전트 실행 실패이며 기술에 대한 부정적 평가가 아닙니다.",
    )


def _validate_output(output: DomainAgentOutput, prepared: PreparedInput) -> DomainAgentOutput:
    expected_tech_ids = set(prepared.technology_ids)
    actual_tech_ids = {item.technology_id for item in output.assessments}
    if actual_tech_ids != expected_tech_ids or len(output.assessments) != 2:
        raise OutputContractError(
            f"technology mismatch: expected={sorted(expected_tech_ids)}, "
            f"actual={sorted(actual_tech_ids)}"
        )

    shared_ids = set(prepared.domain.shared_evidence_ids) & set(prepared.evidence)
    allowed_by_technology = {
        item.technology_id: (set(item.evidence_ids) | shared_ids) & set(prepared.evidence)
        for item in prepared.technical.technologies
    }
    for technology in output.assessments:
        expected_name = next(
            item.name
            for item in prepared.technical.technologies
            if item.technology_id == technology.technology_id
        )
        technology.technology_name = expected_name
        allowed = allowed_by_technology[technology.technology_id]
        for item in technology.criteria:
            unknown_ids = set(item.evidence_ids) - allowed
            if unknown_ids:
                raise OutputContractError(
                    f"{technology.technology_id}/{item.criterion_id.value}: "
                    f"evidence ids are not allowed for this technology: {sorted(unknown_ids)}"
                )
            if item.judgment in {
                Judgment.FAVORABLE,
                Judgment.CONDITIONAL,
                Judgment.UNFAVORABLE,
            } and not item.evidence_ids:
                raise OutputContractError(
                    f"{technology.technology_id}/{item.criterion_id.value}: "
                    f"{item.judgment.value} requires evidence"
                )
            if item.judgment == Judgment.FAVORABLE and item.target_alignment != TargetAlignment.MATCHED:
                raise OutputContractError("favorable requires target_alignment=matched")
            if item.judgment == Judgment.UNFAVORABLE and item.target_alignment != TargetAlignment.CONFLICT:
                raise OutputContractError("unfavorable requires target_alignment=conflict")
            if item.judgment == Judgment.FAILED:
                raise OutputContractError("the model may not emit failed; runtime owns failure state")

        # Status is derived from criterion results rather than trusted to the model.
        if all(
            item.judgment in {Judgment.UNKNOWN, Judgment.NOT_APPLICABLE}
            for item in technology.criteria
        ):
            technology.status = RoleStatus.UNKNOWN
        else:
            technology.status = RoleStatus.COMPLETED

    output.round = prepared.round
    output.domain_name = prepared.domain.name
    if all(item.status == RoleStatus.UNKNOWN for item in output.assessments):
        output.status = RoleStatus.UNKNOWN
    else:
        output.status = RoleStatus.COMPLETED
    return output


class DomainEvaluator:
    """One-call domain evaluator. It deliberately owns no retriever or search tool."""

    def __init__(self, structured_model: Invokable, *, allow_demo: bool = False):
        self.structured_model = structured_model
        self.allow_demo = allow_demo

    def evaluate(self, state: dict[str, Any]) -> DomainAgentOutput:
        prepared = _prepare_state(state)
        demo_ids = sorted(key for key, item in prepared.evidence.items() if item.is_demo)
        if demo_ids and not self.allow_demo:
            raise InputContractError(
                "demo evidence is blocked in real execution; provide technical agent outputs "
                f"or use mock mode: {demo_ids}"
            )
        if not prepared.evidence:
            return _unknown_output(
                prepared,
                "기술 조사 에이전트가 전달한 사용 가능한 근거가 없습니다.",
            )

        payload, original_ids = _alias_evidence_payload(prepared)
        messages = [
            ("system", SYSTEM_PROMPT + "\n근거 ID는 이번 입력의 짧은 별칭이다. "
             "evidence_ids에는 allowed_evidence_ids_by_technology의 별칭을 그대로 사용한다. "
             "원래의 긴 ID를 재구성하지 않는다."),
            ("human", json.dumps(payload, ensure_ascii=False, indent=2)),
        ]
        try:
            raw_output = self.structured_model.invoke(messages)
            output = (
                raw_output
                if isinstance(raw_output, DomainAgentOutput)
                else DomainAgentOutput.model_validate(raw_output)
            )
        except ValidationError as exc:
            raise OutputContractError(str(exc)) from exc
        output = output.model_copy(deep=True)
        for technology in output.assessments:
            for item in technology.criteria:
                item.evidence_ids = [original_ids.get(evidence_id, evidence_id)
                                     for evidence_id in item.evidence_ids]
        return _validate_output(output, prepared)


def create_openai_structured_model(
    model_name: str = "gpt-4.1-mini",
    *,
    timeout: float = 60.0,
    max_retries: int = 1,
) -> Invokable:
    """Build the only external call used by this agent: an LLM, with no tools bound."""

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise DomainAgentError(
            "Install the OpenAI extra: pip install -e '.[openai]'"
        ) from exc

    llm = ChatOpenAI(
        model=model_name,
        temperature=0,
        timeout=timeout,
        max_retries=max_retries,
    )
    return llm.with_structured_output(
        DomainAgentOutput,
        method="json_schema",
        strict=True,
    )


def evaluate_domain_state(
    state: dict[str, Any],
    *,
    structured_model: Invokable | None = None,
    model_name: str = "gpt-4.1-mini",
    allow_demo: bool = False,
) -> DomainAgentOutput:
    model = structured_model or create_openai_structured_model(model_name)
    return DomainEvaluator(model, allow_demo=allow_demo).evaluate(state)
