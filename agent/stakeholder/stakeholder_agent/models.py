"""Internal research models shared by JSON and legacy Markdown entry points."""

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

GROUPS = {
    "operator": "서비스·인프라 운영자",
    "developer": "기술·플랫폼 개발자",
    "supplier": "공급자·경쟁 기술 진영",
    "customer": "도입 조직·서비스 이용자",
    "observer": "투자·애널리스트·미디어",
}
# Historical IDs remain usable; selected roles are no longer a fixed enum.
Group = str
Kind = Literal["paper_report", "statement", "inference", "unknown"]
KIND_LABELS = {"paper_report": "논문 보고", "statement": "당사자 발언·행동",
               "inference": "분석적 추론", "unknown": "미확인"}
ASPECT_LABELS = {"benefit": "편익", "burden": "부담·위험",
                 "adoption_condition": "도입 조건", "reaction": "실제 반응", "evaluation": "평가·의견"}
OUTPUT_SECTIONS = ["분석 정보", "SUMMARY 기여", "평가 기준 및 방법", "이해관계자별 SW/HW 비교",
                   "이해 상충 및 관점 간 연결", "한계 및 편향 검토", "추가 확인 사항", "근거 연결", "REFERENCE"]


@dataclass
class Technology:
    id: str
    name: str
    kind: str
    paper: str
    url: str


@dataclass
class Evidence:
    id: str
    tech_ids: list[str]
    title: str
    url: str
    location: str
    excerpt: str
    publisher: str = "미표기"
    published_at: str = "미표기"
    retrieved_at: str = "미표기"
    source_type: str = "paper"
    scope: str = "direct"
    author: str = "미표기"
    requested_url: str = ""
    metadata_provenance: dict[str, str] = field(default_factory=dict)
    search_queries: list[str] = field(default_factory=list)
    content_sha256: str = ""
    audit: dict = field(default_factory=dict)


@dataclass
class Domain:
    id: str
    name: str
    scenario: str


@dataclass
class AnalysisContext:
    original_request: str = ""
    objective: str = "이해관계자 관점의 편익·부담·도입 조건 평가"
    constraints: str = "미지정"
    domains: list[Domain] = field(default_factory=lambda: [
        Domain("D-01", "클라우드 데이터센터", "LLM 추론 서비스 운영")])
    origin: str = "legacy_default"
    extra_fields: dict[str, str] = field(default_factory=dict)
    additional_context: str = ""


@dataclass
class ParsedInput:
    run_id: str
    as_of: str
    technologies: list[Technology]
    evidence: dict[str, Evidence]
    summary: str
    gaps: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    requested_limits: dict[str, int] = field(default_factory=dict)
    analysis_context: AnalysisContext = field(default_factory=AnalysisContext)


@dataclass
class Budget:
    limits: dict[str, int]
    used: dict[str, int] = field(default_factory=lambda: {"search": 0, "fetch": 0, "llm": 0})

    def remaining(self, key: str) -> int:
        return max(0, self.limits[key] - self.used[key])

    def take(self, key: str) -> bool:
        if not self.remaining(key):
            return False
        self.used[key] += 1
        return True


class Structured(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchQuestion(Structured):
    tech_id: str
    group: Group
    query: str
    reason: str
    domain_id: str = ""


class StakeholderTarget(Structured):
    id: str
    domain_id: str
    name: str
    reason: str
    priority: Literal["core", "conditional"] = "core"


class ResearchPlan(Structured):
    questions: list[SearchQuestion]
    stakeholders: list[StakeholderTarget] = Field(default_factory=list)


class Support(Structured):
    evidence_id: str
    quote: str


class Claim(Structured):
    tech_id: str
    group: Group
    aspect: Literal["benefit", "burden", "adoption_condition", "reaction", "evaluation"]
    kind: Kind
    text: str
    condition: str
    source_scope: Literal["direct", "family", "context"]
    supports: list[Support]
    domain_id: str = ""
    actor: str = ""
    actor_relationship: Literal["provider", "competitor", "adopter", "developer", "customer",
                                "observer", "unspecified"] = "unspecified"


class Insight(Structured):
    text: str
    claim_indices: list[int]


class WebSourceReview(Structured):
    evidence_id: str
    document_type: Literal["supplier_publication", "research", "standard", "reporting",
                           "commentary", "republication", "unknown"]
    perspective: Literal["interested_party", "independent_author", "unknown"]
    relevance: Literal["direct", "family", "background", "unrelated", "unknown"]
    evidence_basis: Literal["methods_and_results", "attributed_statement", "opinion", "unknown"]
    decision: Literal["use", "limited", "exclude"]
    reasons: list[str]
    limitations: list[str]
    basis_quotes: list[str]


class Assessment(Structured):
    source_reviews: list[WebSourceReview] = Field(default_factory=list)
    claims: list[Claim]
    summary: list[Insight]
    implications: list[Insight]
    limitations: list[str]
    follow_up: list[str]


# Live operator analysis selects literal source spans; the public result still
# carries the resolved text and uses the unchanged Claim/Assessment contract.
QuoteKey = Literal[tuple(f"Q{index:03d}" for index in range(1, 81))]


class CatalogSupport(Support):
    quote: QuoteKey


class CatalogClaim(Claim):
    supports: list[CatalogSupport]


class CatalogSourceReview(WebSourceReview):
    basis_quotes: list[QuoteKey]


class CatalogAssessment(Assessment):
    source_reviews: list[CatalogSourceReview] = Field(default_factory=list)
    claims: list[CatalogClaim]


class Review(Structured):
    rejected_claim_indices: list[int]
    issues: list[str]
    queries: list[SearchQuestion]


class OperatorClaimCheck(Structured):
    claim_index: int = Field(strict=True, ge=0)
    supported: bool = Field(strict=True)
    reason: str = Field(min_length=1, max_length=600,
                        description="Short verdict on whether the cited text supports the claim.")


class OperatorReview(Structured):
    """Provider-only contract requiring an explicit verdict for every candidate."""

    checks: list[OperatorClaimCheck]
    queries: list[SearchQuestion]


class AgentState(TypedDict, total=False):
    input_md: str
    normalized_input: Any
    output_format: str
    initial_usage: dict[str, int]
    output_json: dict
    parsed: ParsedInput | None
    evidence: dict[str, Evidence]
    plan: ResearchPlan
    draft: Assessment | None
    review: Review | None
    budget: Budget
    round: int
    errors: list[str]
    gaps: list[str]
    rejected: list[int]
    status: str
    output_md: str
    trace: list[str]
    mode: str
    searched_queries: list[str]
    searched_pairs: list[tuple[str, str]]
    research_log: list[dict]
    selection_origin: str
    coverage: list[dict]
    execution_status: str
    evidence_status: str
    review_succeeded: bool
    pending_source_ids: list[str]
