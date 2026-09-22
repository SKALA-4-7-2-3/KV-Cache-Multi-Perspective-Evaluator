"""Deterministic contract and completeness validation for technical research."""

from __future__ import annotations

import hashlib
import json
import re
from itertools import combinations
from pathlib import Path

from pydantic import ValidationError

from paper_review_agent.evidence_ids import (
    EVIDENCE_ID_VERSION,
    evidence_element_id,
    format_table_cell_suffix,
    table_aggregate_suffix,
)
from paper_review_agent.schemas import ValidationReport
from paper_review_agent.technical_schemas import (
    ExperimentObservation,
    TechnicalArtifactRef,
    TechnicalAudit,
    TechnicalComparison,
    TechnicalDossier,
    TechnicalEvidence,
    TechnicalResearchEnvelope,
)


# Do not reinterpret digits embedded in model/hardware identifiers (A100,
# LLaMA-3.1-8B, Qwen2.5) as standalone experimental values. Context lengths
# such as 128K remain visible because the number starts at a token boundary.
NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9.\-])[-+]?\d[\d,]*(?:\.\d+)?(?:\s*[×xX%])?"
)
NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def validate_dossier_contract(
    dossier: TechnicalDossier,
    evidence: list[TechnicalEvidence],
    audit: TechnicalAudit | None = None,
) -> tuple[list[str], list[str]]:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    errors: list[str] = []
    warnings: list[str] = []
    own_document = {dossier.paper.paper_id}

    for owner, claim in _analysis_claims(dossier):
        _validate_refs(
            owner,
            claim.evidence_ids,
            evidence_by_id,
            errors,
            allowed_documents=own_document,
        )
        _validate_context_refs(
            owner,
            claim.context_evidence_ids,
            evidence_by_id,
            errors,
        )
        _validate_numeric_text(
            owner, claim.text, claim.evidence_ids, evidence_by_id, errors
        )

    if not dossier.analysis.technical_overview.problem_definition:
        errors.append(f"{dossier.paper.paper_id}: problem_definition is empty")
    if not dossier.analysis.technical_overview.core_approach:
        errors.append(f"{dossier.paper.paper_id}: core_approach is empty")
    if not dossier.analysis.technical_overview.experimental_results:
        errors.append(f"{dossier.paper.paper_id}: experimental_results is empty")
    limitation_count = sum(
        len(getattr(dossier.analysis.limitations, name))
        for name in (
            "author_stated",
            "inferred",
            "compute_constraints",
            "data_constraints",
            "generalization_constraints",
            "reproducibility_constraints",
        )
    )
    if not limitation_count:
        errors.append(
            f"{dossier.paper.paper_id}: no limitation or constraint was extracted"
        )

    claim_ids: set[str] = set()
    claims_by_id = {}
    for claim in dossier.claims:
        if claim.claim_id in claim_ids:
            errors.append(f"duplicate claim_id: {claim.claim_id}")
        claim_ids.add(claim.claim_id)
        claims_by_id[claim.claim_id] = claim
        _validate_refs(
            claim.claim_id,
            claim.evidence_ids,
            evidence_by_id,
            errors,
            allowed_documents=own_document,
        )
        _validate_context_refs(
            claim.claim_id,
            claim.context_evidence_ids,
            evidence_by_id,
            errors,
        )
        _validate_numeric_text(
            claim.claim_id, claim.text, claim.evidence_ids, evidence_by_id, errors
        )

    observation_ids: set[str] = set()
    for observation in dossier.experiment_observations:
        if observation.observation_id in observation_ids:
            errors.append(f"duplicate observation_id: {observation.observation_id}")
        observation_ids.add(observation.observation_id)
        _validate_refs(
            observation.observation_id,
            observation.evidence_ids,
            evidence_by_id,
            errors,
            allowed_documents=own_document,
        )
        _validate_numeric_observation(observation, evidence_by_id, errors)

    linked_critical_claim_ids: set[str] = set()
    for item in dossier.critical_inventory:
        if item.disposition == "extracted" and not item.claim_ids:
            errors.append(f"{item.inventory_id}: extracted item requires claim_ids")
        if item.disposition == "extracted" and not item.evidence_ids:
            errors.append(f"{item.inventory_id}: extracted item requires evidence_ids")
        _validate_refs(
            item.inventory_id,
            item.evidence_ids,
            evidence_by_id,
            errors,
            allowed_documents=own_document,
        )
        for claim_id in item.claim_ids:
            if claim_id not in claim_ids:
                errors.append(f"{item.inventory_id}: unknown claim_id {claim_id}")
            else:
                linked_critical_claim_ids.add(claim_id)
                if not claims_by_id[claim_id].critical:
                    errors.append(
                        f"{item.inventory_id}: inventory claim must be critical: {claim_id}"
                    )

    unlinked_critical = {
        claim.claim_id
        for claim in dossier.claims
        if claim.critical and claim.claim_id not in linked_critical_claim_ids
    }
    for claim_id in sorted(unlinked_critical):
        errors.append(f"critical claim is not linked from inventory: {claim_id}")

    for owner, claim in _analysis_claims(dossier):
        if owner.startswith("analysis.scope.inferred_scope[") or owner.startswith(
            "analysis.limitations.inferred["
        ):
            if claim.claim_type != "analyst_inference":
                errors.append(f"{owner}: inferred claim must be analyst_inference")

    referenced = set(dossier.evidence_ids)
    for value in referenced:
        if value not in evidence_by_id:
            errors.append(f"dossier evidence_ids contains unknown ID: {value}")

    if audit is not None:
        expected = claim_ids | observation_ids | set(analysis_audit_item_ids(dossier))
        audit_by_id = {item.item_id: item for item in audit.audits}
        for item_id in sorted(expected):
            item = audit_by_id.get(item_id)
            if item is None:
                errors.append(f"missing semantic audit: {item_id}")
            elif item.verdict != "supported":
                errors.append(
                    f"semantic audit failed: {item_id}={item.verdict}: {item.reason}"
                )
        if audit.missing_critical_topics:
            errors.extend(
                f"missing critical topic: {value}"
                for value in audit.missing_critical_topics
            )
        errors.extend(
            f"numeric consistency: {value}"
            for value in audit.numeric_consistency_errors
        )
        errors.extend(
            f"overgeneralization: {value}" for value in audit.overgeneralization_errors
        )

    unverified_topics = {item.topic for item in dossier.unverified_items}
    if unverified_topics:
        warnings.append("unverified topics: " + ", ".join(sorted(unverified_topics)))
    return _dedupe(errors), _dedupe(warnings)


def validate_comparison_contract(
    comparison: TechnicalComparison,
    dossiers: list[TechnicalDossier],
    evidence: list[TechnicalEvidence],
) -> list[str]:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    observations = {
        item.observation_id: item
        for dossier in dossiers
        for item in dossier.experiment_observations
    }
    observation_owners: dict[str, list[str]] = {}
    for dossier in dossiers:
        for observation in dossier.experiment_observations:
            observation_owners.setdefault(observation.observation_id, []).append(
                dossier.paper.paper_id
            )
    errors: list[str] = []
    for observation_id, owners in observation_owners.items():
        if len(owners) > 1:
            errors.append(
                f"duplicate cross-paper observation_id {observation_id}: {sorted(owners)}"
            )
    known_papers = {dossier.paper.paper_id for dossier in dossiers}
    expected_pairs = {tuple(sorted(pair)) for pair in combinations(known_papers, 2)}
    if len(known_papers) >= 2 and not comparison.relationships:
        errors.append(
            "technical comparison relationships must not be empty for multiple papers"
        )
    if len(known_papers) >= 2 and not comparison.matrix:
        errors.append(
            "technical comparison matrix must not be empty for multiple papers"
        )
    if (
        len(known_papers) >= 2
        and not comparison.common_assumptions
        and not comparison.differing_assumptions
    ):
        errors.append(
            "technical comparison must explicitly record common or differing assumptions"
        )
    seen_pairs: dict[tuple[str, str], int] = {}
    for relationship in comparison.relationships:
        _validate_refs(
            f"relationship:{relationship.left_paper_id}:{relationship.right_paper_id}",
            relationship.evidence_ids,
            evidence_by_id,
            errors,
        )
        documents = {
            evidence_by_id[value].document_id
            for value in relationship.evidence_ids
            if value in evidence_by_id
        }
        pair = {relationship.left_paper_id, relationship.right_paper_id}
        if len(pair) != 2 or not pair.issubset(known_papers):
            errors.append(
                "technology relationship must name two known, distinct papers"
            )
        else:
            pair_key = tuple(sorted(pair))
            seen_pairs[pair_key] = seen_pairs.get(pair_key, 0) + 1
        if not pair.issubset(documents):
            errors.append(
                "technology relationship must cite evidence from both named papers"
            )
        if (
            not relationship.tested_together
            and relationship.claim_type != "analyst_inference"
        ):
            errors.append("untested relationship must be analyst_inference")
    for pair in sorted(expected_pairs - set(seen_pairs)):
        errors.append(
            f"missing technology relationship for papers: {pair[0]}, {pair[1]}"
        )
    for pair, count in sorted(seen_pairs.items()):
        if count > 1:
            errors.append(
                f"duplicate technology relationship for papers: {pair[0]}, {pair[1]}"
            )
    for assumption in comparison.common_assumptions:
        owner = f"common_assumption:{assumption.assumption_id}"
        paper_ids = set(assumption.paper_ids)
        if len(paper_ids) < 2 or not paper_ids.issubset(known_papers):
            errors.append(f"{owner}: must name at least two known, distinct papers")
        _validate_refs(owner, assumption.evidence_ids, evidence_by_id, errors)
        cited_documents = {
            evidence_by_id[value].document_id
            for value in assumption.evidence_ids
            if value in evidence_by_id
        }
        if cited_documents != paper_ids:
            errors.append(
                f"{owner}: evidence must belong to every and only named paper"
            )
    for assumption in comparison.differing_assumptions:
        owner = f"differing_assumption:{assumption.assumption_id}"
        paper_ids = [item.paper_id for item in assumption.paper_assumptions]
        if len(set(paper_ids)) != len(paper_ids):
            errors.append(f"{owner}: duplicate paper assumption")
        if len(set(paper_ids)) < 2 or not set(paper_ids).issubset(known_papers):
            errors.append(f"{owner}: must describe at least two known, distinct papers")
        if len({_norm(item.statement) for item in assumption.paper_assumptions}) < 2:
            errors.append(f"{owner}: identical statements belong in common_assumptions")
        for item in assumption.paper_assumptions:
            _validate_refs(
                f"{owner}:{item.paper_id}",
                item.evidence_ids,
                evidence_by_id,
                errors,
                allowed_documents={item.paper_id},
            )
    for cell in comparison.matrix:
        _validate_refs(
            f"matrix:{cell.dimension}:{cell.paper_id}",
            cell.evidence_ids,
            evidence_by_id,
            errors,
        )
        cited_documents = {
            evidence_by_id[value].document_id
            for value in cell.evidence_ids
            if value in evidence_by_id
        }
        if cell.paper_id not in known_papers or cited_documents != {cell.paper_id}:
            errors.append(
                f"matrix:{cell.dimension}:{cell.paper_id}: evidence must belong to that paper"
            )
    matrix_papers = {cell.paper_id for cell in comparison.matrix}
    for paper_id in sorted(known_papers - matrix_papers):
        errors.append(f"technical comparison matrix is missing paper: {paper_id}")
    for hypothesis in comparison.integration_hypotheses:
        _validate_refs(
            hypothesis.hypothesis_id, hypothesis.evidence_ids, evidence_by_id, errors
        )
        documents = {
            evidence_by_id[value].document_id
            for value in hypothesis.evidence_ids
            if value in evidence_by_id
        }
        if len(documents) < 2:
            errors.append(
                f"{hypothesis.hypothesis_id}: integration requires evidence from both papers"
            )
    for metric in comparison.metric_comparisons:
        selected = [observations.get(value) for value in metric.observation_ids]
        if any(value is None for value in selected):
            errors.append(f"{metric.comparison_id}: unknown observation ID")
            continue
        owners = {
            owner
            for observation_id in metric.observation_ids
            for owner in observation_owners.get(observation_id, [])
        }
        if len(owners) < 2:
            errors.append(
                f"{metric.comparison_id}: metric comparison requires two papers"
            )
        if metric.comparability == "comparable" and not _compatible_observations(
            selected
        ):
            errors.append(
                f"{metric.comparison_id}: incompatible experiment signatures must be not_comparable"
            )
    return _dedupe(errors)


def evidence_resolution_rates(
    dossiers: list[TechnicalDossier], evidence: list[TechnicalEvidence]
) -> tuple[float, float]:
    registry = {item.evidence_id: item for item in evidence}
    refs = [
        value
        for dossier in dossiers
        for values in (
            [
                value
                for _, claim in _analysis_claims(dossier)
                for value in [*claim.evidence_ids, *claim.context_evidence_ids]
            ],
            [
                value
                for claim in dossier.claims
                for value in [*claim.evidence_ids, *claim.context_evidence_ids]
            ],
            [
                value
                for obs in dossier.experiment_observations
                for value in obs.evidence_ids
            ],
            [
                value
                for item in dossier.critical_inventory
                for value in item.evidence_ids
            ],
            dossier.evidence_ids,
        )
        for value in values
    ]
    resolved = sum(value in registry for value in refs)
    locator_resolved = sum(
        value in registry
        and bool(registry[value].locator.element_id)
        and bool(registry[value].locator.document_sha256)
        for value in refs
    )
    denominator = len(refs)
    return (
        resolved / denominator if denominator else 1.0,
        locator_resolved / denominator if denominator else 1.0,
    )


def validate_technical_research(path: Path) -> ValidationReport:
    path = path.expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        envelope = TechnicalResearchEnvelope.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return ValidationReport(
            valid=False, errors=[f"기술조사 결과를 읽을 수 없습니다: {exc}"]
        )
    if envelope.status != "succeeded":
        return ValidationReport(
            valid=False,
            schema_version=envelope.schema_version,
            errors=[f"성공 기술조사 결과가 아닙니다: {envelope.status}"],
        )
    root = path.parent.resolve()
    evidence_path = Path(envelope.evidence_registry_path or "")
    if not evidence_path.is_absolute():
        evidence_path = (root / evidence_path).resolve()
    if not evidence_path.is_relative_to(root):
        return ValidationReport(
            valid=False,
            schema_version=envelope.schema_version,
            errors=["evidence_registry_path가 기술조사 실행 디렉터리를 벗어났습니다."],
        )
    errors = _validate_artifact_files(envelope, root, evidence_path)
    try:
        evidence = [
            TechnicalEvidence.model_validate(item)
            for item in json.loads(evidence_path.read_text(encoding="utf-8"))
        ]
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return ValidationReport(
            valid=False,
            schema_version=envelope.schema_version,
            errors=[f"근거 레지스트리를 읽을 수 없습니다: {exc}"],
        )
    warnings: list[str] = []
    for dossier in envelope.dossiers:
        dossier_errors, dossier_warnings = validate_dossier_contract(dossier, evidence)
        errors.extend(dossier_errors)
        warnings.extend(dossier_warnings)
    errors.extend(
        validate_comparison_contract(envelope.comparison, envelope.dossiers, evidence)
    )
    errors.extend(_validate_artifact_payloads(envelope, evidence, root, evidence_path))
    errors.extend(_validate_evidence_locators(envelope, evidence, root))
    rate, locator_rate = evidence_resolution_rates(envelope.dossiers, evidence)
    if rate != 1.0:
        errors.append(f"evidence resolution rate is {rate:.4f}, expected 1.0")
    if locator_rate != 1.0:
        errors.append(f"locator resolution rate is {locator_rate:.4f}, expected 1.0")
    return ValidationReport(
        valid=not errors,
        schema_version=envelope.schema_version,
        errors=_dedupe(errors),
        warnings=_dedupe(warnings),
    )


def _validate_artifact_files(
    envelope: TechnicalResearchEnvelope,
    root: Path,
    evidence_path: Path,
) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()
    resolved: list[tuple[TechnicalArtifactRef, Path]] = []
    for ref in envelope.artifacts:
        if ref.artifact_id in seen_ids:
            errors.append(f"duplicate artifact_id: {ref.artifact_id}")
        seen_ids.add(ref.artifact_id)
        artifact_path = Path(ref.path)
        if not artifact_path.is_absolute():
            artifact_path = root / artifact_path
        artifact_path = artifact_path.resolve()
        if not artifact_path.is_relative_to(root):
            errors.append(
                f"artifact path escapes technical run directory: {ref.artifact_id}"
            )
            continue
        if artifact_path in seen_paths:
            errors.append(f"duplicate artifact path: {artifact_path}")
        seen_paths.add(artifact_path)
        if not artifact_path.is_file():
            errors.append(
                f"artifact file is missing: {ref.artifact_id}: {artifact_path}"
            )
            continue
        digest = _sha256_file(artifact_path)
        if digest != ref.sha256:
            errors.append(
                f"artifact hash mismatch: {ref.artifact_id}: expected {ref.sha256}, got {digest}"
            )
        if not ref.artifact_id.endswith(ref.sha256[:16]):
            errors.append(f"artifact_id does not match sha256: {ref.artifact_id}")
        resolved.append((ref, artifact_path))

    by_type: dict[str, list[tuple[TechnicalArtifactRef, Path]]] = {}
    for item in resolved:
        by_type.setdefault(item[0].type, []).append(item)
    expected_counts = {
        "dossier": len(envelope.dossiers),
        "comparison": 1,
        "evidence_registry": 1,
        "retrieval_trace": 1,
    }
    for artifact_type, expected in expected_counts.items():
        actual = len(by_type.get(artifact_type, []))
        if actual != expected:
            errors.append(
                f"artifact count mismatch for {artifact_type}: expected {expected}, got {actual}"
            )
    evidence_refs = by_type.get("evidence_registry", [])
    if evidence_refs and evidence_refs[0][1] != evidence_path:
        errors.append(
            "evidence_registry_path does not match evidence_registry artifact"
        )
    return errors


def _validate_artifact_payloads(
    envelope: TechnicalResearchEnvelope,
    evidence: list[TechnicalEvidence],
    root: Path,
    evidence_path: Path,
) -> list[str]:
    errors: list[str] = []
    expected_dossiers = {
        dossier.paper.paper_id: dossier.model_dump(mode="json")
        for dossier in envelope.dossiers
    }
    seen_dossiers: set[str] = set()
    for ref in envelope.artifacts:
        artifact_path = _contained_artifact_path(ref, root)
        if artifact_path is None or not artifact_path.is_file():
            continue
        try:
            if ref.type == "dossier":
                dossier = TechnicalDossier.model_validate_json(
                    artifact_path.read_text("utf-8")
                )
                paper_id = dossier.paper.paper_id
                seen_dossiers.add(paper_id)
                if dossier.model_dump(mode="json") != expected_dossiers.get(paper_id):
                    errors.append(
                        f"dossier artifact differs from run envelope: {paper_id}"
                    )
            elif ref.type == "comparison":
                comparison = TechnicalComparison.model_validate_json(
                    artifact_path.read_text("utf-8")
                )
                if comparison.model_dump(mode="json") != envelope.comparison.model_dump(
                    mode="json"
                ):
                    errors.append("comparison artifact differs from run envelope")
            elif ref.type == "evidence_registry" and artifact_path == evidence_path:
                stored = [
                    TechnicalEvidence.model_validate(item)
                    for item in json.loads(artifact_path.read_text("utf-8"))
                ]
                if [item.model_dump(mode="json") for item in stored] != [
                    item.model_dump(mode="json") for item in evidence
                ]:
                    errors.append(
                        "evidence registry artifact differs from loaded registry"
                    )
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            errors.append(f"invalid {ref.type} artifact {ref.artifact_id}: {exc}")
    missing = set(expected_dossiers) - seen_dossiers
    for paper_id in sorted(missing):
        errors.append(f"missing dossier artifact payload: {paper_id}")
    return errors


def _validate_evidence_locators(
    envelope: TechnicalResearchEnvelope,
    evidence: list[TechnicalEvidence],
    root: Path,
) -> list[str]:
    errors: list[str] = []
    source_chunks, manifest_errors = _load_source_chunk_manifests(envelope, root)
    errors.extend(manifest_errors)
    require_v2 = envelope.run.evidence_id_version == EVIDENCE_ID_VERSION
    papers = {dossier.paper.paper_id: dossier.paper for dossier in envelope.dossiers}
    artifacts = {ref.artifact_id: ref for ref in envelope.artifacts}
    seen_evidence: set[str] = set()
    checked_sources: set[str] = set()
    for item in evidence:
        owner = item.evidence_id
        if owner in seen_evidence:
            errors.append(f"duplicate evidence_id: {owner}")
        seen_evidence.add(owner)
        locator = item.locator
        if not locator.element_id.strip():
            errors.append(f"{owner}: empty locator element_id")
        if not re.fullmatch(r"[0-9a-f]{64}", item.content_hash):
            errors.append(f"{owner}: invalid content_hash")
        elif (
            hashlib.sha256(item.snippet.encode("utf-8")).hexdigest()
            != item.content_hash
        ):
            errors.append(f"{owner}: content_hash does not match evidence snippet")

        expected_prefix = (
            f"{item.source_kind}:{item.document_id}@{locator.document_sha256[:12]}:"
            f"p{int(locator.physical_page or 0):04d}:{locator.element_id}:"
        )
        if not owner.startswith(expected_prefix):
            errors.append(f"{owner}: evidence ID does not match its locator")

        if require_v2:
            errors.extend(_validate_v2_evidence_id(item, expected_prefix))
            errors.extend(
                _validate_locator_against_source_chunk(item, source_chunks)
            )

        if item.source_kind == "paper":
            paper = papers.get(item.document_id)
            if paper is None:
                errors.append(f"{owner}: locator document is absent from dossiers")
            else:
                if locator.document_sha256 != paper.source_hash:
                    errors.append(
                        f"{owner}: locator document hash differs from dossier"
                    )
                if (
                    locator.physical_page is None
                    or not 1 <= locator.physical_page <= paper.page_count
                ):
                    errors.append(
                        f"{owner}: physical page is outside the source document"
                    )
                if paper.paper_id not in checked_sources:
                    checked_sources.add(paper.paper_id)
                    source_path = Path(paper.source_path).expanduser()
                    if not source_path.is_file():
                        errors.append(
                            f"{paper.paper_id}: source document is missing: {source_path}"
                        )
                    elif _sha256_file(source_path) != paper.source_hash:
                        errors.append(
                            f"{paper.paper_id}: source document hash mismatch"
                        )

        if locator.bbox_pt is not None and locator.page_size_pt is not None:
            x0, y0, x1, y1 = locator.bbox_pt
            width, height = locator.page_size_pt
            if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
                errors.append(f"{owner}: bbox lies outside page_size_pt")
        cell_match = re.search(r":cell-r(\d+)-c(\d+)$", owner)
        if cell_match:
            expected_cell = (int(cell_match.group(1)), int(cell_match.group(2)))
            actual_cells = {
                (cell.row_index, cell.column_index) for cell in locator.table_cells
            }
            if expected_cell not in actual_cells:
                errors.append(
                    f"{owner}: table cell ID does not resolve to locator.table_cells"
                )
        if item.content_kind in {"text", "caption"} and locator.text_span is None:
            errors.append(f"{owner}: textual evidence has no text_span")
        if item.extraction_method == "vision":
            if not locator.crop_sha256:
                errors.append(f"{owner}: vision evidence has no crop_sha256")
            if not locator.visual_artifact_id:
                errors.append(
                    f"{owner}: vision evidence has no visual artifact reference"
                )
            else:
                ref = artifacts.get(locator.visual_artifact_id)
                if ref is None or ref.type != "visual_crop":
                    errors.append(
                        f"{owner}: visual artifact reference cannot be resolved"
                    )
                elif locator.crop_sha256 != ref.sha256:
                    errors.append(
                        f"{owner}: visual crop hash differs from artifact hash"
                    )
                elif _contained_artifact_path(ref, root) is None:
                    errors.append(
                        f"{owner}: visual artifact path escapes run directory"
                    )
    return errors


def _load_source_chunk_manifests(
    envelope: TechnicalResearchEnvelope,
    root: Path,
) -> tuple[dict[tuple[str, str, str], dict], list[str]]:
    """Load hash-only source-chunk bindings from the published trace artifact."""

    errors: list[str] = []
    manifests: dict[tuple[str, str, str], dict] = {}
    trace_refs = [item for item in envelope.artifacts if item.type == "retrieval_trace"]
    if not trace_refs:
        return manifests, ["source chunk manifest cannot be resolved: retrieval trace missing"]
    trace_path = _contained_artifact_path(trace_refs[0], root)
    if trace_path is None or not trace_path.is_file():
        return manifests, ["source chunk manifest cannot be resolved: trace path invalid"]
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return manifests, [f"source chunk manifest cannot be read: {exc}"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid retrieval trace line {line_number}: {exc}")
            continue
        if payload.get("trace_kind") != "source_chunk_manifest":
            continue
        if payload.get("manifest_version") != EVIDENCE_ID_VERSION:
            errors.append(
                f"source chunk manifest version mismatch on line {line_number}"
            )
            continue
        chunks = payload.get("chunks")
        if not isinstance(chunks, list):
            errors.append(f"invalid source chunk manifest on line {line_number}")
            continue
        for raw in chunks:
            if not isinstance(raw, dict):
                errors.append(f"invalid source chunk entry on line {line_number}")
                continue
            key = (
                str(raw.get("source_kind", "")),
                str(raw.get("document_id", "")),
                str(raw.get("source_chunk_id", "")),
            )
            if not all(key):
                errors.append(f"incomplete source chunk entry on line {line_number}")
                continue
            previous = manifests.get(key)
            if previous is not None and previous != raw:
                errors.append(
                    "conflicting source chunk manifest entry: " + ":".join(key)
                )
            manifests[key] = raw
    if envelope.run.evidence_id_version == EVIDENCE_ID_VERSION and not manifests:
        errors.append("evidence ID v2 run has no source chunk manifest")
    return manifests, errors


def _validate_v2_evidence_id(
    item: TechnicalEvidence,
    expected_prefix: str,
) -> list[str]:
    errors: list[str] = []
    locator = item.locator
    if not locator.source_chunk_id:
        errors.append(f"{item.evidence_id}: evidence ID v2 requires source_chunk_id")
    if not locator.source_element_id:
        errors.append(f"{item.evidence_id}: evidence ID v2 requires source_element_id")
        return errors
    canonical_element, normalized_label = evidence_element_id(
        object_label=locator.object_label,
        content_kind=item.content_kind,
        source_element_id=locator.source_element_id,
    )
    if locator.element_id != canonical_element:
        errors.append(
            f"{item.evidence_id}: locator element_id is not canonical: "
            f"expected {canonical_element}"
        )
    if locator.normalized_object_label != normalized_label:
        errors.append(
            f"{item.evidence_id}: normalized object label does not match source label"
        )

    suffix: str
    if item.content_kind == "table" and locator.table_cells:
        if len(locator.table_cells) != 1:
            errors.append(
                f"{item.evidence_id}: exact table-cell evidence must contain one cell"
            )
            return errors
        cell = locator.table_cells[0]
        suffix = format_table_cell_suffix(cell.row_index, cell.column_index)
    elif item.content_kind == "table":
        # Aggregate row-group suffix is checked against the source manifest,
        # where the original chunk's length and row set are available.
        suffix = item.evidence_id.removeprefix(expected_prefix)
        if suffix != "whole" and not re.fullmatch(r"rows-(?:r\d{2,}-r\d{2,}|[0-9a-f]{12})", suffix):
            errors.append(f"{item.evidence_id}: invalid table aggregate suffix")
    elif item.content_kind in {"figure", "chart", "diagram"}:
        suffix = "whole"
    else:
        suffix = f"span-{0:05d}-{len(item.snippet):05d}"
    expected_id = expected_prefix + suffix
    if item.evidence_id != expected_id:
        errors.append(
            f"{item.evidence_id}: non-canonical evidence ID; expected {expected_id}"
        )
    return errors


def _validate_locator_against_source_chunk(
    item: TechnicalEvidence,
    source_chunks: dict[tuple[str, str, str], dict],
) -> list[str]:
    locator = item.locator
    if not locator.source_chunk_id:
        return []
    owner = item.evidence_id
    key = (item.source_kind, item.document_id, locator.source_chunk_id)
    source = source_chunks.get(key)
    if source is None:
        return [f"{owner}: source_chunk_id cannot be resolved in retrieval trace"]

    errors: list[str] = []
    comparisons = {
        "physical_page": locator.physical_page,
        "content_kind": item.content_kind,
        "source_element_id": locator.source_element_id,
        "parent_element_id": locator.parent_element_id,
        "object_label": locator.object_label,
        "printed_page_label": locator.printed_page_label,
        "extraction_method": item.extraction_method,
        "crop_sha256": locator.crop_sha256,
    }
    for field, actual in comparisons.items():
        if source.get(field) != actual:
            errors.append(f"{owner}: locator {field} differs from source chunk")
    if source.get("document_version") not in {None, locator.document_sha256}:
        errors.append(f"{owner}: locator document hash differs from source chunk")
    source_bbox = source.get("bbox_pt")
    actual_bbox = list(locator.bbox_pt) if locator.bbox_pt is not None else None
    if source_bbox != actual_bbox:
        errors.append(f"{owner}: locator bbox differs from source chunk")
    source_span = source.get("text_span")
    actual_span = (
        locator.text_span.model_dump(mode="json")
        if locator.text_span is not None
        else None
    )
    if source_span != actual_span:
        errors.append(f"{owner}: locator text_span differs from source chunk")

    if item.content_kind == "table" and locator.table_cells:
        cell = locator.table_cells[0]
        digest = _table_cell_hash(cell)
        matches = [
            raw
            for raw in source.get("table_cells", [])
            if isinstance(raw, dict)
            and raw.get("row_index") == cell.row_index
            and raw.get("column_index") == cell.column_index
            and raw.get("sha256") == digest
        ]
        if not matches:
            errors.append(f"{owner}: exact table cell is absent from source chunk")
    else:
        if source.get("content_hash") != item.content_hash:
            errors.append(f"{owner}: evidence content hash differs from source chunk")

    if item.content_kind == "table" and not locator.table_cells:
        source_span_end = (source.get("text_span") or {}).get("end")
        source_text_length = source.get("text_length")
        if not isinstance(source_text_length, int) or source_text_length < 0:
            errors.append(f"{owner}: source chunk has invalid text_length")
            return errors
        rows = [
            int(raw["row_index"])
            for raw in source.get("table_cells", [])
            if isinstance(raw, dict) and isinstance(raw.get("row_index"), int)
        ]
        expected_suffix = table_aggregate_suffix(
            chunk_text_length=source_text_length,
            span_end=source_span_end,
            row_indices=rows,
            chunk_id=locator.source_chunk_id,
        )
        expected_id = item.evidence_id.rsplit(":", 1)[0] + ":" + expected_suffix
        if item.evidence_id != expected_id:
            errors.append(
                f"{owner}: table row-group ID does not match source chunk; "
                f"expected {expected_id}"
            )
    return errors


def _table_cell_hash(cell) -> str:
    payload = json.dumps(
        [
            cell.row_index,
            cell.column_index,
            cell.raw_text,
            cell.row_header,
            cell.column_header,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _contained_artifact_path(ref: TechnicalArtifactRef, root: Path) -> Path | None:
    artifact_path = Path(ref.path)
    if not artifact_path.is_absolute():
        artifact_path = root / artifact_path
    artifact_path = artifact_path.resolve()
    return artifact_path if artifact_path.is_relative_to(root) else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_refs(
    owner: str,
    evidence_ids: list[str],
    evidence_by_id: dict[str, TechnicalEvidence],
    errors: list[str],
    *,
    allowed_documents: set[str] | None = None,
) -> None:
    for evidence_id in evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            errors.append(f"{owner}: unknown evidence_id {evidence_id}")
        elif evidence.source_kind != "paper":
            errors.append(
                f"{owner}: paper technical claims require paper evidence: {evidence_id}"
            )
        elif (
            allowed_documents is not None
            and evidence.document_id not in allowed_documents
        ):
            errors.append(
                f"{owner}: evidence belongs to another paper: {evidence.document_id}"
            )


def _validate_context_refs(
    owner: str,
    evidence_ids: list[str],
    evidence_by_id: dict[str, TechnicalEvidence],
    errors: list[str],
) -> None:
    for evidence_id in evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            errors.append(f"{owner}: unknown context_evidence_id {evidence_id}")
        elif evidence.source_kind != "common":
            errors.append(
                f"{owner}: context_evidence_ids require common evidence: {evidence_id}"
            )


def _validate_numeric_observation(
    observation: ExperimentObservation,
    evidence_by_id: dict[str, TechnicalEvidence],
    errors: list[str],
) -> None:
    expected: list[str] = []
    if observation.value is not None:
        expected.extend(_numeric_literals(observation.value))
    if observation.value_min is not None:
        expected.append(f"{observation.value_min:g}")
    if observation.value_max is not None:
        expected.append(f"{observation.value_max:g}")
    _validate_numeric_tokens(
        observation.observation_id,
        expected,
        observation.evidence_ids,
        evidence_by_id,
        errors,
        unit=observation.unit,
    )


def _validate_numeric_text(
    owner: str,
    text: str,
    evidence_ids: list[str],
    evidence_by_id: dict[str, TechnicalEvidence],
    errors: list[str],
) -> None:
    expected = _numeric_literals(text)
    if expected:
        _validate_numeric_tokens(owner, expected, evidence_ids, evidence_by_id, errors)


def _validate_numeric_tokens(
    owner: str,
    expected: list[str],
    evidence_ids: list[str],
    evidence_by_id: dict[str, TechnicalEvidence],
    errors: list[str],
    *,
    unit: str | None = None,
) -> None:
    cited = [evidence_by_id[value] for value in evidence_ids if value in evidence_by_id]
    for number in expected:
        normalized_values = _observation_numeric_tokens(number, unit)
        matching = [
            item
            for item in cited
            if any(
                normalized and normalized in _number_tokens(item.snippet)
                for normalized in normalized_values
            )
        ]
        if not matching:
            errors.append(
                f"{owner}: numeric value {number!r} is absent from cited evidence"
            )
            continue
        precisely_located = any(
            _has_precise_numeric_locator(item, normalized)
            for item in matching
            for normalized in normalized_values
            if normalized in _number_tokens(item.snippet)
        )
        if not precisely_located:
            errors.append(
                f"{owner}: numeric evidence requires a text span, exact table cell, "
                f"or labeled visual locator for {number!r}"
            )


def _observation_numeric_tokens(value: str, unit: str | None) -> list[str]:
    """Return strict exact tokens, including a separately structured suffix.

    ``82`` + ``%`` first checks ``82%``.  The bare exact token remains a
    compatibility alternative for prose such as "five models"; it does not
    loosen matching to substrings, so ``5`` still cannot match ``4.5×`` or
    ``256``.
    """

    bare = _normalize_number_token(value)
    suffix = _numeric_unit_suffix(unit)
    if not suffix or bare.endswith(("%", "×")):
        return [bare]
    return [f"{bare}{suffix}", bare]


def _numeric_unit_suffix(unit: str | None) -> str:
    """Map narrowly defined unit phrases to their source-text suffix.

    Structured output sometimes emits ``× higher`` or ``percent lower`` as the
    unit instead of separating the direction. These remain exact-token checks:
    the qualifier is ignored, but the numeric suffix is not.
    """

    normalized = re.sub(r"\s+", " ", (unit or "").strip().casefold())
    qualifiers = (
        "higher|lower|faster|slower|increase|decrease|improvement|reduction|"
        "gain|overhead|retention|speedup|more|less"
    )
    if re.fullmatch(rf"(?:%|percent|percentage)(?: (?:{qualifiers}))?", normalized):
        return "%"
    if re.fullmatch(rf"(?:x|×|time|times)(?: (?:{qualifiers}))?", normalized):
        return "×"
    return ""


def _has_precise_numeric_locator(evidence: TechnicalEvidence, normalized: str) -> bool:
    if evidence.content_kind == "table":
        return any(
            any(
                normalized in _number_tokens(value or "")
                for value in (cell.raw_text, cell.row_header, cell.column_header)
            )
            for cell in evidence.locator.table_cells
        )
    if evidence.extraction_method == "vision":
        return bool(evidence.locator.crop_sha256 or evidence.locator.visual_artifact_id)
    return evidence.locator.text_span is not None


def analysis_audit_item_ids(dossier: TechnicalDossier) -> list[str]:
    return [owner for owner, _ in _analysis_claims(dossier)]


def _analysis_claims(dossier: TechnicalDossier):
    for section_name in ("technical_overview", "scope", "limitations"):
        section = getattr(dossier.analysis, section_name)
        for field_name in type(section).model_fields:
            values = getattr(section, field_name)
            if not isinstance(values, list):
                continue
            for index, value in enumerate(values):
                if hasattr(value, "evidence_ids") and hasattr(
                    value, "context_evidence_ids"
                ):
                    yield f"analysis.{section_name}.{field_name}[{index}]", value


def _compatible_observations(values: list[ExperimentObservation | None]) -> bool:
    observations = [value for value in values if value is not None]
    if len(observations) < 2:
        return False
    fields = (
        "metric",
        "baseline",
        "model",
        "hardware",
        "context_length",
        "concurrency",
        "dataset",
        "workload",
        "evaluation_mode",
        "unit",
    )
    for field in fields:
        normalized = {_norm(getattr(item, field)) for item in observations}
        if len(normalized) > 1:
            return False
    return True


def _normalize_number_token(value: str) -> str:
    return re.sub(r"[\s,]", "", value).lower().replace("x", "×")


def _number_tokens(value: str) -> set[str]:
    tokens = {
        _normalize_number_token(number) for number in _numeric_literals(value)
    }
    # PDF and Vision extraction commonly render a thousands separator as a
    # regular, non-breaking, or narrow non-breaking space (``28 843``). Keep
    # the primary scanner strict, then add the complete grouped value as an
    # exact alternative. A whitespace-separated numeric list may create one
    # harmless aggregate token, but never aliases any individual expected
    # value (for example ``64 128 256`` cannot satisfy ``28,843``).
    spaced_thousands = re.compile(
        r"(?<![A-Za-z0-9.\-])[-+]?\d{1,3}"
        r"(?:[ \u00a0\u202f]\d{3})+(?:\.\d+)?(?:\s*[×xX%])?"
    )
    tokens.update(
        _normalize_number_token(match.group(0))
        for match in spaced_thousands.finditer(value)
    )
    lowered = value.casefold()
    tokens.update(
        number
        for word, number in NUMBER_WORDS.items()
        if re.search(rf"\b{word}\b", lowered)
    )
    return tokens


def _numeric_literals(value: str) -> list[str]:
    """Extract numeric literals without treating set notation as one integer.

    ``NUMBER_RE`` deliberately accepts thousands separators, but mathematical
    sets such as ``{64,128,256,512,1024}`` use the same comma character.  A
    brace-delimited token, or a comma token that is not a syntactically valid
    thousands-grouped integer, is therefore expanded into its individual
    values.  Ordinary values such as ``1,740`` and ``30,583`` remain atomic.
    """

    values: list[str] = []
    scan_value = _mask_ascii_numeric_range_separators(value)
    for match in NUMBER_RE.finditer(scan_value):
        raw = match.group(0)
        if "," not in raw:
            values.append(raw)
            continue
        before = value[: match.start()].rstrip()
        after = value[match.end() :].lstrip()
        brace_list = before.endswith("{") and after.startswith("}")
        numeric_part = raw.rstrip("×xX% ")
        valid_thousands = bool(
            re.fullmatch(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", numeric_part)
        )
        if brace_list or not valid_thousands:
            suffix = raw[len(numeric_part) :]
            parts = numeric_part.split(",")
            values.extend(
                part + (suffix if index == len(parts) - 1 else "")
                for index, part in enumerate(parts)
                if part
            )
        else:
            values.append(raw)
    return values


def _mask_ascii_numeric_range_separators(value: str) -> str:
    """Replace unambiguous ASCII numeric range hyphens with equal-width spaces.

    Without this normalization, the upper bound of ``3.3×-27.5×`` is parsed as
    the negative value ``-27.5×``. A leading/prose negative remains untouched.
    Digit-to-digit ranges are accepted only when the left number is not embedded
    in an identifier such as ``LLaMA-3.1-8B`` or ``A100-80GB``.
    """

    characters = list(value)
    for index, character in enumerate(value):
        if character != "-" or index == 0 or index + 1 >= len(value):
            continue
        if not value[index + 1].isdigit():
            continue
        previous = value[index - 1]
        if previous in {"×", "%"} or (
            previous.isdigit() and _left_number_is_not_identifier(value, index)
        ):
            characters[index] = " "
    return "".join(characters)


def _left_number_is_not_identifier(value: str, separator_index: int) -> bool:
    cursor = separator_index - 1
    while cursor >= 0 and (value[cursor].isdigit() or value[cursor] in {".", ","}):
        cursor -= 1
    if cursor < 0:
        return True
    prefix = value[cursor]
    if prefix.isalpha() or prefix == "_":
        return False
    if prefix in {"+", "-"} and cursor > 0 and value[cursor - 1].isalnum():
        return False
    return True


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
