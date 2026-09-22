from __future__ import annotations

import json

from paper_review_agent.technical_models import (
    _augment_query_plan,
    _evidence_payload,
    _evidence_prompt_json,
    _is_unscoped_arabic_benchmark_table_expansion,
    _normalize_absolute_observation_baselines,
    _strip_comparison_workflow_metadata,
    finalize_dossier_extraction,
)
from paper_review_agent.schemas import (
    LimitationsAnalysis,
    PaperAnalysis,
    PaperMetadata,
    ScopeAnalysis,
    TechnicalOverview,
)
from paper_review_agent.technical_schemas import (
    CriticalClaimItem,
    DossierExtraction,
    EvidenceLocator,
    ExperimentObservation,
    ResearchQueryPlan,
    TableCellLocator,
    TechnicalClaim,
    TechnicalComparison,
    TechnicalEvidence,
    ComparisonCell,
    TextSpan,
)


def _located_table_evidence() -> TechnicalEvidence:
    return TechnicalEvidence(
        evidence_id=(
            "paper:paper-a@aaaaaaaaaaaa:p0007:table-01:cell-r03-c04"
        ),
        source_kind="paper",
        document_id="paper-a",
        content_kind="table",
        extraction_method="vision",
        snippet="Table 1 reports measured throughput of 128 GB/s per host.",
        content_hash="b" * 64,
        locator=EvidenceLocator(
            document_sha256="a" * 64,
            physical_page=7,
            printed_page_label="5",
            section_path=["Evaluation", "Memory fabric"],
            element_id="table-01",
            object_label="Table 1",
            parent_element_id="caption-01",
            bbox_pt=(72.0, 144.0, 540.0, 360.0),
            page_size_pt=(612.0, 792.0),
            coordinate_system="pdf_top_left_points",
            text_span=TextSpan(start=12, end=68),
            table_cells=[
                TableCellLocator(
                    row_index=3,
                    column_index=4,
                    raw_text="128 GB/s",
                    row_header="Per-host bandwidth",
                    column_header="16 hosts",
                )
            ],
            visual_artifact_id="visual-paper-a-table-01",
            crop_sha256="c" * 64,
        ),
    )


def test_compact_evidence_payload_preserves_model_relevant_locator_fields():
    evidence = _located_table_evidence()
    before = evidence.model_dump(mode="json")

    payload = _evidence_payload(evidence)

    assert payload == {
        "evidence_id": evidence.evidence_id,
        "source_kind": "paper",
        "document_id": "paper-a",
        "content_kind": "table",
        "extraction_method": "vision",
        "snippet": evidence.snippet,
        "locator": {
            "physical_page": 7,
            "printed_page_label": "5",
            "section_path": ["Evaluation", "Memory fabric"],
            "element_id": "table-01",
            "object_label": "Table 1",
            "parent_element_id": "caption-01",
            "bbox_pt": [72.0, 144.0, 540.0, 360.0],
            "text_span": {"start": 12, "end": 68},
            "table_cells": [
                {
                    "row_index": 3,
                    "column_index": 4,
                    "raw_text": "128 GB/s",
                    "row_header": "Per-host bandwidth",
                    "column_header": "16 hosts",
                }
            ],
            "crop_sha256": "c" * 64,
        },
    }
    # Prompt projection is read-only; deterministic validators still receive
    # the complete, unchanged TechnicalEvidence object.
    assert evidence.model_dump(mode="json") == before


def test_evidence_prompt_serialization_omits_registry_metadata_and_is_smaller():
    evidence = _located_table_evidence()
    compact_json = _evidence_prompt_json([evidence])
    compact = json.loads(compact_json)[0]
    full_json = json.dumps(
        [evidence.model_dump(mode="json")],
        ensure_ascii=False,
        separators=(",", ":"),
    )

    assert "content_hash" not in compact
    assert {
        "document_sha256",
        "page_size_pt",
        "coordinate_system",
        "visual_artifact_id",
    }.isdisjoint(compact["locator"])
    assert len(compact_json.encode()) <= len(full_json.encode()) * 0.8
    # The shared serializer is minified because the same payload is embedded
    # in extraction, audit, and comparison prompts.
    assert '": ' not in compact_json


def _empty_analysis() -> PaperAnalysis:
    return PaperAnalysis(
        technical_overview=TechnicalOverview(),
        scope=ScopeAnalysis(),
        limitations=LimitationsAnalysis(),
    )


def test_absolute_observation_uses_explicit_workload_baseline_configuration():
    observation = ExperimentObservation(
        observation_id="ttft-100",
        metric="mean TTFT",
        value="8156",
        unit="ms",
        baseline="32 TB PF Memory Appliance configuration",
        workload="multi-turn conversation; 2 TB baseline",
        evaluation_mode="simulated",
        evidence_ids=["paper:evidence"],
        confidence=0.99,
    )
    ratio = observation.model_copy(
        update={
            "observation_id": "ratio-300",
            "metric": "TTFT ratio",
            "value": "6.6",
            "unit": "× higher",
        }
    )
    extraction = DossierExtraction(
        analysis=_empty_analysis(),
        claims=[],
        critical_inventory=[
            CriticalClaimItem(
                inventory_id="excluded",
                category="scope",
                summary="not applicable",
                disposition="excluded",
                reason="test fixture",
            )
        ],
        experiment_observations=[observation, ratio],
    )

    normalized = _normalize_absolute_observation_baselines(extraction)

    assert normalized.experiment_observations[0].baseline == "2 TB baseline"
    assert (
        normalized.experiment_observations[1].baseline
        == "32 TB PF Memory Appliance configuration"
    )


def test_inventory_evidence_is_derived_from_its_resolved_linked_claim():
    evidence = _located_table_evidence()
    claim = TechnicalClaim(
        claim_id="bandwidth",
        text="Per-host bandwidth is 128 GB/s.",
        claim_type="observed_result",
        evidence_ids=[evidence.evidence_id],
        confidence=0.99,
        critical=True,
    )
    extraction = DossierExtraction(
        analysis=_empty_analysis(),
        claims=[claim],
        critical_inventory=[
            CriticalClaimItem(
                inventory_id="bandwidth-inventory",
                category="result",
                summary=claim.text,
                disposition="extracted",
                claim_ids=[claim.claim_id],
                evidence_ids=["paper:malformed:table-reference"],
            )
        ],
        experiment_observations=[],
    )

    normalized = finalize_dossier_extraction(
        extraction,
        evidence=[evidence],
        paper_id="paper-a",
    )

    assert normalized.critical_inventory[0].evidence_ids == [evidence.evidence_id]


def test_query_plan_always_searches_prefill_setup_overhead():
    plan = ResearchQueryPlan(
        critical_inventory=["abstract"],
        mechanisms=["method"],
        experiments=["results"],
        scope=["scope"],
        limitations=["limitations"],
    )
    paper = PaperMetadata(
        paper_id="paper-a",
        title="RDKV",
        source_path="/tmp/paper-a.pdf",
        source_hash="a" * 64,
        page_count=1,
    )

    augmented = _augment_query_plan(plan, paper)

    assert any(
        all(term in query.casefold() for term in ("prefill", "overhead", "ttft"))
        for query in augmented.experiments
    )


def test_arabic_benchmark_table_expansion_is_not_a_missing_headline_topic():
    overreach = (
        "Decision-critical Table 1 coverage omits the complete per-budget "
        "method/task result ranges and row-level condition mapping."
    )
    required_roman_matrix = (
        "Table I omits a materially different platform result range."
    )
    real_headline = "The abstract headline result of 9.1% is missing."

    assert _is_unscoped_arabic_benchmark_table_expansion(overreach)
    assert not _is_unscoped_arabic_benchmark_table_expansion(required_roman_matrix)
    assert not _is_unscoped_arabic_benchmark_table_expansion(real_headline)


def test_comparison_output_strips_internal_repair_provenance():
    comparison = TechnicalComparison(
        matrix=[
            ComparisonCell(
                dimension="latency",
                paper_id="paper-a",
                summary=(
                    "128K에서 4.5× speedup을 보고한다. "
                    "이 셀은 이전의 잘못된 축약 evidence ID 대신 완전한 ID를 사용한다."
                ),
                evidence_ids=["paper:paper-a@aaaaaaaaaaaa:p0001:element:whole"],
            )
        ]
    )

    cleaned = _strip_comparison_workflow_metadata(comparison)

    assert cleaned.matrix[0].summary == "128K에서 4.5× speedup을 보고한다."
