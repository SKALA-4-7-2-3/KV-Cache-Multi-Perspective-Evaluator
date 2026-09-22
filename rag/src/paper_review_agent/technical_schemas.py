"""Versioned contracts for evidence-first multi-paper technical research."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_review_agent.schemas import (
    LimitationsAnalysis,
    PaperAnalysis,
    PaperMetadata,
    ScopeAnalysis,
    TechnicalOverview,
    TokenUsage,
    utc_now,
)


TECHNICAL_SCHEMA_VERSION = "1.0.0"


class TechnicalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TechnicalResearchRequest(TechnicalModel):
    instruction: str = Field(min_length=1)
    sources: list[str] = Field(default_factory=list)
    # Common sources are an explicit allow-list. They are not inferred from the
    # instruction and may support context_evidence_ids only.
    common_sources: list[str] = Field(default_factory=list)
    output_language: Literal["ko", "en"] = "ko"
    job_id: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
    )
    force_reindex: bool = False


class TextSpan(TechnicalModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> "TextSpan":
        if self.end <= self.start:
            raise ValueError("text span end must be greater than start")
        return self


class TableCellLocator(TechnicalModel):
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    raw_text: str = ""
    row_header: str | None = None
    column_header: str | None = None


class EvidenceLocator(TechnicalModel):
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    physical_page: int | None = Field(default=None, ge=1)
    printed_page_label: str | None = None
    section_path: list[str] = Field(default_factory=list)
    # ``element_id`` is the public citation object (for example ``table-01``).
    # The parser/index join remains explicit so validation never has to infer it
    # from a human-readable label.
    element_id: str
    source_chunk_id: str | None = Field(default=None, min_length=1)
    source_element_id: str | None = None
    object_label: str | None = None
    normalized_object_label: str | None = None
    parent_element_id: str | None = None
    bbox_pt: tuple[float, float, float, float] | None = None
    page_size_pt: tuple[float, float] | None = None
    coordinate_system: Literal["pdf_top_left_points"] = "pdf_top_left_points"
    text_span: TextSpan | None = None
    table_cells: list[TableCellLocator] = Field(default_factory=list)
    visual_artifact_id: str | None = None
    crop_sha256: str | None = None

    @model_validator(mode="after")
    def validate_geometry(self) -> "EvidenceLocator":
        if self.bbox_pt is not None:
            x0, y0, x1, y1 = self.bbox_pt
            if x1 <= x0 or y1 <= y0:
                raise ValueError("bbox_pt must have positive width and height")
        return self


class TechnicalEvidence(TechnicalModel):
    evidence_id: str
    source_kind: Literal["paper", "common"]
    document_id: str
    content_kind: Literal["text", "table", "caption", "figure", "chart", "diagram"]
    extraction_method: Literal["native_text", "pdfplumber", "vision"] = "native_text"
    snippet: str = Field(min_length=1)
    content_hash: str
    locator: EvidenceLocator


class TechnicalClaim(TechnicalModel):
    claim_id: str
    text: str = Field(min_length=1)
    claim_type: Literal["author_claim", "observed_result", "analyst_inference"]
    evidence_ids: list[str] = Field(min_length=1)
    context_evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    critical: bool = False


class CriticalClaimItem(TechnicalModel):
    inventory_id: str
    category: Literal[
        "problem", "contribution", "mechanism", "result", "scope", "limitation"
    ]
    summary: str
    disposition: Literal["extracted", "excluded", "unverified"]
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    searched_queries: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_disposition(self) -> "CriticalClaimItem":
        # Provider structured-output validation must remain permissive enough for
        # deterministic post-processing to repair omitted cross-references.  The
        # public dossier contract still rejects an extracted item unless both
        # claim_ids and evidence_ids are present after that normalization step.
        if self.disposition in {"excluded", "unverified"} and not self.reason:
            raise ValueError("excluded/unverified inventory items require a reason")
        if self.disposition == "unverified" and not self.searched_queries:
            raise ValueError("unverified inventory items require searched_queries")
        return self


class ExperimentObservation(TechnicalModel):
    observation_id: str
    metric: str
    value: str | None = None
    value_min: float | None = None
    value_max: float | None = None
    unit: str | None = None
    direction: Literal[
        "higher_is_better", "lower_is_better", "neutral", "not_applicable"
    ] = "not_applicable"
    baseline: str | None = None
    model: str | None = None
    hardware: str | None = None
    context_length: str | None = None
    concurrency: str | None = None
    dataset: str | None = None
    workload: str | None = None
    evaluation_mode: Literal[
        "measured", "emulated", "simulated", "analytical", "not_stated"
    ]
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def require_value(self) -> "ExperimentObservation":
        if self.value is None and self.value_min is None and self.value_max is None:
            raise ValueError("an experiment observation requires a value or range")
        if (
            self.value_min is not None
            and self.value_max is not None
            and self.value_max < self.value_min
        ):
            raise ValueError("value_max must be greater than or equal to value_min")
        return self


class UnverifiedItem(TechnicalModel):
    item_id: str
    topic: str
    reason: str
    searched_queries: list[str] = Field(min_length=1)
    filters: dict[str, str] = Field(default_factory=dict)
    attempts: int = Field(ge=1, le=3)


class TechnicalDossier(TechnicalModel):
    dossier_version: Literal["1.0.0"] = TECHNICAL_SCHEMA_VERSION
    paper: PaperMetadata
    analysis: PaperAnalysis
    claims: list[TechnicalClaim] = Field(default_factory=list)
    critical_inventory: list[CriticalClaimItem] = Field(min_length=1)
    experiment_observations: list[ExperimentObservation] = Field(default_factory=list)
    unverified_items: list[UnverifiedItem] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class TechnologyRelationship(TechnicalModel):
    left_paper_id: str
    right_paper_id: str
    relationship: Literal["substitute", "complementary", "orthogonal", "dependency"]
    rationale: str
    claim_type: Literal["analyst_inference"] = "analyst_inference"
    evidence_ids: list[str] = Field(min_length=2)
    tested_together: bool = False


class ComparisonCell(TechnicalModel):
    dimension: str
    paper_id: str
    summary: str
    evidence_ids: list[str] = Field(min_length=1)


class MetricComparison(TechnicalModel):
    comparison_id: str
    metric: str
    observation_ids: list[str] = Field(min_length=2)
    comparability: Literal["comparable", "not_comparable"]
    reason: str


class IntegrationHypothesis(TechnicalModel):
    hypothesis_id: str
    text: str
    claim_type: Literal["analyst_inference"] = "analyst_inference"
    evidence_ids: list[str] = Field(min_length=2)
    assumptions: list[str] = Field(min_length=1)
    validation_needed: list[str] = Field(min_length=1)


class CommonAssumption(TechnicalModel):
    """An assumption shared by two or more papers, with paper-owned evidence."""

    assumption_id: str
    summary: str = Field(min_length=1)
    paper_ids: list[str] = Field(min_length=2)
    evidence_ids: list[str] = Field(min_length=2)


class PaperAssumption(TechnicalModel):
    paper_id: str
    statement: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class DifferingAssumption(TechnicalModel):
    """Paper-specific values for one assumption dimension that are not equivalent."""

    assumption_id: str
    dimension: str = Field(min_length=1)
    paper_assumptions: list[PaperAssumption] = Field(min_length=2)
    implication: str = Field(min_length=1)


class TechnicalComparison(TechnicalModel):
    comparison_version: Literal["1.0.0"] = TECHNICAL_SCHEMA_VERSION
    relationships: list[TechnologyRelationship] = Field(default_factory=list)
    common_assumptions: list[CommonAssumption] = Field(default_factory=list)
    differing_assumptions: list[DifferingAssumption] = Field(default_factory=list)
    matrix: list[ComparisonCell] = Field(default_factory=list)
    metric_comparisons: list[MetricComparison] = Field(default_factory=list)
    integration_hypotheses: list[IntegrationHypothesis] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    unverified_items: list[UnverifiedItem] = Field(default_factory=list)


class TechnicalArtifactRef(TechnicalModel):
    artifact_id: str
    type: Literal[
        "dossier", "comparison", "evidence_registry", "retrieval_trace", "visual_crop"
    ]
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer: str


class TechnicalVisionRunMetadata(TechnicalModel):
    """Versioned Vision settings that can change a dossier's evidence set."""

    enabled: bool
    model: str | None = None
    schema_version: str
    prompt_revision: str
    configuration_prompt_version: str
    max_visuals_per_paper: int = Field(ge=1)
    max_requests_per_paper: int = Field(ge=1)
    max_pixels_per_paper: int = Field(ge=1)
    max_concurrency: int = Field(ge=1)


class TechnicalRunMetadata(TechnicalModel):
    job_id: str
    openai_model: str
    embedding_provider: str
    embedding_model: str
    embedding_revision: str | None = None
    index_profile: str | None = None
    evidence_id_version: str = "1.0.0"
    contract_schema_version: Literal["1.0.0"] = TECHNICAL_SCHEMA_VERSION
    prompt_version: str | None = None
    index_version: str | None = None
    vision: TechnicalVisionRunMetadata | None = None
    started_at: datetime
    finished_at: datetime | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    # Linux ru_maxrss is captured by the technical run itself so the promotion
    # artifact does not have to trust an unbound, manually copied number.
    peak_rss_bytes: int | None = Field(default=None, gt=0)
    completed_without_oom: bool | None = None


class TechnicalQuality(TechnicalModel):
    evidence_resolution_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    critical_inventory_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    unsupported_numeric_claims: int = Field(default=0, ge=0)
    locator_resolution_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class TechnicalDiagnostic(TechnicalModel):
    node: str
    code: str
    message: str
    document_id: str | None = None


class TechnicalResearchEnvelope(TechnicalModel):
    schema_version: Literal["1.0.0"] = TECHNICAL_SCHEMA_VERSION
    status: Literal[
        "running", "succeeded", "failed_ingestion", "failed_quality", "provider_error"
    ]
    run: TechnicalRunMetadata
    artifacts: list[TechnicalArtifactRef] = Field(default_factory=list)
    dossiers: list[TechnicalDossier] = Field(default_factory=list)
    comparison: TechnicalComparison | None = None
    evidence_registry_path: str | None = None
    quality: TechnicalQuality = Field(default_factory=TechnicalQuality)
    diagnostics: list[TechnicalDiagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self) -> "TechnicalResearchEnvelope":
        if self.status == "succeeded":
            if (
                not self.dossiers
                or self.comparison is None
                or not self.evidence_registry_path
            ):
                raise ValueError(
                    "successful research requires dossiers, comparison and evidence registry"
                )
            if self.quality.evidence_resolution_rate != 1.0:
                raise ValueError(
                    "successful research requires 100% evidence resolution"
                )
            if self.quality.locator_resolution_rate != 1.0:
                raise ValueError("successful research requires 100% locator resolution")
            if self.quality.unsupported_numeric_claims:
                raise ValueError(
                    "successful research cannot contain unsupported numeric claims"
                )
        return self


class ResearchQueryPlan(TechnicalModel):
    critical_inventory: list[str] = Field(min_length=1)
    mechanisms: list[str] = Field(min_length=1)
    experiments: list[str] = Field(min_length=1)
    scope: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    visuals: list[str] = Field(default_factory=list)


class DossierExtraction(TechnicalModel):
    analysis: PaperAnalysis
    claims: list[TechnicalClaim]
    critical_inventory: list[CriticalClaimItem] = Field(min_length=1)
    experiment_observations: list[ExperimentObservation]
    unverified_items: list[UnverifiedItem] = Field(default_factory=list)


class TechnicalFacetExtraction(TechnicalModel):
    """One independently generated, mergeable section of a technical dossier.

    The three nullable section fields make the contract compatible with OpenAI
    structured output while the validator guarantees that exactly the section
    named by ``facet`` is populated.  Cross-cutting records are emitted by the
    facet that owns the statement and are deterministically namespaced during
    assembly, so short model-generated IDs cannot collide across parallel calls.
    """

    facet: Literal["technical_overview", "scope", "limitations"]
    technical_overview: TechnicalOverview | None = None
    scope: ScopeAnalysis | None = None
    limitations: LimitationsAnalysis | None = None
    claims: list[TechnicalClaim] = Field(default_factory=list)
    critical_inventory: list[CriticalClaimItem] = Field(default_factory=list)
    experiment_observations: list[ExperimentObservation] = Field(default_factory=list)
    unverified_items: list[UnverifiedItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_exactly_selected_section(self) -> "TechnicalFacetExtraction":
        sections = {
            "technical_overview": self.technical_overview,
            "scope": self.scope,
            "limitations": self.limitations,
        }
        if sections[self.facet] is None:
            raise ValueError(f"selected facet {self.facet} must be populated")
        unexpected = [
            name
            for name, value in sections.items()
            if name != self.facet and value is not None
        ]
        if unexpected:
            raise ValueError(
                "only the selected facet may be populated: " + ", ".join(unexpected)
            )
        return self


class TechnicalAuditItem(TechnicalModel):
    item_id: str
    verdict: Literal["supported", "partial", "unsupported"]
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class TechnicalAudit(TechnicalModel):
    audits: list[TechnicalAuditItem]
    missing_critical_topics: list[str] = Field(default_factory=list)
    numeric_consistency_errors: list[str] = Field(default_factory=list)
    overgeneralization_errors: list[str] = Field(default_factory=list)


class RetrievalBenchmarkRequest(TechnicalModel):
    golden_path: str
    providers: list[Literal["gemini", "bge-m3"]] = Field(min_length=1)
    # The promotion contract is deliberately fixed at @10.  Allowing another
    # value while retaining recall_at_10/ndcg_at_10 field names would make a
    # benchmark artifact ambiguous.
    k: Literal[10] = 10
    validation_artifact_path: str | None = None


class RetrievalProviderMetrics(TechnicalModel):
    provider: str
    recall_at_10: float = Field(ge=0.0, le=1.0)
    ndcg_at_10: float = Field(ge=0.0, le=1.0)
    numeric_table_recall_at_10: float = Field(ge=0.0, le=1.0)
    p50_latency_ms: float = Field(ge=0.0)
    p95_latency_ms: float = Field(ge=0.0)
    peak_rss_bytes: int = Field(ge=0)
    latency_measurement: Literal["end_to_end", "derived_from_full_trace"] = "end_to_end"
    passed_absolute_gate: bool


class RetrievalE2EValidationArtifact(TechnicalModel):
    """Independent evidence for gates a retrieval-only bake-off cannot prove.

    The referenced technical run is hash checked by ``benchmark_retrieval``.
    Peak RSS must be measured by the E2E harness around that same run.
    """

    schema_version: Literal["1.0.0"] = "1.0.0"
    golden_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    technical_run_path: str = Field(min_length=1)
    technical_run_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bge_index_profile: str = Field(min_length=1)
    successful_paper_ids: list[str] = Field(min_length=2)
    completed_without_oom: bool
    peak_rss_bytes: int = Field(gt=0)
    # Optional paper-specific acceptance evidence.  Older artifacts remain
    # valid, while new artifacts can prove that a separately versioned golden
    # expectation file was evaluated against semantic dossier fields.
    dossier_expectations_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    dossier_expectations_path: str | None = Field(default=None, min_length=1)
    dossier_expectation_count: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_distinct_papers(self) -> "RetrievalE2EValidationArtifact":
        if len(set(self.successful_paper_ids)) < 2:
            raise ValueError("E2E validation requires at least two distinct papers")
        expectation_fields = (
            self.dossier_expectations_sha256,
            self.dossier_expectations_path,
            self.dossier_expectation_count,
        )
        if any(value is not None for value in expectation_fields) and not all(
            value is not None for value in expectation_fields
        ):
            raise ValueError(
                "dossier expectation path, hash and count must be provided together"
            )
        return self


class RetrievalPromotionGate(TechnicalModel):
    bge_full_results_present: bool = False
    gemini_baseline_present: bool = False
    overall_recall_at_10_passed: bool = False
    numeric_table_recall_at_10_passed: bool = False
    ndcg_delta_passed: bool = False
    validation_artifact_present: bool = False
    validation_artifact_valid: bool = False
    locator_resolution_passed: bool = False
    unsupported_numeric_claims_passed: bool = False
    two_paper_e2e_passed: bool = False
    memory_within_14_gib_passed: bool = False
    all_passed: bool = False


class RetrievalBenchmarkReport(TechnicalModel):
    generated_at: datetime = Field(default_factory=utc_now)
    golden_path: str
    metrics: list[RetrievalProviderMetrics]
    promotion_gate: RetrievalPromotionGate = Field(
        default_factory=RetrievalPromotionGate
    )
    validation_artifact_path: str | None = None
    validation_artifact_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    bge_promoted: bool = False
    reasons: list[str] = Field(default_factory=list)


class ModelInstallReport(TechnicalModel):
    model_id: str
    revision: str
    local_path: str
    files_sha256: str
    already_present: bool = False
