"""Adapters for the technical agent's immutable paper_analysis JSON outputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterator

from .agent import InputContractError


TECHNOLOGIES = {
    "SW-01": {"name": "RDKV", "approach": "SW"},
    "HW-01": {"name": "Photonic-CXL", "approach": "HW"},
}


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputContractError(f"{label} must be a JSON object")
    return value


def _iter_claims(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], dict[str, Any]]]:
    if isinstance(value, dict):
        if isinstance(value.get("text"), str) and isinstance(value.get("evidence_ids"), list):
            yield path, value
        for key, child in value.items():
            if key not in {"evidence_ids", "context_evidence_ids"}:
                yield from _iter_claims(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_claims(child, (*path, str(index)))


def _criterion_ids(path: tuple[str, ...], text: str) -> set[str]:
    """Map a technical claim to domain criteria without calling another model."""

    normalized = text.lower()
    joined_path = ".".join(path)
    criteria: set[str] = set()

    keyword_map = {
        "capacity": ("capacity", "memory", "hbm", "cache size", " tb", " gb", "context length", "메모리", "용량"),
        "quality": ("accuracy", "quality", "distortion", "longbench", "ruler", "infinitebench", "정확", "품질", "왜곡"),
        "latency_predictability": ("latency", "ttft", "tpot", "time-to-first-token", "tail", "지연"),
        "throughput": ("throughput", "speedup", "decoding speed", "bandwidth", "처리량", "대역폭"),
        "gpu_compatibility": ("gpu", "a100", "h100", "h200", "cuda", "kernel", "flashattention", "hbm"),
        "dedicated_hardware_dependency": ("cxl", "photonic", "optical", "fiber", "appliance", "pf-nic", "pcie", "전용"),
        "deployment_complexity": ("integration", "kernel", "layout", "adapter", "dma", "load/store", "appliance", "통합", "배포"),
        "maturity": ("emulation", "simulation", "pending", "prototype", "physical", "future work", "validation", "실증", "시뮬레이션", "에뮬레이션"),
        "customer_value": ("cost", "customer", "operational", "service cost", "비용", "고객"),
        "domain_fit": ("long-context", "long context", "llm serving", "inference", "conversation", "enterprise", "document", "qa", "장문맥", "추론"),
    }
    for criterion, keywords in keyword_map.items():
        if any(keyword in normalized for keyword in keywords):
            criteria.add(criterion)

    if ".scope.domains." in f".{joined_path}." or ".scope.target_tasks." in f".{joined_path}.":
        criteria.add("domain_fit")
    if "evaluated_settings" in joined_path:
        criteria.update({"domain_fit", "maturity"})
    if joined_path.startswith("limitations"):
        criteria.update({"maturity", "domain_fit"})
    if "experimental_results" in joined_path and not criteria:
        criteria.update({"domain_fit", "maturity"})
    if "mechanisms" in joined_path or "core_approach" in joined_path:
        criteria.add("deployment_complexity")
    return criteria


def _claim_texts(section: Any) -> list[str]:
    return [
        claim["text"]
        for _, claim in _iter_claims(section)
        if isinstance(claim.get("text"), str) and claim["text"].strip()
    ]


def _convert_one(raw: dict[str, Any], technology_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if technology_id not in TECHNOLOGIES:
        raise InputContractError(f"unsupported technology_id: {technology_id}")
    raw = _require_mapping(raw, f"{technology_id} analysis")
    if raw.get("status") != "succeeded":
        raise InputContractError(
            f"{technology_id} technical analysis status must be 'succeeded'; got {raw.get('status')!r}"
        )

    analysis = _require_mapping(raw.get("analysis"), f"{technology_id}.analysis")
    paper = _require_mapping(raw.get("paper"), f"{technology_id}.paper")
    raw_registry = raw.get("evidence_registry")
    if not isinstance(raw_registry, list):
        raise InputContractError(f"{technology_id}.evidence_registry must be a list")

    claims = list(_iter_claims(analysis))
    referenced_raw_ids: set[str] = set()
    criteria_by_raw_id: dict[str, set[str]] = {}
    conditions_by_raw_id: dict[str, set[str]] = {}
    inferred_only_by_raw_id: dict[str, bool] = {}

    for path, claim in claims:
        raw_ids = list(
            dict.fromkeys(
                str(item)
                for item in (
                    list(claim.get("evidence_ids", []))
                    + list(claim.get("context_evidence_ids", []))
                )
            )
        )
        referenced_raw_ids.update(raw_ids)
        claim_criteria = _criterion_ids(path, claim["text"])
        is_condition = any(key in path for key in ("evaluated_settings", "operating_conditions", "out_of_scope"))
        is_inferred = claim.get("claim_type") == "inferred"
        for raw_id in raw_ids:
            criteria_by_raw_id.setdefault(raw_id, set()).update(claim_criteria)
            if is_condition:
                conditions_by_raw_id.setdefault(raw_id, set()).add(claim["text"])
            inferred_only_by_raw_id[raw_id] = inferred_only_by_raw_id.get(raw_id, True) and is_inferred

    registry_by_raw_id: dict[str, dict[str, Any]] = {}
    for item in raw_registry:
        item = _require_mapping(item, f"{technology_id}.evidence_registry item")
        raw_id = item.get("evidence_id")
        if not isinstance(raw_id, str) or not raw_id:
            raise InputContractError(f"{technology_id} evidence item is missing evidence_id")
        if raw_id in registry_by_raw_id:
            raise InputContractError(f"{technology_id} duplicate evidence_id: {raw_id}")
        registry_by_raw_id[raw_id] = item

    missing = referenced_raw_ids - set(registry_by_raw_id)
    if missing:
        raise InputContractError(
            f"{technology_id} analysis references missing evidence: {sorted(missing)}"
        )

    converted_evidence: dict[str, Any] = {}
    converted_ids: list[str] = []
    for raw_id in sorted(referenced_raw_ids):
        item = registry_by_raw_id[raw_id]
        evidence_id = f"{technology_id}::{raw_id}"
        converted_ids.append(evidence_id)
        converted_evidence[evidence_id] = {
            "id": evidence_id,
            "doc_id": technology_id,
            "excerpt": str(item.get("snippet") or "").strip(),
            "page": item.get("page"),
            "location": item.get("section"),
            "url": None,
            "conditions": sorted(conditions_by_raw_id.get(raw_id, set())),
            "criterion_ids": sorted(criteria_by_raw_id.get(raw_id, set())),
            "basis": "inference" if inferred_only_by_raw_id.get(raw_id, False) else "direct",
            "collected_at": raw.get("run", {}).get("finished_at") if isinstance(raw.get("run"), dict) else None,
            "is_demo": False,
        }
        if not converted_evidence[evidence_id]["excerpt"]:
            raise InputContractError(f"{technology_id}/{raw_id} has an empty snippet")

    overview = _require_mapping(analysis.get("technical_overview", {}), f"{technology_id}.technical_overview")
    scope = _require_mapping(analysis.get("scope", {}), f"{technology_id}.scope")
    limitations_section = _require_mapping(analysis.get("limitations", {}), f"{technology_id}.limitations")

    summary_parts = []
    for key in ("problem_definition", "core_approach", "novelty"):
        summary_parts.extend(_claim_texts(overview.get(key, [])))
    summary = " ".join(summary_parts[:5]).strip() or str(paper.get("title") or technology_id)

    experimental_conditions = []
    for key in ("evaluated_settings", "operating_conditions", "target_tasks", "out_of_scope"):
        experimental_conditions.extend(_claim_texts(scope.get(key, [])))

    limitations = []
    for key in (
        "author_stated",
        "generalization_constraints",
        "compute_constraints",
        "data_constraints",
        "reproducibility_constraints",
        "inferred",
    ):
        limitations.extend(_claim_texts(limitations_section.get(key, [])))
    limitations.extend(_claim_texts(scope.get("out_of_scope", [])))

    technology = TECHNOLOGIES[technology_id]
    technical_summary = {
        "technology_id": technology_id,
        "name": technology["name"],
        "approach": technology["approach"],
        "summary": summary,
        "experimental_conditions": list(dict.fromkeys(experimental_conditions)),
        "limitations": list(dict.fromkeys(limitations)),
        "evidence_ids": converted_ids,
    }
    document = {
        "technology_id": technology_id,
        "paper": deepcopy(paper),
        "source_schema_version": raw.get("schema_version"),
        "source_status": raw.get("status"),
        "quality": deepcopy(raw.get("quality", {})),
    }
    return technical_summary, converted_evidence, document


def adapt_paper_analyses(
    base_state: dict[str, Any],
    *,
    sw_analysis: dict[str, Any],
    hw_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Create the shared domain-agent state without changing teammate outputs.

    The caller supplies an existing state containing config.domain. Technical
    evidence and assessments are replaced with normalized SW-01/HW-01 data.
    Unrelated non-demo evidence and other role assessments are preserved.
    """

    state = deepcopy(_require_mapping(base_state, "base_state"))
    if not isinstance(state.get("config", {}).get("domain"), dict):
        raise InputContractError("base_state.config.domain must be an object")

    sw_summary, sw_evidence, sw_document = _convert_one(sw_analysis, "SW-01")
    hw_summary, hw_evidence, hw_document = _convert_one(hw_analysis, "HW-01")

    existing_evidence = state.get("evidence", {})
    if not isinstance(existing_evidence, dict):
        raise InputContractError("base_state.evidence must be an object")
    preserved_evidence = {
        key: deepcopy(value)
        for key, value in existing_evidence.items()
        if isinstance(value, dict)
        and not value.get("is_demo", False)
        and value.get("doc_id") not in {"SW-01", "HW-01"}
    }
    new_evidence = {**sw_evidence, **hw_evidence}
    collisions = set(preserved_evidence) & set(new_evidence)
    if collisions:
        raise InputContractError(f"evidence ID collision: {sorted(collisions)}")
    state["evidence"] = {**preserved_evidence, **new_evidence}

    assessments = state.get("assessments", {})
    if not isinstance(assessments, dict):
        raise InputContractError("base_state.assessments must be an object")
    state["assessments"] = {
        **deepcopy(assessments),
        "technical": {
            "status": "completed",
            "technologies": [sw_summary, hw_summary],
        },
    }

    documents = state.get("documents", {})
    if not isinstance(documents, dict):
        documents = {}
    state["documents"] = {
        **deepcopy(documents),
        "SW-01": sw_document,
        "HW-01": hw_document,
    }
    return state
