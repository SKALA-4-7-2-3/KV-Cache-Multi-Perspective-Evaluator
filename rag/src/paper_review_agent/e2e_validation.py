"""Create hash-bound promotion evidence from a completed technical research run.

The retrieval benchmark intentionally does not infer end-to-end quality or memory
properties from retrieval-only measurements.  This module turns a *validated*
``technical/run.json`` into the small, immutable artifact consumed by the
promotion gate.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from paper_review_agent.artifacts import atomic_write
from paper_review_agent.dossier_expectations import (
    DossierExpectationError,
    validate_dossier_expectation_file,
)
from paper_review_agent.technical_schemas import (
    RetrievalE2EValidationArtifact,
    TechnicalResearchEnvelope,
)
from paper_review_agent.technical_validation import validate_technical_research


class E2EValidationArtifactError(ValueError):
    """Raised when a run cannot provide trustworthy promotion evidence."""


def create_retrieval_e2e_validation_artifact(
    golden_path: Path,
    technical_run_path: Path,
    output_path: Path | None = None,
    *,
    peak_rss_bytes: int | None = None,
    completed_without_oom: bool | None = None,
    expected_index_profile: str | None = None,
    expected_paper_ids: list[str] | None = None,
    dossier_expectations_path: Path | None = None,
) -> RetrievalE2EValidationArtifact:
    """Validate a successful two-paper run and atomically bind it to a golden set.

    ``peak_rss_bytes`` and ``completed_without_oom`` are read from the run
    metadata when present.  They remain explicit overrides for older run files
    that predate those metadata fields.  If both a run value and an explicit
    value are supplied they must agree; this prevents a caller from silently
    rewriting a measured result.
    """

    golden = _existing_file(golden_path, "golden")
    run_path = _existing_file(technical_run_path, "technical run")
    try:
        run_raw = run_path.read_bytes()
        run_payload = json.loads(run_raw)
        envelope = TechnicalResearchEnvelope.model_validate(run_payload)
    except (OSError, json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise E2EValidationArtifactError(
            f"기술조사 run.json 계약이 유효하지 않습니다: {exc}"
        ) from exc

    _validate_success_envelope(envelope)
    contract_report = validate_technical_research(run_path)
    if not contract_report.valid:
        rendered = "; ".join(contract_report.errors[:10])
        raise E2EValidationArtifactError(
            f"기술조사 아티팩트/근거 계약 검증에 실패했습니다: {rendered}"
        )

    run_metadata = run_payload.get("run")
    if not isinstance(run_metadata, dict):
        raise E2EValidationArtifactError("run metadata가 JSON 객체가 아닙니다.")
    measured_peak = _metadata_value(run_metadata, "peak_rss_bytes")
    measured_completion = _metadata_value(run_metadata, "completed_without_oom")
    resolved_peak = _resolve_measurement(
        "peak_rss_bytes", measured_peak, peak_rss_bytes
    )
    resolved_completion = _resolve_measurement(
        "completed_without_oom", measured_completion, completed_without_oom
    )
    if isinstance(resolved_peak, bool) or not isinstance(resolved_peak, int):
        raise E2EValidationArtifactError("peak_rss_bytes는 양의 정수여야 합니다.")
    if resolved_peak <= 0:
        raise E2EValidationArtifactError("peak_rss_bytes는 0보다 커야 합니다.")
    if not isinstance(resolved_completion, bool):
        raise E2EValidationArtifactError("completed_without_oom은 bool이어야 합니다.")

    index_profile = envelope.run.index_profile
    if not index_profile:
        raise E2EValidationArtifactError("run metadata에 BGE index_profile이 없습니다.")
    if expected_index_profile is not None and index_profile != expected_index_profile:
        raise E2EValidationArtifactError(
            "run metadata의 index_profile이 기대값과 일치하지 않습니다."
        )

    paper_ids = [dossier.paper.paper_id for dossier in envelope.dossiers]
    if len(paper_ids) != len(set(paper_ids)):
        raise E2EValidationArtifactError("run.json에 중복 paper_id가 있습니다.")
    if expected_paper_ids is not None and set(expected_paper_ids) != set(paper_ids):
        raise E2EValidationArtifactError(
            "run.json의 성공 paper_id 집합이 기대값과 일치하지 않습니다."
        )

    expectations_path: Path | None = None
    expectation_count: int | None = None
    if dossier_expectations_path is not None:
        expectations_path = _existing_file(
            dossier_expectations_path, "dossier expectations"
        )
        try:
            expectation_report = validate_dossier_expectation_file(
                envelope, expectations_path
            )
        except DossierExpectationError as exc:
            raise E2EValidationArtifactError(str(exc)) from exc
        if not expectation_report.valid:
            rendered = "; ".join(expectation_report.errors[:20])
            raise E2EValidationArtifactError(
                f"dossier golden expectation 검증에 실패했습니다: {rendered}"
            )
        expectation_count = expectation_report.expectation_count

    artifact = RetrievalE2EValidationArtifact(
        golden_sha256=_sha256_file(golden),
        technical_run_path=str(run_path),
        technical_run_sha256=hashlib.sha256(run_raw).hexdigest(),
        bge_index_profile=index_profile,
        successful_paper_ids=paper_ids,
        completed_without_oom=resolved_completion,
        peak_rss_bytes=resolved_peak,
        dossier_expectations_sha256=(
            _sha256_file(expectations_path) if expectations_path is not None else None
        ),
        dossier_expectations_path=(
            str(expectations_path) if expectations_path is not None else None
        ),
        dossier_expectation_count=expectation_count,
    )
    destination = (
        _resolve_path(output_path)
        if output_path is not None
        else golden.with_suffix(".e2e.json")
    )
    serialized = (
        json.dumps(
            artifact.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    atomic_write(destination, serialized)
    return artifact


def _validate_success_envelope(envelope: TechnicalResearchEnvelope) -> None:
    errors: list[str] = []
    if envelope.status != "succeeded":
        errors.append(f"status={envelope.status}")
    if envelope.run.embedding_provider != "bge-m3":
        errors.append("embedding_provider가 bge-m3가 아님")
    if envelope.run.finished_at is None:
        errors.append("finished_at 누락")
    if len({dossier.paper.paper_id for dossier in envelope.dossiers}) < 2:
        errors.append("서로 다른 성공 논문이 2편 미만")
    if envelope.quality.evidence_resolution_rate != 1.0:
        errors.append("evidence_resolution_rate가 1.0이 아님")
    if envelope.quality.locator_resolution_rate != 1.0:
        errors.append("locator_resolution_rate가 1.0이 아님")
    if envelope.quality.critical_inventory_coverage != 1.0:
        errors.append("critical_inventory_coverage가 1.0이 아님")
    if envelope.quality.unsupported_numeric_claims != 0:
        errors.append("unsupported_numeric_claims가 0이 아님")
    if errors:
        raise E2EValidationArtifactError(
            "BGE-M3 E2E 승격 조건을 충족하지 않습니다: " + "; ".join(errors)
        )


def _metadata_value(metadata: dict[str, Any], key: str) -> Any:
    if key in metadata:
        return metadata[key]
    resource_usage = metadata.get("resource_usage")
    if isinstance(resource_usage, dict):
        return resource_usage.get(key)
    return None


def _resolve_measurement(name: str, measured: Any, supplied: Any) -> Any:
    if measured is not None and supplied is not None and measured != supplied:
        raise E2EValidationArtifactError(
            f"{name} CLI 값이 run metadata의 측정값과 다릅니다."
        )
    resolved = measured if measured is not None else supplied
    if resolved is None:
        raise E2EValidationArtifactError(
            f"run metadata에 {name}가 없습니다. 명시적 측정값을 제공하세요."
        )
    return resolved


def _existing_file(path: Path, label: str) -> Path:
    resolved = _resolve_path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} 파일을 찾을 수 없습니다: {resolved}")
    return resolved


def _resolve_path(path: Path) -> Path:
    return Path(os.path.expandvars(str(path))).expanduser().resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


__all__ = [
    "E2EValidationArtifactError",
    "create_retrieval_e2e_validation_artifact",
]
