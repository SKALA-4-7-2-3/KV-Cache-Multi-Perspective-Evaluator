"""Versioned public contracts and internal structured-output models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.2.0"
FACETS = ("technical_overview", "scope", "limitations")

TECHNICAL_FIELDS = (
    "problem_definition",
    "core_approach",
    "novelty",
    "mechanisms",
    "training_process",
    "inference_process",
    "requirements",
    "experimental_results",
)
SCOPE_FIELDS = (
    "target_tasks",
    "domains",
    "operating_conditions",
    "evaluated_settings",
    "modalities",
    "author_claimed_scope",
    "inferred_scope",
    "out_of_scope",
)
LIMITATION_FIELDS = (
    "author_stated",
    "inferred",
    "compute_constraints",
    "data_constraints",
    "generalization_constraints",
    "reproducibility_constraints",
)
FACET_FIELDS = {
    "technical_overview": TECHNICAL_FIELDS,
    "scope": SCOPE_FIELDS,
    "limitations": LIMITATION_FIELDS,
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoundingBox(StrictModel):
    """A page-relative rectangle expressed in PDF points from the top-left origin."""

    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float | None = None
    page_height: float | None = None
    coordinate_system: Literal["pdf_top_left_points"] = "pdf_top_left_points"

    @model_validator(mode="after")
    def validate_bounds(self) -> "BoundingBox":
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("bbox의 x1/y1은 x0/y0보다 커야 합니다.")
        if self.page_width is not None and (self.x0 < 0 or self.x1 > self.page_width + 0.01):
            raise ValueError("bbox가 페이지 너비를 벗어났습니다.")
        if self.page_height is not None and (self.y0 < 0 or self.y1 > self.page_height + 0.01):
            raise ValueError("bbox가 페이지 높이를 벗어났습니다.")
        return self


class TextSpan(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_span(self) -> "TextSpan":
        if self.end < self.start:
            raise ValueError("text span의 end는 start 이상이어야 합니다.")
        return self


class TableCellRef(StrictModel):
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    raw_text: str = ""
    row_header: str | None = None
    column_header: str | None = None


EvidenceContentKind = Literal[
    "text", "table", "caption", "figure", "chart", "diagram"
]
ExtractionMethod = Literal["native_text", "pdfplumber", "vision"]


class PaperAnalysisRequest(StrictModel):
    source: str
    paper_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    output_language: Literal["ko", "en"] = "ko"
    force_reindex: bool = False


class TokenUsage(StrictModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class RunMetadata(StrictModel):
    run_id: str
    openai_model: str
    embedding_model: str
    audit_provider: Literal["openai", "gemini"] = "gemini"
    audit_model: str | None = None
    gemini_model: str | None = None
    prompt_version: str
    index_version: str
    started_at: datetime
    finished_at: datetime
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    quality_repairs: int = 0


class PaperMetadata(StrictModel):
    paper_id: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    arxiv_id: str | None = None
    source_path: str
    source_hash: str
    page_count: int


class Evidence(StrictModel):
    evidence_id: str
    source_kind: Literal["paper", "common"]
    document_id: str
    page: int | None = None
    section: str | None = None
    chunk_id: str
    content_kind: EvidenceContentKind = "text"
    snippet: str
    content_hash: str
    element_id: str | None = None
    parent_element_id: str | None = None
    object_label: str | None = None
    printed_page: str | None = None
    bbox: BoundingBox | None = None
    text_span: TextSpan | None = None
    table_cells: list[TableCellRef] = Field(default_factory=list)
    crop_hash: str | None = None
    extraction_method: ExtractionMethod = "native_text"


class GroundedClaim(StrictModel):
    text: str = Field(min_length=1)
    claim_type: Literal["author_claim", "observed_result", "analyst_inference"]
    evidence_ids: list[str] = Field(min_length=1)
    context_evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


ClaimList = list[GroundedClaim]


class TechnicalOverview(StrictModel):
    problem_definition: ClaimList = Field(default_factory=list)
    core_approach: ClaimList = Field(default_factory=list)
    novelty: ClaimList = Field(default_factory=list)
    mechanisms: ClaimList = Field(default_factory=list)
    training_process: ClaimList = Field(default_factory=list)
    inference_process: ClaimList = Field(default_factory=list)
    requirements: ClaimList = Field(default_factory=list)
    experimental_results: ClaimList = Field(default_factory=list)
    not_reported: list[str] = Field(default_factory=list)


class ScopeAnalysis(StrictModel):
    target_tasks: ClaimList = Field(default_factory=list)
    domains: ClaimList = Field(default_factory=list)
    operating_conditions: ClaimList = Field(default_factory=list)
    evaluated_settings: ClaimList = Field(default_factory=list)
    modalities: ClaimList = Field(default_factory=list)
    author_claimed_scope: ClaimList = Field(default_factory=list)
    inferred_scope: ClaimList = Field(default_factory=list)
    out_of_scope: ClaimList = Field(default_factory=list)
    not_reported: list[str] = Field(default_factory=list)


class LimitationsAnalysis(StrictModel):
    author_stated: ClaimList = Field(default_factory=list)
    inferred: ClaimList = Field(default_factory=list)
    compute_constraints: ClaimList = Field(default_factory=list)
    data_constraints: ClaimList = Field(default_factory=list)
    generalization_constraints: ClaimList = Field(default_factory=list)
    reproducibility_constraints: ClaimList = Field(default_factory=list)
    not_reported: list[str] = Field(default_factory=list)


class PaperAnalysis(StrictModel):
    technical_overview: TechnicalOverview
    scope: ScopeAnalysis
    limitations: LimitationsAnalysis


class ClaimAudit(StrictModel):
    claim_key: str
    verdict: Literal["supported", "partial", "unsupported"]
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class QualityReport(StrictModel):
    ingestion_characters: int = 0
    indexed_chunks: int = 0
    evidence_resolution_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    unsupported_claims: int = 0
    partial_claims: int = 0
    audits: list[ClaimAudit] = Field(default_factory=list)
    searched_queries: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class Diagnostic(StrictModel):
    node: str
    code: str
    message: str
    facet: str | None = None


class PaperAnalysisEnvelope(StrictModel):
    schema_version: Literal["1.0.0", "1.1.0", "1.2.0"] = SCHEMA_VERSION
    status: Literal["succeeded", "failed_ingestion", "failed_quality", "provider_error"]
    run: RunMetadata
    paper: PaperMetadata | None = None
    analysis: PaperAnalysis | None = None
    evidence_registry: list[Evidence] = Field(default_factory=list)
    quality: QualityReport = Field(default_factory=QualityReport)
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_status_shape(self) -> PaperAnalysisEnvelope:
        if self.status == "succeeded":
            if self.paper is None or self.analysis is None:
                raise ValueError("성공 결과에는 paper와 analysis가 필요합니다.")
        elif self.analysis is not None:
            raise ValueError("실패 결과의 analysis는 null이어야 합니다.")
        return self


class ValidationReport(StrictModel):
    valid: bool
    schema_version: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IndexReport(StrictModel):
    indexed_documents: int = 0
    indexed_chunks: int = 0
    skipped_documents: int = 0
    errors: list[str] = Field(default_factory=list)


class PageElement(StrictModel):
    page: int
    section: str | None = None
    content_kind: EvidenceContentKind
    text: str
    element_id: str | None = None
    parent_element_id: str | None = None
    object_label: str | None = None
    printed_page: str | None = None
    bbox: BoundingBox | None = None
    text_span: TextSpan | None = None
    table_cells: list[TableCellRef] = Field(default_factory=list)
    crop_hash: str | None = None
    extraction_method: ExtractionMethod = "native_text"


class Chunk(StrictModel):
    chunk_id: str
    source_kind: Literal["paper", "common"]
    document_id: str
    # Immutable source-content version (normally the source SHA-256). This is
    # separate from the BGE index generation so callers can filter a corpus by
    # a document revision without depending on storage internals.
    document_version: str | None = None
    page: int | None = None
    section: str | None = None
    content_kind: EvidenceContentKind
    text: str
    content_hash: str
    element_id: str | None = None
    parent_element_id: str | None = None
    object_label: str | None = None
    printed_page: str | None = None
    bbox: BoundingBox | None = None
    text_span: TextSpan | None = None
    table_cells: list[TableCellRef] = Field(default_factory=list)
    crop_hash: str | None = None
    extraction_method: ExtractionMethod = "native_text"

    def as_evidence(self, snippet_chars: int = 1200) -> Evidence:
        return Evidence(
            evidence_id=f"ev-{self.chunk_id}",
            source_kind=self.source_kind,
            document_id=self.document_id,
            page=self.page,
            section=self.section,
            chunk_id=self.chunk_id,
            content_kind=self.content_kind,
            snippet=self.text[:snippet_chars],
            content_hash=self.content_hash,
            element_id=self.element_id,
            parent_element_id=self.parent_element_id,
            object_label=self.object_label,
            printed_page=self.printed_page,
            bbox=self.bbox,
            text_span=self.text_span,
            table_cells=self.table_cells,
            crop_hash=self.crop_hash,
            extraction_method=self.extraction_method,
        )


class ParsedDocument(StrictModel):
    metadata: PaperMetadata
    elements: list[PageElement]
    chunks: list[Chunk]
    character_count: int


class QueryPlan(StrictModel):
    technical_overview: list[str] = Field(min_length=1)
    scope: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)

    def for_facet(self, facet: str) -> list[str]:
        return list(getattr(self, facet))


class FacetClaim(StrictModel):
    field: str
    text: str = Field(min_length=1)
    claim_type: Literal["author_claim", "observed_result", "analyst_inference"]
    evidence_ids: list[str] = Field(min_length=1)
    context_evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class FacetExtraction(StrictModel):
    facet: Literal["technical_overview", "scope", "limitations"]
    claims: list[FacetClaim] = Field(default_factory=list)
    not_reported: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_coverage(self) -> FacetExtraction:
        expected = set(FACET_FIELDS[self.facet])
        reported = {claim.field for claim in self.claims}
        absent = set(self.not_reported)
        invalid = (reported | absent) - expected
        overlap = reported & absent
        missing = expected - reported - absent
        if invalid:
            raise ValueError(f"허용되지 않은 facet 필드: {sorted(invalid)}")
        if overlap:
            raise ValueError(f"보고됨과 미보고가 겹치는 필드: {sorted(overlap)}")
        if missing:
            raise ValueError(f"facet 필드 누락: {sorted(missing)}")
        return self


class EvidenceAudit(StrictModel):
    audits: list[ClaimAudit] = Field(default_factory=list)
    missing_topics: list[str] = Field(default_factory=list)
    failed_facets: list[Literal["technical_overview", "scope", "limitations"]] = Field(
        default_factory=list
    )


class FacetWorkResult(StrictModel):
    facet: Literal["technical_overview", "scope", "limitations"]
    attempt: int
    extraction: FacetExtraction
    evidence: list[Evidence]
    usage: TokenUsage = Field(default_factory=TokenUsage)


def utc_now() -> datetime:
    return datetime.now(UTC)
