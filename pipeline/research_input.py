"""Read saved research without importing or executing the research runtime.

The bundle is the lossless source of truth. ``papers`` and domain state are
bounded compatibility views; omitted context is recorded, never silently
presented as a complete analysis or as a new upstream audit.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any


PAPER_CONTEXT_CHARS = 36_000
DOMAIN_CONTEXT_CHARS = 85_000
CRITERIA = (
    "capacity", "quality", "latency_predictability", "throughput",
    "gpu_compatibility", "dedicated_hardware_dependency",
    "deployment_complexity", "maturity", "customer_value", "domain_fit",
)
_FIELD_ORDER = {
    "technical_overview": (
        "problem_definition", "core_approach", "experimental_results",
        "requirements", "mechanisms", "inference_process", "novelty",
        "training_process",
    ),
    "scope": (
        "evaluated_settings", "operating_conditions", "out_of_scope",
        "target_tasks", "domains", "author_claimed_scope", "inferred_scope",
        "modalities",
    ),
    "limitations": (
        "author_stated", "generalization_constraints", "compute_constraints",
        "reproducibility_constraints", "inferred", "data_constraints",
    ),
}


def _size(value: Any) -> int:
    # Match the default json.dumps spacing used by the stakeholder input guard.
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _contained(root: Path, value: str) -> Path:
    path = Path(value)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Saved research artifact escapes its directory: {value}")
    return path


def _refs(claim: dict) -> set[str]:
    return set(claim.get("evidence_ids", [])) | set(claim.get("context_evidence_ids", []))


def _analysis_rows(dossier: dict):
    """Interleave facets and fields so a size limit cannot erase one facet."""
    queues = []
    analysis = dossier["analysis"]
    for section, order in _FIELD_ORDER.items():
        fields = analysis.get(section, {})
        for field in (*order, *(key for key in fields if key not in order and key != "not_reported")):
            rows = fields.get(field, [])
            if rows:
                queues.append([(section, field, index, claim) for index, claim in enumerate(rows)])
    for index in range(max((len(queue) for queue in queues), default=0)):
        for queue in queues:
            if index < len(queue):
                yield queue[index]


def _paper_evidence(item: dict) -> dict:
    locator = item.get("locator", {})
    return {
        "evidence_id": item["evidence_id"], "document_id": item["document_id"],
        "snippet": item["snippet"], "source_kind": item["source_kind"],
        "page": locator.get("physical_page"),
        "section": "; ".join(locator.get("section_path", [])) or None,
        "chunk_id": locator.get("source_chunk_id"),
        "content_hash": item.get("content_hash"),
        "content_kind": item.get("content_kind", "text"),
    }


def _project_paper(dossier: dict, run: dict, evidence: dict[str, dict]) -> tuple[dict, dict]:
    paper_id = dossier["paper"]["paper_id"]
    warning = (
        "저장된 기술조사 1.0.0 dossier에서 선택한 제한된 호환 입력입니다. "
        "전체 주장·관측·제약·근거 위치·비교 결과는 원본 bundle에 보존되어 있습니다. "
        "누락된 문맥은 반증 또는 근거 없음으로 해석하지 마십시오."
    )
    projection = {
        "schema_version": "1.1.0", "status": "succeeded",
        "paper": deepcopy(dossier["paper"]),
        "analysis": {
            section: {"not_reported": deepcopy(dossier["analysis"].get(section, {}).get("not_reported", []))}
            for section in _FIELD_ORDER
        },
        "evidence_registry": [],
        "quality": {"warnings": [warning]},
        "run": deepcopy(run["run"]),
        "diagnostics": [],
        "projection_provenance": {
            "source_schema_version": run["schema_version"],
            "source_dossier_version": dossier.get("dossier_version"),
            "source_job_id": run["run"].get("job_id"),
            "adapter_version": "saved-research-1.0.0", "is_complete": False,
        },
    }
    projection["run"]["run_id"] = run["run"].get("job_id")
    if _size(projection) > PAPER_CONTEXT_CHARS:
        raise ValueError(f"Paper metadata and explicit gaps exceed context budget: {paper_id}")
    included_paths, excluded, included_evidence = [], [], set()
    for section, field, index, claim in _analysis_rows(dossier):
        path = f"analysis.{section}.{field}[{index}]"
        refs = _refs(claim)
        # The old consumers accept paper-owned sources only; common context is
        # retained in the lossless bundle instead of relabelled as paper evidence.
        if any(evidence[eid]["source_kind"] != "paper" or evidence[eid]["document_id"] != paper_id for eid in refs):
            excluded.append({"path": path, "reason": "legacy_consumer_cannot_represent_common_context"})
            continue
        old_count = len(projection["evidence_registry"])
        rows = projection["analysis"][section].setdefault(field, [])
        rows.append(deepcopy(claim))
        new_ids = sorted(refs - included_evidence)
        projection["evidence_registry"].extend(_paper_evidence(evidence[eid]) for eid in new_ids)
        if _size(projection) > PAPER_CONTEXT_CHARS:
            rows.pop()
            del projection["evidence_registry"][old_count:]
            excluded.append({"path": path, "reason": "bounded_context_budget"})
        else:
            included_paths.append(path)
            included_evidence.update(refs)
    selected_texts = {
        claim["text"] for section in projection["analysis"].values()
        for field, rows in section.items() if field != "not_reported" for claim in rows
    }
    included_claims = [claim["claim_id"] for claim in dossier.get("claims", []) if claim["text"] in selected_texts]
    all_claims = {claim["claim_id"] for claim in dossier.get("claims", [])}
    if any(not any(rows for field, rows in projection["analysis"][section].items() if field != "not_reported") for section in _FIELD_ORDER):
        raise ValueError(f"Context budget cannot cover all three technical facets: {paper_id}")
    return projection, {
        "paper_id": paper_id, "context_chars": _size(projection),
        "context_budget_chars": PAPER_CONTEXT_CHARS,
        "included_analysis_paths": included_paths, "excluded_analysis": excluded,
        "included_claim_ids": included_claims,
        "excluded_claim_ids": sorted(all_claims - set(included_claims)),
        "included_evidence_ids": sorted(included_evidence),
        "excluded_evidence_ids": sorted(
            eid for eid, item in evidence.items()
            if item["document_id"] == paper_id and eid not in included_evidence
        ),
        "observation_ids_preserved_in_bundle": [item["observation_id"] for item in dossier.get("experiment_observations", [])],
    }


def load_saved_research(result_dir: str | Path) -> dict:
    """Validate local artifacts and return original data plus bounded projections.

    This performs no source-document parsing, embedding, network or LLM calls.
    Artifact hashes are checked; source PDFs and semantic audits are not rerun.
    """
    source = Path(result_dir).expanduser().resolve()
    run_path = source if source.is_file() else source / "run.json"
    root = run_path.parent
    run = _read(run_path)
    if run.get("schema_version") != "1.0.0" or run.get("status") != "succeeded":
        raise ValueError("Saved research must be a succeeded TechnicalResearchEnvelope 1.0.0")
    hashes = {"run.json": hashlib.sha256(run_path.read_bytes()).hexdigest()}
    artifacts = {}
    for item in run.get("artifacts", []):
        path = _contained(root, item["path"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"Saved research artifact hash mismatch: {item['path']}")
        if path in artifacts:
            raise ValueError(f"Duplicate research artifact: {item['path']}")
        artifacts[path] = item
        hashes[str(path.relative_to(root))] = digest
    registry_path = _contained(root, run["evidence_registry_path"])
    if registry_path not in artifacts or artifacts[registry_path]["type"] != "evidence_registry":
        raise ValueError("Evidence registry must be a hash-checked declared artifact")
    evidence = {}
    for row in _read(registry_path):
        eid = row["evidence_id"]
        if eid in evidence:
            raise ValueError(f"Duplicate research evidence ID: {eid}")
        if not row.get("snippet") or not isinstance(row.get("locator"), dict):
            raise ValueError(f"Research evidence lacks text or locator: {eid}")
        evidence[eid] = row
    dossiers = deepcopy(run.get("dossiers", []))
    comparison = deepcopy(run.get("comparison"))
    if len(dossiers) != 2 or not isinstance(comparison, dict):
        raise ValueError("This integration requires the selected two-paper research bundle")
    declared_dossiers = {
        value["paper"]["paper_id"]: value
        for path, item in artifacts.items() if item["type"] == "dossier"
        for value in [_read(path)]
    }
    comparison_files = [path for path, item in artifacts.items() if item["type"] == "comparison"]
    if len(comparison_files) != 1 or _read(comparison_files[0]) != comparison:
        raise ValueError("Inline comparison differs from its declared artifact")
    technology_map = {}
    for dossier in dossiers:
        paper = dossier["paper"]
        pid = paper["paper_id"]
        if declared_dossiers.get(pid) != dossier:
            raise ValueError(f"Inline dossier differs from its declared artifact: {pid}")
        arxiv = str(paper.get("arxiv_id") or "").split("v")[0]
        technology = {"2605.08317": "SW-01", "2607.27187": "HW-01"}.get(arxiv)
        if technology is None or technology in technology_map.values() or pid in technology_map:
            raise ValueError(f"Unexpected or duplicate paper identity: {pid}")
        technology_map[pid] = technology
        refs = set(dossier.get("evidence_ids", []))
        for _, _, _, claim in _analysis_rows(dossier):
            refs.update(_refs(claim))
        for field in ("claims", "experiment_observations", "critical_inventory"):
            for claim in dossier.get(field, []):
                refs.update(_refs(claim))
        if refs - evidence.keys():
            raise ValueError(f"Dossier has unresolved evidence references: {pid}")
    papers, manifests = [], []
    for dossier in sorted(dossiers, key=lambda d: technology_map[d["paper"]["paper_id"]] != "SW-01"):
        paper, manifest = _project_paper(dossier, run, evidence)
        papers.append(paper)
        manifests.append(manifest)
    return {
        "run": run, "dossiers": dossiers, "comparison": comparison,
        "evidence": evidence, "technology_map": technology_map, "papers": papers,
        "context_manifest": {
            "adapter_version": "saved-research-1.0.0", "source_directory": str(root),
            "source_run_id": run["run"].get("job_id"), "source_artifact_hashes": hashes,
            "artifact_integrity": "verified", "source_pdf_revalidation": "not_performed",
            "semantic_audit": "upstream_record_preserved_not_rerun",
            "selection_policy": "whole_claims_interleaved_by_facet_and_field_with_complete_referenced_snippets",
            "originals_preserved": True, "papers": manifests,
            "legacy_papers_chars": _size(papers),
        },
    }


def _claim_lines(paper: dict, section: str, fields: tuple[str, ...]) -> list[str]:
    return [f"[{claim['claim_type']}] {claim['text']}"
            for field in fields for claim in paper["analysis"].get(section, {}).get(field, [])]


def _domain_evidence(item: dict, technology_id: str, finished_at: str | None) -> dict:
    locator = item.get("locator", {})
    location = "; ".join(str(value) for value in (
        "/".join(locator.get("section_path", [])), locator.get("object_label"),
        f"element={locator['element_id']}" if locator.get("element_id") else "",
    ) if value)
    return {
        "id": item["evidence_id"], "doc_id": technology_id,
        "excerpt": item["snippet"], "page": locator.get("physical_page"),
        "location": location or None, "url": None, "conditions": [],
        "criterion_ids": [], "basis": "direct", "collected_at": finished_at,
        "is_demo": False,
    }


def _domain_config(request: dict) -> dict:
    supplied = request.get("domain")
    if not isinstance(supplied, dict):
        domains = request.get("domains") or []
        supplied = domains[0] if domains and isinstance(domains[0], dict) else {}
    raw_requirements = supplied.get("requirements", request.get("requirements", []))
    if isinstance(raw_requirements, dict):
        raw_requirements = [dict(value, criterion_id=key) if isinstance(value, dict)
                            else {"criterion_id": key, "target": str(value)}
                            for key, value in raw_requirements.items()]
    if not isinstance(raw_requirements, list):
        raw_requirements = []
    by_id = {item["criterion_id"]: item for item in raw_requirements
             if isinstance(item, dict) and item.get("criterion_id") in CRITERIA}
    requirements = []
    for criterion in CRITERIA:
        item = by_id.get(criterion, {})
        target = str(item.get("target") or "미지정: 사용자 목표 요구조건이 제공되지 않았습니다.")
        requirements.append({
            "criterion_id": criterion, "target": target,
            "priority": item.get("priority") if item.get("priority") in {"must", "should", "could"} else "should",
            "rationale": str(item.get("rationale") or "제공된 요구조건만 사용하며 수치 목표를 추정하지 않습니다."),
        })
    users = supplied.get("target_users", request.get("target_users", []))
    if isinstance(users, str):
        users = [users]
    return {
        "name": str(supplied.get("name") or "미지정 도메인"),
        "scenario": str(supplied.get("scenario") or "미지정: 사용자 운영 시나리오가 제공되지 않았습니다."),
        "target_users": users or ["미지정"], "requirements": requirements,
        "shared_evidence_ids": [],
    }


def to_domain_state(bundle: dict, request: dict, *, run_id: str, as_of: str) -> dict:
    """Create the domain evaluator's strict state without renaming evidence IDs."""
    state = {
        "run_id": run_id, "as_of": as_of, "config": {"domain": _domain_config(request)},
        "assessments": {"technical": {"status": "completed", "technologies": []}},
        "evidence": {}, "review": {"round": 0},
    }
    finished = bundle["run"]["run"].get("finished_at")
    included_observations, excluded_observations = [], []
    for paper in bundle["papers"]:
        pid = paper["paper"]["paper_id"]
        technology = bundle["technology_map"][pid]
        dossier = next(d for d in bundle["dossiers"] if d["paper"]["paper_id"] == pid)
        ids = sorted(item["evidence_id"] for item in paper["evidence_registry"])
        summary = _claim_lines(paper, "technical_overview", _FIELD_ORDER["technical_overview"])
        conditions = _claim_lines(paper, "scope", _FIELD_ORDER["scope"])
        limitations = _claim_lines(paper, "limitations", _FIELD_ORDER["limitations"])
        for section in _FIELD_ORDER:
            limitations.extend("미보고: " + value for value in paper["analysis"][section].get("not_reported", []))
        limitations.extend("미검증: " + item["topic"] + "; " + item["reason"] for item in dossier.get("unverified_items", []))
        limitations.append("입력은 제한된 기술 문맥이며 전체 원본은 bundle에 보존됨. 사용자 요구조건 미지정 시 적합·부적합을 단정하지 말 것.")
        result = {
            "technology_id": technology, "name": "RDKV" if technology == "SW-01" else "Photonic-CXL",
            "approach": "SW" if technology == "SW-01" else "HW",
            "summary": "\n".join(summary) or paper["paper"]["title"],
            "experimental_conditions": conditions, "limitations": limitations,
            "evidence_ids": ids,
        }
        state["assessments"]["technical"]["technologies"].append(result)
        for eid in ids:
            state["evidence"][eid] = _domain_evidence(bundle["evidence"][eid], technology, finished)
    if _size(state) > DOMAIN_CONTEXT_CHARS:
        raise ValueError("Selected domain input exceeds its bounded context budget")
    observation_queue = [
        (dossier, dossier["experiment_observations"][index])
        for index in range(max(len(d.get("experiment_observations", [])) for d in bundle["dossiers"]))
        for dossier in bundle["dossiers"]
        if index < len(dossier.get("experiment_observations", []))
    ]
    for dossier, observation in observation_queue:
        technology = bundle["technology_map"][dossier["paper"]["paper_id"]]
        result = next(item for item in state["assessments"]["technical"]["technologies"] if item["technology_id"] == technology)
        # Keep the exact observation and its measured/emulated/simulated mode
        # together. Interleave papers so neither paper consumes the budget first.
        text = "실험 관측: " + json.dumps(observation, ensure_ascii=False)
        additions = set(observation["evidence_ids"]) - set(state["evidence"])
        result["experimental_conditions"].append(text)
        old_ids = list(result["evidence_ids"])
        result["evidence_ids"] = sorted(set(old_ids) | set(observation["evidence_ids"]))
        for eid in additions:
            state["evidence"][eid] = _domain_evidence(bundle["evidence"][eid], technology, finished)
        if _size(state) > DOMAIN_CONTEXT_CHARS:
            result["experimental_conditions"].pop()
            result["evidence_ids"] = old_ids
            for eid in additions:
                del state["evidence"][eid]
            excluded_observations.append(observation["observation_id"])
        else:
            included_observations.append(observation["observation_id"])
    state["context_manifest"] = {
        "included_evidence_ids": sorted(state["evidence"]),
        "excluded_evidence_ids": sorted(set(bundle["evidence"]) - set(state["evidence"])),
        "included_observation_ids": included_observations,
        "excluded_observation_ids": excluded_observations,
        "domain_input_chars": _size(state), "domain_input_budget_chars": DOMAIN_CONTEXT_CHARS,
        "domain_scope": "first_requested_domain",
    }
    return state
