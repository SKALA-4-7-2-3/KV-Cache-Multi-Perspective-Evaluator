"""팀 Agent가 넘길 최소 입력 계약. 값 검증은 Pydantic, 내용 검수는 사람이 수행한다."""

from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Tech = Literal["SW-01", "HW-01"]
Role = Literal["technical", "market", "stakeholders", "domain"]
Method = Literal[
    "analysis", "gpu_experiment", "emulation", "simulation", "prototype_test",
    "qualification", "operational", "documentation", "statement", "measurement", "unspecified",
]


def merge_by_id(old: dict, new: dict) -> dict:
    """병렬 문서·근거·오류는 동일 ID/동일 내용만 허용한다. 입력을 변경하지 않는다."""
    merged = dict(old)
    for key, value in new.items():
        if key in merged and merged[key] != value:
            raise ValueError("동일 ID에 서로 다른 데이터가 전달되었습니다.")
        merged[key] = value
    return merged


def merge_assessments(old: dict, new: dict) -> dict:
    """각 역할은 자기 결과만 반환한다. 새 회차만 대체하며 동회차 충돌은 오류다."""
    merged = dict(old)
    for role, value in new.items():
        RoleResult.model_validate(value)
        if role not in ("technical", "market", "stakeholders", "domain"):
            raise ValueError("알 수 없는 역할입니다.")
        if role in merged:
            previous = merged[role]
            if value["round"] < previous["round"]:
                continue
            if value["round"] == previous["round"] and value != previous:
                raise ValueError("동일 역할·회차에 서로 다른 평가가 전달되었습니다.")
        merged[role] = value
    return merged


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Config(BaseModel):
    # 팀 전체의 모델·검색 설정은 통합 코드가 관리한다. review는 필요한 설정만 읽는다.
    model_config = ConfigDict(extra="ignore")
    run_id: Text
    domain: Text
    demo: bool = False
    rubric_version: Text = "kv-cache-rubric-v1"
    # 예: {"quality": "정확도 감소 1%p 이하"}. 숫자의 타당성 자체는 사람이 검수한다.
    requirements: dict[str, Text] = Field(default_factory=dict)


class Document(StrictModel):
    title: Text
    url: HttpUrl
    version: Text
    pages: int = Field(ge=1, le=200)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    kind: Literal["paper", "web"]
    published_at: str | None = None
    retrieved_at: Text
    source_type: Literal["paper", "official_product", "standard", "news", "market_report", "community"] | None = None
    citation_key: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")


class Evidence(StrictModel):
    id: Text
    doc_id: Text
    technology_ids: list[Tech] = Field(min_length=1)
    excerpt: Text
    page: int | None = Field(default=None, ge=1)
    location: str | None = None
    method: Method = "unspecified"
    # 검색/추출 모듈이 설정한다. LLM에게 발급 권한을 주지 않는다.
    verified_source: bool = False
    synthetic: bool = False
    collected_at: Text
    independence: Literal["author", "vendor", "third_party", "unknown"] = "unknown"
    conditions: list[Text] = Field(default_factory=list)


class Metric(StrictModel):
    name: Text
    value: float = Field(allow_inf_nan=False)
    unit: Text
    evidence_ids: list[Text] = Field(min_length=1)
    # 빠진 조건은 null로 둔다. 서로 다른 조건의 배수는 비교하지 않는다.
    model: Text | None = None
    hardware: Text | None = None
    baseline: Text | None = None
    context_tokens: int | None = Field(default=None, gt=0)
    concurrency: int | None = Field(default=None, gt=0)
    workload: Text | None = None
    method: Method = "unspecified"


class Assessment(StrictModel):
    criterion_id: Text
    judgment: Literal["met", "favorable", "conditional", "unfavorable", "unknown", "failed", "not_applicable"]
    conclusion: Text
    conditions: list[Text] = Field(default_factory=list)
    evidence_ids: list[Text] = Field(default_factory=list)
    basis: Literal["fact", "inference", "mixed", "unknown"]
    gaps: list[Text] = Field(default_factory=list)
    need_more: list[Text] = Field(default_factory=list, max_length=2)
    metrics: list[Metric] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low", "unavailable"] = "unavailable"
    counter_evidence: list[Text] = Field(default_factory=list)
    analysis_scope: Literal["selected_domain", "global", "mixed"] = "mixed"
    domain_relevance: Literal["direct", "indirect", "unclear"] = "unclear"


class TRLCheck(StrictModel):
    status: Literal["met", "not_met", "unknown"]
    reason: Text
    evidence_ids: list[Text] = Field(default_factory=list)


class TechnologyAssessment(StrictModel):
    status: Literal["completed", "unknown", "failed"]
    items: list[Assessment]
    trl_checks: dict[int, TRLCheck] = Field(default_factory=dict)


class RoleResult(StrictModel):
    round: int = Field(ge=0, le=1)
    status: Literal["completed", "unknown", "failed"]
    results: dict[Tech, TechnologyAssessment] = Field(default_factory=dict)


class Issue(StrictModel):
    code: Text
    role: Role | None = None
    technology_id: Tech | None = None
    criterion_id: str | None = None
    message: Text
    repairable: bool = False


class Review(StrictModel):
    round: int = Field(ge=0, le=1)
    status: Literal["completed", "partial", "failed"]
    next: Literal["repair", "render"]
    input_cells: int = Field(ge=0, le=8)
    dirty_roles: list[Role]
    repair_requests: dict[str, list[str]]
    checks: list[Issue]
    gaps: list[str]
    rubric_version: Text
    human_review_required: Literal[True] = True


class Synthesis(StrictModel):
    # 각 items는 Assessment로 검증한 뒤 JSON 딕셔너리로 전달한다.
    comparison_matrix: list[dict[str, Any]]
    by_criterion: list[dict[str, Any]]
    view_differences: list[dict[str, Any]]
    metric_comparisons: list[dict[str, Any]]
    trl: dict[str, Any]
    used_evidence_ids: list[str]
    references: list[dict[str, Any]]
    summary: list[str]
    disclaimer: str
    demo: bool
    integrated: dict[str, Any] = Field(default_factory=dict)


class ReviewState(TypedDict, total=False):
    """실제 병렬 Graph에서 사용하는 State. config/review는 순차 노드만 쓴다."""
    config: dict
    documents: Annotated[dict, merge_by_id]
    evidence: Annotated[dict, merge_by_id]
    assessments: Annotated[dict, merge_assessments]
    errors: Annotated[dict, merge_by_id]
    review: dict
    synthesis: dict
    report_input_md: str
