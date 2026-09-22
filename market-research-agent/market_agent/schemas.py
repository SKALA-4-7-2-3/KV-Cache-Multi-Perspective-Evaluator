"""외부 데이터 경계와 에이전트 결과의 계약."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CRITERIA = {
    "market_size_growth": "시장 규모·성장",
    "commercialization": "제품화",
    "adoption": "실제 채택",
    "ecosystem_support": "생태계 지원",
    "standardization": "표준화",
    "business_value": "비용·고객 가치·사업화 조건",
}
Criterion = Literal["market_size_growth", "commercialization", "adoption", "ecosystem_support", "standardization", "business_value"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Limits(Record):
    search: int = Field(ge=0, strict=True)
    extract: int = Field(ge=0, strict=True)
    llm: int = Field(ge=0, strict=True)


class Segment(Record):
    text: str
    start: int
    end: int
    locator: str


class Evidence(Record):
    id: str
    doc_id: str
    title: str
    url: str
    publisher: str = ""
    published_at: date | None = None
    retrieved_at: str = ""
    locator: str = ""
    excerpt: str = ""
    content_hash: str = ""
    source_type: str = "미확인"
    access_status: Literal["provided_summary", "full_text", "snippet", "failed"]
    tech_ids: list[str] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)
    access_scope: str = "미확인"
    content_status: Literal['unchecked', 'substantive', 'metadata_only', 'identity_mismatch'] = 'unchecked'
    content_reason: str = ''
    requested_url: str = ''
    criteria: list[Criterion] = Field(default_factory=list)


class Technology(Record):
    id: str
    name: str
    approach: Literal["SW", "HW"]
    paper: str
    url: str
    summary: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    paper_id: str = ''


class MarketInput(Record):
    role: Literal["market"] = "market"
    schema_version: Literal["0.1", "1.1.0"]
    run_id: str
    domain: str
    as_of: date
    language: str
    limits: Limits
    technologies: dict[str, Technology]
    evidence: dict[str, Evidence]
    raw_markdown: str
    input_hash: str
    provenance: str
    notes: str
    warnings: list[str] = Field(default_factory=list)
    input_format: Literal['markdown', 'paper_analysis_json'] = 'markdown'
    source_documents: list[dict] = Field(default_factory=list)


class Metric(Record):
    value: float
    unit: str
    currency: str | None
    year: str
    market_definition: str
    geography: str
    actual_or_forecast: Literal["actual", "forecast"]


Basis = Literal["fact", "inference", "unknown"]
Relation = Literal["exact", "method_family", "adjacent", "unknown"]
Verdict = Literal["favorable", "conditional", "unfavorable", "unknown", "not_applicable"]
EvidenceLevel = Literal['research_experiment','simulation','publisher_statement','planned_release','customer_case','projection','inference']


class Citation(Record):
    evidence_id: str
    quote: str
    subject: str
    source_character: str
    identity_quote: str = ""
    locator: str = ""
    context: str = ''


class ContextFinding(Record):
    statement: str
    basis: Basis
    relation_to_technology: Relation
    citations: list[Citation]
    conditions: list[str]
    metric: Metric | None = None


class Assessment(Record):
    tech_id: str
    criterion_id: Criterion
    judgment: str
    basis: Basis
    relation_to_technology: Relation
    evidence_ids: list[str]
    conditions: list[str]
    metric: Metric | None
    gaps: list[str]
    verdict: Verdict = "unknown"
    citations: list[Citation] = Field(default_factory=list)
    context_findings: list[ContextFinding] = Field(default_factory=list)
    research_status: Literal["not_started", "searched", "reviewed"] | None = None
    unknown_reasons: list[str] = Field(default_factory=list)
    next_action: str = ""
    search_ids: list[str] = Field(default_factory=list)
    reviewed_evidence_ids: list[str] = Field(default_factory=list)


class Question(Record):
    tech_id: str
    criterion_id: Criterion
    query: str
    reason: str
    criteria: list[Criterion] = Field(default_factory=list)
    source_type: str = "공식 문서·연구 원문"


class Analysis(Record):
    assessments: list[Assessment]
    followup_questions: list[Question]


class Claim(Record):
    tech_id: str
    criterion_id: Criterion
    statement: str
    basis: Literal['fact', 'inference']
    relation_to_technology: Literal['exact', 'method_family', 'adjacent']
    citation: Citation
    conditions: list[str]
    metric: Metric | None
    evidence_level: EvidenceLevel = 'publisher_statement'


class SourceReview(Record):
    evidence_id: str
    outcome: Literal['claims_extracted', 'no_market_claim']
    reason: str
    criteria: list[Criterion] = Field(default_factory=list)


class Extraction(Record):
    claims: list[Claim]
    reviews: list[SourceReview]


class SelectedClaim(Record):
    tech_id: str
    criterion_id: Criterion
    statement: str
    basis: Literal['fact', 'inference']
    relation_to_technology: Literal['exact', 'method_family', 'adjacent']
    quote_id: str
    subject: str
    conditions: list[str]
    metric: Metric | None
    evidence_level: EvidenceLevel = 'publisher_statement'


class SelectedExtraction(Record):
    claims: list[SelectedClaim]
    reviews: list[SourceReview]


class DraftAssessment(Record):
    tech_id: str
    criterion_id: Criterion
    judgment: str
    verdict: Verdict
    basis: Basis
    claim_ids: list[str]
    conditions: list[str]
    gaps: list[str]


class ClaimReview(Record):
    claim_id: str
    supported: bool
    reason: str
    market_relevant: bool = True
    relation_supported: bool = True
    conditions_preserved: bool = True
    evidence_level: EvidenceLevel = 'publisher_statement'


class SemanticClaimReview(ClaimReview):
    market_relevant: bool
    relation_supported: bool
    conditions_preserved: bool
    evidence_level: EvidenceLevel


class DraftAnalysis(Record):
    assessments: list[DraftAssessment]
    followup_questions: list[Question]
    claim_reviews: list[ClaimReview] = Field(default_factory=list)


class ReviewedDraftAnalysis(DraftAnalysis):
    claim_reviews: list[SemanticClaimReview]


class MarketResult(Record):
    output_schema_version: str = "0.3"
    role: Literal["market"] = "market"
    status: Literal["completed", "unknown", "failed"]
    round: int
    assessments: list[Assessment]
    followup_questions: list[Question]
    technology_status: dict[str, str]
    errors: list[dict[str, str]]
    usage: dict[str, int]
    mode: str


def unknown(tech_id: str, criterion_id: str, reason: str) -> Assessment:
    return Assessment(tech_id=tech_id, criterion_id=criterion_id, judgment=reason,
                      basis="unknown", relation_to_technology="unknown", evidence_ids=[],
                      conditions=[], metric=None, gaps=[reason])
