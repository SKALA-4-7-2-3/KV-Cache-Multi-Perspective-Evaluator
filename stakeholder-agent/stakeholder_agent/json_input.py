"""Validate paper-analysis JSON and preserve its provenance at the public boundary.

The upstream paper findings are data, not instructions. Their original claims,
confidence values and audits remain upstream reports; this adapter never upgrades
them to independently verified facts or turns paper scope into user requirements.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, field_validator

from .contracts import InputError
from .models import AnalysisContext, Domain, Evidence, ParsedInput, Technology

NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]
CounterName = Literal["llm", "search", "fetch"]

# Identities come from the pair selected by the user, not from filename order.
# Versionless URLs deliberately avoid inventing a paper version absent upstream.
PROJECT_PAPERS = {
    "SW-01": {
        "arxiv_id": "2605.08317", "name": "RDKV", "kind": "SW",
        "title": "RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache",
        "url": "https://arxiv.org/abs/2605.08317",
    },
    "HW-01": {
        "arxiv_id": "2607.27187", "name": "Photonic-CXL", "kind": "HW",
        "title": "A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference",
        "url": "https://arxiv.org/abs/2607.27187",
    },
}


class ExtensibleInput(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)


class DomainInput(ExtensibleInput):
    id: StrictStr
    name: StrictStr
    scenario: StrictStr = "미지정"

    @field_validator("id", "name")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("도메인 ID와 이름은 비어 있을 수 없습니다.")
        return value


class RequestInput(ExtensibleInput):
    original_request: StrictStr
    domains: list[DomainInput] = Field(min_length=1)
    objective: StrictStr = "이해관계자 관점의 편익, 부담 및 도입 조건 평가"
    requirements: Any = None
    additional_context: Any = ""

    @field_validator("original_request", "objective")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("최초 요청과 분석 목적은 비어 있을 수 없습니다.")
        return value

    @field_validator("domains")
    @classmethod
    def unique_domains(cls, domains):
        ids = [domain.id.casefold() for domain in domains]
        if len(ids) != len(set(ids)):
            raise ValueError("중복된 도메인 ID입니다.")
        return domains


class PaperMetadataInput(ExtensibleInput):
    paper_id: StrictStr = Field(min_length=1)
    title: StrictStr = Field(min_length=1)
    arxiv_id: StrictStr | None = None
    authors: list[StrictStr] = Field(default_factory=list)
    page_count: Annotated[int, Field(strict=True, ge=1)] | None = None
    source_hash: StrictStr | None = None
    source_path: StrictStr | None = None
    abstract: StrictStr | None = None


class PaperEvidenceInput(ExtensibleInput):
    evidence_id: StrictStr = Field(min_length=1)
    document_id: StrictStr = Field(min_length=1)
    snippet: StrictStr = Field(min_length=1)
    chunk_id: StrictStr | None = None
    content_hash: StrictStr | None = None
    content_kind: StrictStr = "text"
    source_kind: Literal["paper"] = "paper"
    page: Annotated[int, Field(strict=True, ge=1)] | None = None
    section: StrictStr | None = None


class PaperClaimInput(ExtensibleInput):
    text: StrictStr = Field(min_length=1)
    claim_type: StrictStr = Field(min_length=1)
    confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None = None
    evidence_ids: list[StrictStr]
    context_evidence_ids: list[StrictStr] = Field(default_factory=list)


class PaperAnalysisInput(ExtensibleInput):
    schema_version: Literal["1.1.0"]
    status: StrictStr
    paper: PaperMetadataInput
    analysis: dict[str, dict[str, Any]]
    evidence_registry: list[PaperEvidenceInput]
    quality: dict[str, Any] = Field(default_factory=dict)
    run: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[Any] = Field(default_factory=list)


class RunConfigInput(ExtensibleInput):
    as_of: StrictStr | None = None
    model: StrictStr | None = None
    model_timeout: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    tool_timeout: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    repair_limit: Annotated[int, Field(strict=True, ge=0, le=1)] | None = None


class StakeholderInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"] = "1.0"
    run_id: StrictStr | None = None
    role: Literal["stakeholders"] = "stakeholders"
    paper_analyses: list[PaperAnalysisInput] = Field(min_length=2, max_length=2)
    request: RequestInput
    config: RunConfigInput = Field(default_factory=RunConfigInput)
    round: NonnegativeInt = 0
    budget: dict[CounterName, NonnegativeInt] = Field(default_factory=dict)
    usage: dict[CounterName, NonnegativeInt] = Field(default_factory=dict)


@dataclass
class NormalizedInput:
    parsed: ParsedInput
    request: dict
    papers: list[dict]
    provenance: list[dict]
    round: int
    budget: dict
    usage: dict
    schema_version: str
    config: dict


def _duplicate_safe_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"중복된 JSON 키: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise InputError(f"JSON에 유한하지 않은 숫자를 사용할 수 없습니다: {value}")


def _json_data(value, label):
    """Clone native JSON values so normalization cannot mutate the caller's data."""
    try:
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, allow_nan=False)
        return json.loads(value, object_pairs_hook=_duplicate_safe_object,
                          parse_constant=_invalid_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise InputError(f"{label}은 유효한 JSON이어야 합니다: {exc}") from None


def _text(value, fallback=""):
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _identity(paper: PaperMetadataInput):
    title = paper.title.casefold()
    title_matches = set()
    if re.search(r"\brdkv\b", title):
        title_matches.add("SW-01")
    if "photonic-cxl" in title and "memory appliance" in title:
        title_matches.add("HW-01")
    arxiv_matches = set()
    if paper.arxiv_id:
        match = re.fullmatch(r"(\d{4}\.\d{4,5})(?:v[1-9]\d*)?", paper.arxiv_id)
        if not match:
            raise InputError(f"잘못된 arxiv_id: {paper.arxiv_id}")
        arxiv_matches = {key for key, value in PROJECT_PAPERS.items()
                         if value["arxiv_id"] == match.group(1)}
        if not arxiv_matches:
            raise InputError(f"선정된 논문 쌍에 없는 arxiv_id: {paper.arxiv_id}")
    candidates = title_matches | arxiv_matches
    if len(candidates) != 1:
        raise InputError(f"논문 식별 정보가 없거나 충돌합니다: {paper.title}")
    return candidates.pop()


def _claims_and_references(paper: PaperAnalysisInput, evidence_ids: set[str]):
    claims = {}
    gaps = []
    for section, categories in paper.analysis.items():
        for category, items in categories.items():
            if not isinstance(items, list):
                raise InputError(f"analysis.{section}.{category}는 배열이어야 합니다.")
            if category == "not_reported":
                if any(not isinstance(item, str) for item in items):
                    raise InputError("not_reported는 문자열 배열이어야 합니다.")
                for item in items:
                    gaps.append(f"{paper.paper.paper_id}: upstream 미보고 항목 {section}.{item}")
                continue
            for index, item in enumerate(items):
                path = f"{section}.{category}.{index}"
                claim = PaperClaimInput.model_validate(item)
                refs = set(claim.evidence_ids + claim.context_evidence_ids)
                if refs - evidence_ids:
                    raise InputError(f"{path}: 연결되지 않은 근거 ID {sorted(refs - evidence_ids)}")
                if not claim.evidence_ids:
                    gaps.append(f"{paper.paper.paper_id}: {path}에 직접 연결된 근거가 없습니다.")
                claims[path] = claim
    audits = paper.quality.get("audits", [])
    if not isinstance(audits, list):
        raise InputError("quality.audits는 배열이어야 합니다.")
    seen = set()
    for audit in audits:
        if not isinstance(audit, dict) or not isinstance(audit.get("claim_key"), str):
            raise InputError("각 upstream audit에는 claim_key가 필요합니다.")
        key = audit["claim_key"]
        if key not in claims or key in seen:
            raise InputError(f"중복되거나 연결되지 않은 upstream audit claim_key: {key}")
        seen.add(key)
        refs = audit.get("evidence_ids", [])
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            raise InputError(f"{key}: audit evidence_ids는 문자열 배열이어야 합니다.")
        if set(refs) - evidence_ids:
            raise InputError(f"{key}: audit에서 연결되지 않은 근거 ID가 있습니다.")
        verdict = audit.get("verdict")
        if verdict is not None and not isinstance(verdict, str):
            raise InputError(f"{key}: audit verdict는 문자열이어야 합니다.")
        if verdict not in {"supported", None}:
            gaps.append(f"{paper.paper.paper_id}: upstream audit {key}={audit.get('verdict')}")
    return gaps


def _normalize_papers(models, papers):
    evidence = {}
    raw_evidence = {}
    technologies = {}
    provenance = []
    summaries = []
    gaps = []
    for model, raw in zip(models, papers, strict=True):
        if model.status not in {"succeeded", "partial"}:
            raise InputError(f"upstream 논문 분석 상태를 사용할 수 없습니다: {model.status}")
        tech_id = _identity(model.paper)
        if tech_id in technologies:
            raise InputError(f"동일한 기술의 논문이 중복되었습니다: {tech_id}")
        project = PROJECT_PAPERS[tech_id]
        technologies[tech_id] = Technology(tech_id, project["name"], project["kind"],
                                          project["title"], project["url"])
        ids = {entry.evidence_id for entry in model.evidence_registry}
        gaps.extend(_claims_and_references(model, ids))
        if not ids:
            gaps.append(f"{tech_id}: upstream에 제공된 논문 근거가 없습니다.")
        if model.status == "partial":
            gaps.append(f"{tech_id}: upstream 논문 분석이 partial 상태입니다.")
        missing = [key for key in ("authors", "arxiv_id", "version", "published_at", "url")
                   if not raw["paper"].get(key)]
        if raw["paper"].get("title") != project["title"]:
            missing.append("complete_title")
        if missing:
            gaps.append(f"{tech_id}: upstream 서지 정보 미확인: {', '.join(missing)}. "
                        "제목과 URL은 project_registry의 선정 정보로 보완합니다.")
        for category in ("warnings", "unsupported_claims", "partial_claims"):
            value = model.quality.get(category)
            if value:
                gaps.append(f"{tech_id}: upstream quality.{category}: {_text(value)}")
        if model.diagnostics:
            gaps.append(f"{tech_id}: upstream diagnostics: {_text(model.diagnostics)}")
        truncated = []
        for source, raw_source in zip(model.evidence_registry, raw["evidence_registry"], strict=True):
            if source.document_id != model.paper.paper_id:
                raise InputError(f"{source.evidence_id}: document_id와 paper_id가 일치하지 않습니다.")
            if source.page and model.paper.page_count and source.page > model.paper.page_count:
                raise InputError(f"{source.evidence_id}: 논문 쪽수 범위를 벗어난 근거입니다.")
            if source.evidence_id in raw_evidence:
                if raw_evidence[source.evidence_id] != raw_source:
                    raise InputError(f"근거 ID 충돌: {source.evidence_id}")
                continue
            raw_evidence[source.evidence_id] = raw_source
            location = "; ".join(part for part in (
                f"p. {source.page}" if source.page is not None else "",
                source.section or "",
            ) if part) or "원문 위치 미확인"
            if len(source.snippet) == 1200:
                truncated.append(source.evidence_id)
            evidence[source.evidence_id] = Evidence(
                id=source.evidence_id, tech_ids=[tech_id], title=project["title"],
                url=project["url"], location=location, excerpt=source.snippet,
                author=", ".join(model.paper.authors) or "미표기", source_type="paper", scope="direct",
                content_sha256=sha256(source.snippet.encode("utf-8")).hexdigest(),
                metadata_provenance={
                    "title": "project_registry", "url": "project_registry",
                    "excerpt": "upstream.evidence_registry.snippet",
                    "location": "upstream.evidence_registry.page/section",
                    "content_sha256": "computed_from_supplied_snippet",
                    "upstream_content_hash": source.content_hash or "미확인",
                    "paper_id": model.paper.paper_id,
                    "chunk_id": source.chunk_id or "미확인",
                    "source_schema_version": model.schema_version,
                    "upstream_run_id": _text(model.run.get("run_id"), "미확인"),
                },
            )
        if truncated:
            gaps.append(f"{tech_id}: {len(truncated)}개 발췌가 1,200자 길이로 제한되어 "
                        "원문 일부가 생략되었을 수 있습니다. 원문 chunk 해시와 발췌 해시를 구분합니다.")
        provenance.append({
            "kind": "paper_analysis", "tech_id": tech_id,
            "schema_version": model.schema_version, "status": model.status,
            "paper": raw["paper"], "run": raw.get("run", {}),
            "quality": raw.get("quality", {}), "diagnostics": raw.get("diagnostics", []),
            "identity_source": "upstream.arxiv_id_or_title",
            "display_metadata_source": "project_registry", "project_registry": dict(project),
            "missing_metadata": missing, "possibly_truncated_evidence_ids": truncated,
            "evidence_registry": raw["evidence_registry"],
        })
        summaries.append({"tech_id": tech_id, "paper_id": model.paper.paper_id,
                          "analysis": raw["analysis"], "quality": raw.get("quality", {})})
    return ([technologies[key] for key in PROJECT_PAPERS], evidence, provenance,
            json.dumps(summaries, ensure_ascii=False, indent=2), gaps)


def parse_json_input(data, *, request=None, as_of=None, run_id=None) -> NormalizedInput:
    """Accept an envelope, or two paper JSON objects plus a separate request.

    This function performs no file reads, network requests, or model calls.
    Counter budgets are absolute allocations. Usage is cumulative and may equal
    or exceed its allocation; the runtime must clamp remaining calls to zero.
    """
    data = _json_data(data, "입력")
    if request is not None:
        request = _json_data(request, "request")
    if isinstance(data, list):
        data = {"paper_analyses": data, "request": request}
    elif not isinstance(data, dict):
        raise InputError("입력은 JSON 객체 또는 두 논문 분석의 배열이어야 합니다.")
    elif request is not None:
        if "request" in data and data["request"] != request:
            raise InputError("envelope의 request와 별도 request가 서로 다릅니다.")
        data["request"] = request
    if as_of is not None:
        if not isinstance(data.get("config", {}), dict):
            raise InputError("config는 JSON 객체여야 합니다.")
        config = data.setdefault("config", {})
        if config.get("as_of") is not None and config["as_of"] != as_of:
            raise InputError("서로 다른 조사 기준일이 전달되었습니다.")
        config["as_of"] = as_of
    if run_id is not None:
        if data.get("run_id") is not None and data["run_id"] != run_id:
            raise InputError("서로 다른 run_id가 전달되었습니다.")
        data["run_id"] = run_id
    try:
        model = StakeholderInput.model_validate(data)
        papers = data["paper_analyses"]
        technologies, evidence, provenance, summary, gaps = _normalize_papers(model.paper_analyses, papers)
    except ValidationError as exc:
        # Avoid echoing full source snippets or user contexts in error messages.
        details = "; ".join(f"{'.'.join(map(str, issue['loc']))}: {issue['msg']}"
                            for issue in exc.errors(include_input=False))
        raise InputError(f"JSON 입력 규격 오류: {details}") from None
    resolved_date = model.config.as_of
    date_origin = "input.config.as_of"
    if resolved_date is None:
        resolved_date = datetime.now(UTC).astimezone().date().isoformat()
        date_origin = "runtime_local_date_default"
        gaps.append(f"조사 기준일이 미지정되어 실행일 {resolved_date}를 사용했습니다.")
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", resolved_date, re.ASCII):
            raise ValueError
        date.fromisoformat(resolved_date)
    except ValueError:
        raise InputError("조사 기준일은 유효한 YYYY-MM-DD 날짜여야 합니다.") from None
    resolved_id = model.run_id
    if resolved_id is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", resolved_id):
        raise InputError("run_id는 1~128자의 영문, 숫자, 하이픈 또는 밑줄이어야 합니다.")
    if resolved_id is None:
        resolved_id = "auto-" + uuid4().hex
    safe_config = {key: value for key, value in model.config.model_dump().items()
                   if key in RunConfigInput.model_fields and value is not None}
    safe_config["as_of"] = resolved_date
    if model.config.model_extra:
        gaps.append("미지원 config 필드를 적용하지 않았습니다: " + ", ".join(model.config.model_extra))
    request_data = model.request.model_dump(mode="json")
    extras = {key: _text(value) for key, value in (model.request.model_extra or {}).items()}
    # Domain extensions stay visible to the planner, as well as in the returned request.
    domain_extras = {domain.id: domain.model_extra for domain in model.request.domains if domain.model_extra}
    if domain_extras:
        key = "domain_extensions"
        while key in extras:
            key = "_" + key
        extras[key] = _text(domain_extras)
    context = AnalysisContext(
        original_request=model.request.original_request, objective=model.request.objective,
        constraints=_text(model.request.requirements, "미지정"),
        domains=[Domain(domain.id, domain.name, domain.scenario) for domain in model.request.domains],
        origin="json_request", extra_fields=extras,
        additional_context=_text(model.request.additional_context),
    )
    provenance.append({"kind": "normalization", "as_of": resolved_date, "as_of_source": date_origin,
                       "run_id": resolved_id, "run_id_source": "input" if model.run_id else "generated",
                       "source_schema_versions": [paper.schema_version for paper in model.paper_analyses]})
    parsed = ParsedInput(
        run_id=resolved_id, as_of=resolved_date, technologies=technologies, evidence=evidence,
        summary=summary, gaps=gaps, requested_limits=dict(model.budget), analysis_context=context,
        metadata={"schema_version": model.schema_version, "input_format": "json",
                  "조사 기준일 출처": date_origin, "표시 서지 정보 출처": "project_registry",
                  "upstream_run_ids": _text([paper.run.get("run_id") for paper in model.paper_analyses])},
    )
    return NormalizedInput(parsed=parsed, request=request_data, papers=papers, provenance=provenance,
                           round=model.round, budget=dict(model.budget),
                           usage={"llm": 0, "search": 0, "fetch": 0, **model.usage},
                           schema_version=model.schema_version, config=safe_config)
