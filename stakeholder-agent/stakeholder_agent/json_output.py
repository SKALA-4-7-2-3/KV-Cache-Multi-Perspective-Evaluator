"""Validated JSON handoff of final findings, never of an unfiltered model draft.

Observed benefits and burdens are not technology suitability judgments. The
current research graph does not implement a requirement-level suitability rubric,
so its common criterion is explicitly ``unknown`` while retaining the findings.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import prompts
from .config import AgentConfig
from .models import ResearchPlan
from .stakeholders import coverage_for

if TYPE_CHECKING:
    from .json_input import NormalizedInput


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(OutputModel):
    evidence_id: str
    quote: str


class Finding(OutputModel):
    id: str
    technology_id: Literal["SW-01", "HW-01"]
    domain_id: str
    stakeholder_id: str
    aspect: Literal["benefit", "burden", "adoption_condition", "reaction", "evaluation"]
    kind: Literal["paper_report", "statement", "inference"]
    text: str
    condition: str
    source_scope: Literal["direct", "family", "context"]
    actor: str
    actor_relationship: str
    evidence_ids: list[str]
    supports: list[Citation]


class LinkedInsight(OutputModel):
    text: str
    claim_ids: list[str]
    domain_ids: list[str]
    technology_ids: list[str]


class CriterionResult(OutputModel):
    criterion_id: Literal["stakeholder_impact"] = "stakeholder_impact"
    domain_id: str
    judgment: Literal["unknown"] = "unknown"
    rationale: str = "긍정 및 부정 발언과 목표 요구 충족 판정은 구분하며 기술 적합 판정을 보류합니다."
    conditions: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class TechnologyResult(OutputModel):
    technology_id: Literal["SW-01", "HW-01"]
    summary: list[LinkedInsight] = Field(default_factory=list)
    criteria: list[CriterionResult] = Field(default_factory=list)
    claims: list[Finding] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class SelectedStakeholder(OutputModel):
    id: str
    domain_id: str
    name: str
    reason: str
    priority: Literal["core", "conditional"]


class CoverageRow(OutputModel):
    domain_id: str
    technology_id: str
    stakeholder_id: str
    search_status: Literal["searched", "failed", "not_searched"]
    evidence_status: Literal["direct", "family", "inference_only", "unavailable"]
    claim_ids: list[str]


class SourceAudit(OutputModel):
    evidence_id: str
    cited: bool
    decision: str
    audit: dict[str, Any]


class EvidenceRecord(OutputModel):
    id: str
    technology_ids: list[str]
    title: str
    url: str
    author: str
    publisher: str
    published_at: str
    retrieved_at: str
    source_type: str
    scope: str
    location: str
    excerpt: str
    excerpt_sha256: str
    collected_content_sha256: str
    requested_url: str
    search_queries: list[str]
    metadata_provenance: dict[str, str]
    audit: dict[str, Any]
    upstream: dict[str, Any] | None = None
    cited: bool


class Reference(OutputModel):
    evidence_id: str
    title: str
    url: str
    author: str
    publisher: str
    published_at: str
    retrieved_at: str
    location: str
    source_type: str


class RuntimeMetadata(OutputModel):
    model: str
    prompt_version: str
    input_schema_version: str
    input_sha256: str | None
    as_of: str | None
    outer_round: int
    internal_repair_round: int
    semantic_review_succeeded: bool
    selection_origin: str
    trace: list[str]
    excluded_claim_count: int
    upstream_paper_reverified: Literal[False] = False


class ResultDetails(OutputModel):
    request: dict[str, Any]
    selected_stakeholders: list[SelectedStakeholder]
    observations: list[Finding]
    paper_and_inference_findings: list[Finding]
    summary: list[LinkedInsight]
    implications: list[LinkedInsight]
    coverage: list[CoverageRow]
    source_audits: list[SourceAudit]
    upstream_provenance: list[dict[str, Any]]
    limitations: list[str]
    unverified_model_limitations: list[str]
    used_evidence_ids: list[str]
    runtime: RuntimeMetadata


class AnalysisResult(OutputModel):
    by_technology: dict[Literal["SW-01", "HW-01"], TechnologyResult]
    details: ResultDetails

    @model_validator(mode="after")
    def both_technologies(self):
        if set(self.by_technology) != {"SW-01", "HW-01"}:
            raise ValueError("Both technology result entries must be present")
        if any(key != value.technology_id for key, value in self.by_technology.items()):
            raise ValueError("Technology result identifiers must match their keys")
        return self


class OutputError(OutputModel):
    id: str
    role: Literal["stakeholders"] = "stakeholders"
    round: int
    stage: str
    code: str
    message: str


class Counters(OutputModel):
    llm: int = Field(default=0, ge=0)
    search: int = Field(default=0, ge=0)
    fetch: int = Field(default=0, ge=0)


class Usage(OutputModel):
    limits: Counters
    used: Counters
    remaining: Counters
    delta: Counters

    @model_validator(mode="after")
    def consistent_counters(self):
        for key in ("llm", "search", "fetch"):
            used = getattr(self.used, key)
            if getattr(self.remaining, key) != max(getattr(self.limits, key) - used, 0):
                raise ValueError(f"{key}: remaining must equal max(limits - used, 0)")
            if getattr(self.delta, key) > used:
                raise ValueError(f"{key}: delta cannot exceed cumulative usage")
        return self


class StakeholderOutput(OutputModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    role: Literal["stakeholders"] = "stakeholders"
    round: int = Field(ge=0)
    execution_status: Literal["completed", "failed"]
    evidence_status: Literal["sufficient", "limited", "unavailable"]
    status: Literal["completed", "partial", "failed"]
    mode: Literal["live", "fixture"]
    result: AnalysisResult
    new_evidence: dict[str, EvidenceRecord]
    evidence: dict[str, EvidenceRecord]
    references: list[Reference]
    gaps: list[str]
    follow_up_questions: list[str]
    errors: list[OutputError]
    usage: Usage

    @model_validator(mode="after")
    def consistent_links(self):
        claims = [claim for result in self.result.by_technology.values() for claim in result.claims]
        by_id = {claim.id: claim for claim in claims}
        if len(by_id) != len(claims):
            raise ValueError("Claim IDs must be unique")
        used = {eid for claim in claims for eid in claim.evidence_ids}
        if not used <= self.evidence.keys():
            raise ValueError("Claims must reference registered evidence")
        if any(key != record.id for key, record in self.evidence.items()):
            raise ValueError("Evidence identifiers must match registry keys")
        for claim in claims:
            if not claim.evidence_ids or {s.evidence_id for s in claim.supports} != set(claim.evidence_ids):
                raise ValueError("Claim citations must match their evidence IDs")
        details = self.result.details
        for group, expected_kind in ((details.observations, "statement"),
                                     (details.paper_and_inference_findings, "analytical")):
            expected = {claim.id: claim for claim in claims
                        if (claim.kind == "statement") == (expected_kind == "statement")}
            actual = {claim.id: claim for claim in group}
            if len(actual) != len(group) or actual != expected:
                raise ValueError("Detail finding partitions must exactly match canonical accepted claims")
        if set(details.used_evidence_ids) != used or {r.evidence_id for r in self.references} != used:
            raise ValueError("References must contain exactly the cited evidence")

        def check_insight(item):
            if not item.claim_ids or not set(item.claim_ids) <= by_id.keys():
                raise ValueError("Insights must reference accepted claims")
            referenced = [by_id[identifier] for identifier in item.claim_ids]
            if (set(item.domain_ids) != {claim.domain_id for claim in referenced}
                    or set(item.technology_ids) != {claim.technology_id for claim in referenced}):
                raise ValueError("Insight scope must match its referenced claims")

        for item in [*details.summary, *details.implications]:
            check_insight(item)
        for result in self.result.by_technology.values():
            own_ids = {claim.id for claim in result.claims}
            if any(claim.technology_id != result.technology_id for claim in result.claims):
                raise ValueError("Claims must match their enclosing technology result")
            for item in [*result.summary, *result.criteria]:
                if not set(item.claim_ids) <= own_ids:
                    raise ValueError("Technology evaluations must reference their own claims")
            for item in result.summary:
                check_insight(item)
            for item in result.criteria:
                if any(by_id[identifier].domain_id != item.domain_id for identifier in item.claim_ids):
                    raise ValueError("Criterion domain must match its referenced claims")
        for row in details.coverage:
            if not set(row.claim_ids) <= by_id.keys():
                raise ValueError("Coverage must reference accepted claims")
            if any((by_id[identifier].technology_id, by_id[identifier].domain_id,
                    by_id[identifier].stakeholder_id)
                   != (row.technology_id, row.domain_id, row.stakeholder_id)
                   for identifier in row.claim_ids):
                raise ValueError("Coverage scope must match its referenced claims")
        if any(record.source_type != "web" or self.evidence.get(key) != record
               for key, record in self.new_evidence.items()):
            raise ValueError("New evidence must be collected web evidence in the registry")
        if self.execution_status == "failed" and claims:
            raise ValueError("Failed semantic validation cannot publish accepted claims")
        return self


def _unique(values):
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value.strip()))


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _usage(state, normalized, config):
    previous = normalized.usage if normalized else state.get("initial_usage", {})
    defaults = {"llm": config.llm_limit, "search": config.search_limit, "fetch": config.fetch_limit}
    requested = normalized.budget if normalized else state.get("initial_budget", {})
    budget = state.get("budget")
    limits = dict(budget.limits) if budget else {key: min(value, requested.get(key, value))
                                               for key, value in defaults.items()}
    current = dict(budget.used) if budget else dict(previous)
    used = {key: max(previous.get(key, 0), current.get(key, 0)) for key in defaults}
    return Usage(limits=Counters(**limits), used=Counters(**used),
                 remaining=Counters(**{key: max(0, limits[key] - used[key]) for key in defaults}),
                 delta=Counters(**{key: used[key] - previous.get(key, 0) for key in defaults}))


def render_json_output(state: dict, normalized: NormalizedInput | None, *, config: AgentConfig,
                       mode: str = "live", input_error: str | None = None) -> dict:
    """Export reviewed findings with stable IDs and the latest design's envelope.

    The semantic review gate fails closed. Source bodies are the bounded excerpts
    actually supplied to the graph, retained for downstream citation validation.
    The original upstream evidence IDs and raw chunk provenance are preserved.
    """
    # Import at call time because the graph's renderer may import this module.
    from .graph import validate_claims

    parsed = state.get("parsed") or (normalized.parsed if normalized else None)
    run_id = parsed.run_id if parsed else state.get("error_run_id", "unavailable")
    outer_round = normalized.round if normalized else state.get("outer_round", 0)
    domains = parsed.analysis_context.domains if parsed else []
    tech_ids = {tech.id for tech in parsed.technologies} if parsed else set()
    draft = state.get("draft")
    plan = state.get("plan") or ResearchPlan(questions=[], stakeholders=[])
    selected = [target for target in plan.stakeholders if target.domain_id in {d.id for d in domains}]
    plan = ResearchPlan(questions=plan.questions, stakeholders=selected)
    sources = dict(parsed.evidence) if parsed else {}
    sources.update(state.get("evidence", {}))
    usable_sources = state.get("evidence", sources)
    semantic_ok = bool(state.get("review_succeeded")) and not input_error
    execution_ok = (draft is not None and parsed is not None and semantic_ok
                    and state.get("execution_status") != "failed")
    rejected = set(state.get("rejected", []))
    if state.get("review"):
        rejected.update(state["review"].rejected_claim_indices)
    issues = []
    if draft and parsed:
        invalid, issues = validate_claims(draft, usable_sources, tech_ids, {d.id for d in domains},
                                         {(t.domain_id, t.id) for t in selected},
                                         allow_family_inference=True)
        rejected.update(invalid)
    accepted = {index: claim for index, claim in enumerate(draft.claims)
                if execution_ok and index not in rejected and claim.kind != "unknown"} if draft else {}
    claim_ids = {index: f"STK-{run_id}-R{outer_round}-C{index + 1:03d}" for index in accepted}
    findings = {
        index: Finding(id=claim_ids[index], technology_id=claim.tech_id, domain_id=claim.domain_id,
                       stakeholder_id=claim.group, aspect=claim.aspect, kind=claim.kind, text=claim.text,
                       condition=claim.condition, source_scope=claim.source_scope, actor=claim.actor,
                       actor_relationship=claim.actor_relationship,
                       evidence_ids=_unique(s.evidence_id for s in claim.supports),
                       supports=[Citation(**support.model_dump()) for support in claim.supports])
        for index, claim in accepted.items()
    }
    used_ids = _unique(eid for finding in findings.values() for eid in finding.evidence_ids)

    def linked(insights):
        rows = []
        for insight in insights:
            if not insight.claim_indices or any(index not in findings for index in insight.claim_indices):
                continue
            ids = list(dict.fromkeys(insight.claim_indices))
            rows.append(LinkedInsight(text=insight.text, claim_ids=[claim_ids[index] for index in ids],
                                      domain_ids=_unique(findings[index].domain_id for index in ids),
                                      technology_ids=_unique(findings[index].technology_id for index in ids)))
        return rows

    summary = linked(draft.summary) if draft else []
    implications = linked(draft.implications) if draft else []
    if not summary:
        for domain in domains:
            for technology_id in ("SW-01", "HW-01"):
                candidate = next((row for row in findings.values() if row.domain_id == domain.id
                                  and row.technology_id == technology_id), None)
                if candidate:
                    summary.append(LinkedInsight(text=candidate.text, claim_ids=[candidate.id],
                                                 domain_ids=[domain.id], technology_ids=[technology_id]))

    coverage = []
    if parsed:
        for row in coverage_for(parsed, plan, list(accepted.items()), state.get("research_log", [])):
            coverage.append(CoverageRow(domain_id=row["domain_id"], technology_id=row["tech_id"],
                                        stakeholder_id=row["group"], search_status=row["search_status"],
                                        evidence_status=row["evidence_status"],
                                        claim_ids=[claim_ids[index] for index in row["claim_indices"]]))
    required = {(target.domain_id, target.id, tech_id) for target in selected
                if target.priority == "core" for tech_id in tech_ids}
    direct = {(row.domain_id, row.stakeholder_id, row.technology_id) for row in coverage
              if row.evidence_status == "direct"}
    evidence_status = ("sufficient" if execution_ok and required and required <= direct
                       else "limited" if findings else "unavailable")
    if mode == "fixture" and evidence_status == "sufficient":
        evidence_status = "limited"

    error_messages = _unique([*state.get("errors", []), *([input_error] if input_error else [])])
    if state.get("pending_source_ids"):
        error_messages.append("출처 검토 미완료: " + ", ".join(state["pending_source_ids"])
                              + ". 보류 자료는 주장 근거로 사용하지 않았습니다.")
    if not semantic_ok and draft is not None:
        error_messages.append("의미 검토를 완료하지 못하여 분석 주장과 그 요약을 공개 결과에서 제외했습니다.")
    errors = [OutputError(id=f"STK-{run_id}-R{outer_round}-ERR-{_digest(message)[:12]}",
                          round=outer_round, stage="input" if message == input_error else "research_or_review",
                          code="invalid_input" if message == input_error else "execution_issue", message=message)
              for message in _unique(error_messages)]
    gaps = _unique([*(parsed.gaps if parsed else []), *state.get("gaps", []), *issues])
    if mode == "fixture":
        gaps.append("오프라인 fixture 실행입니다. 실제 모델 및 웹 조사 결과가 아닙니다.")
    if rejected:
        gaps.append(f"검증에서 제외된 주장 {len(rejected)}개와 이에 의존한 요약 및 시사점은 사용하지 않았습니다.")
    if draft:
        for claim in draft.claims:
            if claim.kind == "unknown":
                gaps.append(f"{claim.domain_id}/{claim.tech_id}/{claim.group}: {claim.aspect} 근거를 확보하지 못했습니다.")
    if not findings:
        gaps.append("현재 조사와 검토를 통과하여 전달할 수 있는 이해관계자 관찰이 없습니다.")

    upstream = {record["evidence_id"]: record for paper in (normalized.papers if normalized else [])
                for record in paper.get("evidence_registry", [])}
    evidence = {}
    for identifier, source in sources.items():
        values = asdict(source)
        evidence[identifier] = EvidenceRecord(
            id=identifier, technology_ids=values["tech_ids"], title=source.title, url=source.url,
            author=source.author, publisher=source.publisher, published_at=source.published_at,
            retrieved_at=source.retrieved_at, source_type=source.source_type, scope=source.scope,
            location=source.location, excerpt=source.excerpt,
            excerpt_sha256=sha256(source.excerpt.encode("utf-8")).hexdigest(),
            collected_content_sha256=source.content_sha256, requested_url=source.requested_url,
            search_queries=list(source.search_queries), metadata_provenance=deepcopy(source.metadata_provenance),
            audit=deepcopy(source.audit), upstream=deepcopy(upstream.get(identifier)), cited=identifier in used_ids)
    references = [Reference(evidence_id=eid, **{key: getattr(evidence[eid], key) for key in (
        "title", "url", "author", "publisher", "published_at", "retrieved_at", "location", "source_type")})
        for eid in used_ids]
    by_technology = {}
    for tech_id in ("SW-01", "HW-01"):
        own = [finding for finding in findings.values() if finding.technology_id == tech_id]
        tech_gaps = [] if own else ["검토를 통과한 해당 기술의 이해관계자 관찰을 확보하지 못했습니다."]
        criteria = []
        for domain in domains:
            domain_claims = [finding for finding in own if finding.domain_id == domain.id]
            criteria.append(CriterionResult(domain_id=domain.id, claim_ids=[claim.id for claim in domain_claims],
                                            conditions=_unique(claim.condition for claim in domain_claims),
                                            gaps=["관찰의 긍정 및 부정 여부를 기술 적합성 판정으로 변환하지 않았습니다."]))
        by_technology[tech_id] = TechnologyResult(
            technology_id=tech_id, summary=[item for item in summary if item.technology_ids == [tech_id]],
            criteria=criteria, claims=own, gaps=tech_gaps)

    request = deepcopy(normalized.request) if normalized else {}
    metadata = RuntimeMetadata(
        model=state.get("runtime_model_id", config.model),
        prompt_version=getattr(prompts, "PROMPT_VERSION", "unversioned"),
        input_schema_version=normalized.schema_version if normalized else "unknown",
        input_sha256=_digest({"schema_version": normalized.schema_version,
                              "request": normalized.request, "paper_analyses": normalized.papers,
                              "config": normalized.config, "budget": normalized.budget,
                              "usage": normalized.usage, "round": normalized.round})
        if normalized else None,
        as_of=parsed.as_of if parsed else None, outer_round=outer_round,
        internal_repair_round=state.get("round", 0), semantic_review_succeeded=semantic_ok,
        selection_origin=state.get("selection_origin", "unavailable"), trace=list(state.get("trace", [])),
        excluded_claim_count=len(rejected))
    details = ResultDetails(
        request=request, selected_stakeholders=[SelectedStakeholder(**target.model_dump()) for target in selected],
        observations=[finding for finding in findings.values() if finding.kind == "statement"],
        paper_and_inference_findings=[finding for finding in findings.values() if finding.kind != "statement"],
        summary=summary, implications=implications, coverage=coverage,
        source_audits=[SourceAudit(evidence_id=eid, cited=record.cited,
                                  decision=record.audit.get("decision", "hold"), audit=record.audit)
                       for eid, record in evidence.items() if record.source_type == "web"],
        upstream_provenance=deepcopy(normalized.provenance) if normalized else [],
        limitations=[
            "논문 근거는 상위 에이전트가 전달한 발췌이며 이 에이전트가 논문 전체를 재검증한 것은 아닙니다.",
            "출처 분류와 구절 확인은 내용의 진실성이나 독립 재현을 보장하지 않습니다.",
            "실제 발언과 논문 보고 및 분석적 추론을 구분하며, 관련 기술 계열 자료를 대상 논문의 직접 반응으로 해석하지 않습니다.",
            "현재 에이전트는 관찰을 제공하며, 긍정 및 부정 발언만으로 목표 요구조건 대비 기술 적합성을 판정하지 않습니다.",
        ], unverified_model_limitations=list(draft.limitations) if draft else [],
        used_evidence_ids=used_ids, runtime=metadata)
    status = ("failed" if not execution_ok else "partial" if errors or gaps or evidence_status != "sufficient"
              or state.get("status") == "partial" else "completed")
    output = StakeholderOutput(
        run_id=run_id, round=outer_round, execution_status="completed" if execution_ok else "failed",
        evidence_status=evidence_status, status=status, mode=mode,
        result=AnalysisResult(by_technology=by_technology, details=details),
        new_evidence={eid: record for eid, record in evidence.items() if record.source_type == "web"},
        evidence=evidence, references=references, gaps=_unique(gaps),
        follow_up_questions=_unique(draft.follow_up if draft else []), errors=errors,
        usage=_usage(state, normalized, config))
    return output.model_dump(mode="json")
