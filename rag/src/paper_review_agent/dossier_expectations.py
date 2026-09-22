"""Golden expectation checks over the semantic content of technical dossiers.

The expectation file is deliberately separate from the general technical
contract.  It describes paper-specific acceptance checks without baking a
particular paper or metric into production validation code.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from paper_review_agent.technical_schemas import (
    TechnicalDossier,
    TechnicalResearchEnvelope,
)


class DossierExpectationError(ValueError):
    """Raised when an expectation file is invalid or an expectation is unmet."""


class _ExpectationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaperSelector(_ExpectationModel):
    paper_id_regex: str | None = None
    title_regex: str | None = None
    arxiv_id: str | None = None
    source_basename: str | None = None

    @model_validator(mode="after")
    def require_selector(self) -> "PaperSelector":
        if not any(
            (
                self.paper_id_regex,
                self.title_regex,
                self.arxiv_id,
                self.source_basename,
            )
        ):
            raise ValueError("at least one paper selector is required")
        _compile_optional_regex(self.paper_id_regex, "paper_id_regex")
        _compile_optional_regex(self.title_regex, "title_regex")
        return self


SemanticScope = Literal[
    "analysis",
    "claims",
    "critical_inventory",
    "experiment_observations",
    "unverified_items",
]


class SemanticExpectation(_ExpectationModel):
    expectation_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    description: str = Field(min_length=1)
    scopes: list[SemanticScope] = Field(
        default_factory=lambda: [
            "analysis",
            "claims",
            "critical_inventory",
            "experiment_observations",
        ],
        min_length=1,
    )
    match_within: Literal["record", "dossier"] = "record"
    all_of: list[str] = Field(min_length=1)
    any_of: list[str] = Field(default_factory=list)
    case_sensitive: bool = False

    @model_validator(mode="after")
    def validate_patterns(self) -> "SemanticExpectation":
        flags = 0 if self.case_sensitive else re.IGNORECASE
        for field_name, patterns in (("all_of", self.all_of), ("any_of", self.any_of)):
            for pattern in patterns:
                try:
                    re.compile(pattern, flags)
                except re.error as exc:
                    raise ValueError(
                        f"invalid regex in {field_name}: {pattern!r}: {exc}"
                    ) from exc
        return self


class PaperExpectations(_ExpectationModel):
    selector: PaperSelector
    expectations: list[SemanticExpectation] = Field(min_length=1)


class DossierExpectationFile(_ExpectationModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    papers: list[PaperExpectations] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_expectation_ids(self) -> "DossierExpectationFile":
        ids = [
            expectation.expectation_id
            for paper in self.papers
            for expectation in paper.expectations
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("expectation_id values must be unique")
        return self


class ExpectationCheckResult(_ExpectationModel):
    expectation_id: str
    paper_id: str
    passed: bool
    description: str
    matched_record: str | None = None
    missing_all_of: list[str] = Field(default_factory=list)
    any_of_matched: bool = True


class DossierExpectationReport(_ExpectationModel):
    valid: bool
    expectation_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    checks: list[ExpectationCheckResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def load_dossier_expectations(path: Path) -> DossierExpectationFile:
    """Load and strictly validate a paper-specific golden expectation file."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return DossierExpectationFile.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise DossierExpectationError(
            f"dossier expectation 파일이 유효하지 않습니다: {exc}"
        ) from exc


def validate_dossier_expectations(
    envelope: TechnicalResearchEnvelope,
    expectations: DossierExpectationFile,
) -> DossierExpectationReport:
    """Evaluate goldens against dossier semantics, never the evidence registry.

    Extracted inventory entries count as semantic findings.  Excluded and
    unverified inventory entries do not, so a query or a recorded gap cannot
    masquerade as a recovered result.  ``unverified_items`` are available only
    when an expectation explicitly selects that scope.
    """

    errors: list[str] = []
    checks: list[ExpectationCheckResult] = []
    selected_papers: set[str] = set()
    for paper_spec in expectations.papers:
        matching = [
            dossier
            for dossier in envelope.dossiers
            if _selector_matches(dossier, paper_spec.selector)
        ]
        if len(matching) != 1:
            rendered = _selector_description(paper_spec.selector)
            errors.append(
                f"selector({rendered})는 정확히 한 dossier와 일치해야 하지만 "
                f"{len(matching)}개와 일치했습니다."
            )
            continue
        dossier = matching[0]
        if dossier.paper.paper_id in selected_papers:
            errors.append(
                f"여러 selector가 같은 dossier를 선택했습니다: {dossier.paper.paper_id}"
            )
            continue
        selected_papers.add(dossier.paper.paper_id)
        for expectation in paper_spec.expectations:
            checks.append(_evaluate_expectation(dossier, expectation))

    failed = [check for check in checks if not check.passed]
    for check in failed:
        detail = ", ".join(check.missing_all_of)
        if not check.any_of_matched:
            detail = f"{detail}; any_of 불일치" if detail else "any_of 불일치"
        errors.append(
            f"{check.paper_id}/{check.expectation_id}: {check.description}"
            + (f" (불일치: {detail})" if detail else "")
        )
    passed_count = sum(check.passed for check in checks)
    return DossierExpectationReport(
        valid=not errors,
        expectation_count=sum(
            len(paper.expectations) for paper in expectations.papers
        ),
        passed_count=passed_count,
        checks=checks,
        errors=errors,
    )


def validate_dossier_expectation_file(
    envelope: TechnicalResearchEnvelope,
    path: Path,
) -> DossierExpectationReport:
    return validate_dossier_expectations(envelope, load_dossier_expectations(path))


def _evaluate_expectation(
    dossier: TechnicalDossier,
    expectation: SemanticExpectation,
) -> ExpectationCheckResult:
    records = _semantic_records(dossier, expectation.scopes)
    candidates = (
        ["\n".join(record for _, record in records)]
        if expectation.match_within == "dossier"
        else [record for _, record in records]
    )
    flags = 0 if expectation.case_sensitive else re.IGNORECASE
    all_patterns = [re.compile(pattern, flags) for pattern in expectation.all_of]
    any_patterns = [re.compile(pattern, flags) for pattern in expectation.any_of]
    for candidate in candidates:
        normalized = _normalize(candidate)
        if all(pattern.search(normalized) for pattern in all_patterns) and (
            not any_patterns or any(pattern.search(normalized) for pattern in any_patterns)
        ):
            return ExpectationCheckResult(
                expectation_id=expectation.expectation_id,
                paper_id=dossier.paper.paper_id,
                passed=True,
                description=expectation.description,
                matched_record=normalized[:1000],
            )

    # Dossier-wide diagnostics are more useful than reporting every failed
    # record: they distinguish an entirely absent value from a co-location
    # failure while preserving the stricter record-level pass condition.
    corpus = _normalize("\n".join(record for _, record in records))
    missing = [pattern.pattern for pattern in all_patterns if not pattern.search(corpus)]
    any_matched = not any_patterns or any(pattern.search(corpus) for pattern in any_patterns)
    return ExpectationCheckResult(
        expectation_id=expectation.expectation_id,
        paper_id=dossier.paper.paper_id,
        passed=False,
        description=expectation.description,
        missing_all_of=missing,
        any_of_matched=any_matched,
    )


def _semantic_records(
    dossier: TechnicalDossier,
    scopes: list[SemanticScope],
) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    if "analysis" in scopes:
        _collect_analysis_records(dossier.analysis.model_dump(mode="json"), "analysis", records)
    if "claims" in scopes:
        records.extend(("claims", claim.text) for claim in dossier.claims)
    if "critical_inventory" in scopes:
        records.extend(
            ("critical_inventory", item.summary)
            for item in dossier.critical_inventory
            if item.disposition == "extracted"
        )
    if "experiment_observations" in scopes:
        for observation in dossier.experiment_observations:
            payload = observation.model_dump(mode="json")
            semantic_keys = (
                "metric",
                "value",
                "value_min",
                "value_max",
                "unit",
                "direction",
                "baseline",
                "model",
                "hardware",
                "context_length",
                "concurrency",
                "dataset",
                "workload",
                "evaluation_mode",
            )
            parts = [
                f"{key}: {payload[key]}"
                for key in semantic_keys
                if payload.get(key) is not None
            ]
            records.append(("experiment_observations", " | ".join(parts)))
    if "unverified_items" in scopes:
        records.extend(
            ("unverified_items", f"{item.topic} | {item.reason}")
            for item in dossier.unverified_items
        )
    return [(scope, _normalize(record)) for scope, record in records if record.strip()]


def _collect_analysis_records(
    value: object,
    path: str,
    records: list[tuple[str, str]],
) -> None:
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str) and text.strip():
            records.append((path, text))
            return
        for key, child in value.items():
            # Evidence references and confidences are contract metadata, not
            # semantic dossier content.
            if key in {"evidence_ids", "context_evidence_ids", "confidence"}:
                continue
            _collect_analysis_records(child, f"{path}.{key}", records)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _collect_analysis_records(child, f"{path}[{index}]", records)
    elif isinstance(value, str) and value.strip():
        records.append((path, value))


def _selector_matches(dossier: TechnicalDossier, selector: PaperSelector) -> bool:
    paper = dossier.paper
    if selector.paper_id_regex and not re.search(selector.paper_id_regex, paper.paper_id):
        return False
    if selector.title_regex and not re.search(
        selector.title_regex, paper.title or "", re.IGNORECASE
    ):
        return False
    if selector.arxiv_id and selector.arxiv_id != paper.arxiv_id:
        return False
    if selector.source_basename and selector.source_basename != Path(paper.source_path).name:
        return False
    return True


def _selector_description(selector: PaperSelector) -> str:
    return ", ".join(
        f"{key}={value}"
        for key, value in selector.model_dump(exclude_none=True).items()
    )


def _compile_optional_regex(pattern: str | None, name: str) -> None:
    if pattern is None:
        return
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"invalid {name}: {pattern!r}: {exc}") from exc


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


__all__ = [
    "DossierExpectationError",
    "DossierExpectationFile",
    "DossierExpectationReport",
    "ExpectationCheckResult",
    "PaperExpectations",
    "PaperSelector",
    "SemanticExpectation",
    "load_dossier_expectations",
    "validate_dossier_expectation_file",
    "validate_dossier_expectations",
]
