"""A bounded research graph. Every invocation owns its state and budgets."""

import re
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256

from langgraph.graph import END, START, StateGraph

from . import prompts
from .config import AgentConfig
from .contracts import InputError, parse_input, render_output
from .evidence import quote_options, resolve_support_quotes, source_quote_has_text
from .models import (
    ASPECT_LABELS,
    AgentState,
    Assessment,
    Budget,
    Evidence,
    ResearchPlan,
    Review,
    SearchQuestion,
)
from .retrieval import candidate_matches, discovery_candidate
from .source_quality import assess_operator_sources, assess_web_sources, pending_web_source_ids, web_source_issue
from .stakeholders import aggregate_evidence_status, coverage_for, operating_organizations, select_targets


def _unique(items):
    return list(dict.fromkeys(items))


def _normal(text: str) -> str:
    return " ".join(text.split()).casefold()


def _candidate_matches(technology, hit) -> bool:
    return candidate_matches(technology, hit)


def validate_claims(draft: Assessment, evidence: dict[str, Evidence], tech_ids: set[str],
                    domain_ids: set[str] | None = None, selected_targets=None,
                    *, allow_family_inference: bool = False):
    """Check ID, technology and literal source span; semantic validity is reviewed separately."""
    rejected, issues = [], []
    seen_claims = set()
    for index, claim in enumerate(draft.claims):
        reason = ""
        if claim.tech_id not in tech_ids:
            reason = "알 수 없는 기술 ID"
        elif domain_ids is not None and claim.domain_id not in domain_ids:
            reason = "누락되거나 알 수 없는 도메인 ID"
        elif selected_targets is not None and (claim.domain_id, claim.group) not in selected_targets:
            reason = "이 도메인의 조사 대상으로 선정되지 않은 역할"
        elif not claim.text.strip():
            reason = "빈 주장"
        elif claim.kind == "statement" and (not claim.actor.strip()
                                            or claim.actor_relationship == "unspecified"):
            reason = "실제 발언·평가의 주체와 관계가 명시되지 않음"
        elif claim.kind == "unknown":
            if claim.supports:
                reason = "미확인 주장에 사실 근거를 붙임"
        elif not claim.supports:
            reason = "근거 없는 주장"
        elif claim.aspect == "reaction" and claim.kind not in ("statement", "unknown"):
            reason = "추론 또는 논문 보고를 실제 반응으로 사용"
        elif claim.source_scope == "context":
            reason = "일반 배경 자료로 특정 기술의 편익·조건·반응을 판단함"
        elif (claim.source_scope == "family" and claim.kind != "statement"
              and not (allow_family_inference and claim.kind == "inference")):
            reason = "기술 계열 자료에서 특정 구현의 효과·도입 조건을 추정함"
        for support in claim.supports:
            source = evidence.get(support.evidence_id)
            if source is None:
                reason = "등록되지 않은 근거 ID"
            elif claim.tech_id not in source.tech_ids:
                reason = "다른 기술의 근거"
            elif len(support.quote.strip()) < 12 or _normal(support.quote) not in _normal(source.excerpt):
                reason = "원문에서 확인되지 않는 근거 구절"
            elif source.source_type == "web" and not source_quote_has_text(source.excerpt, support.quote):
                reason = "웹 근거가 링크 주소·짧은 메뉴 등으로 구성되어 본문 근거로 불충분함"
            elif claim.kind == "paper_report" and source.source_type != "paper":
                reason = "웹 자료를 논문 보고로 표시"
            elif claim.kind == "statement" and source.source_type == "paper":
                reason = "입력 논문 보고를 외부 이해관계자의 실제 평가로 표시"
            elif claim.aspect == "reaction" and source.source_type == "paper":
                reason = "논문 내용을 외부 주체의 실제 반응으로 표시"
            if source is not None and (issue := web_source_issue(
                    source, claim, allow_family_inference=allow_family_inference)):
                reason = issue
        signature = (claim.domain_id, claim.tech_id, claim.kind, _normal(claim.actor), _normal(claim.text))
        if claim.kind != "unknown" and signature in seen_claims:
            reason = "같은 도메인·기술의 동일 관찰을 역할별로 반복함"
        if reason:
            rejected.append(index)
            issues.append(f"주장 {index}: {reason}")
        elif claim.kind != "unknown":
            seen_claims.add(signature)
    return rejected, issues


def build_graph(config: AgentConfig, model, web):
    """Compile without making network calls; providers are replaceable objects."""
    def prepare(state: AgentState):
        limits = {"search": config.search_limit, "fetch": config.fetch_limit, "llm": config.llm_limit}
        used = {key: state.get("initial_usage", {}).get(key, 0) for key in limits}
        base = {"parsed": None, "evidence": {}, "budget": Budget(limits, used), "draft": None, "review": None,
                "rejected": [], "errors": [], "gaps": [], "round": 0, "status": "running", "trace": ["prepare"],
                "searched_queries": [], "searched_pairs": [], "research_log": [], "coverage": [],
                "execution_status": "running", "evidence_status": "unavailable", "review_succeeded": False,
                "pending_source_ids": []}
        try:
            if state.get("normalized_input") is not None:
                parsed = state["normalized_input"].parsed
            else:
                if len(state["input_md"]) > config.max_input_chars:
                    raise InputError("입력 Markdown이 허용 크기를 넘었습니다.")
                parsed = parse_input(state["input_md"])
            for key, value in parsed.requested_limits.items():
                if key in limits:
                    limits[key] = min(limits[key], value)
            usable = dict(parsed.evidence)
            gaps = list(parsed.gaps)
            for eid, record in parsed.evidence.items():
                published = re.search(r"\d{4}-\d{2}-\d{2}", record.published_at)
                if published and published.group() > parsed.as_of:
                    usable.pop(eid)
                    gaps.append(f"평가 기준일 이후 입력 근거 제외: {eid}")
            base.update(parsed=parsed, evidence=usable, gaps=gaps)
            if model is None:
                base.update(status="failed", execution_status="failed",
                            errors=["LLM 설정이 없습니다. OPENAI_API_KEY를 설정하세요."])
            elif web is None:
                base["errors"] = ["외부 검색 설정이 없습니다. TAVILY_API_KEY를 설정하세요."]
        except InputError as exc:
            base.update(status="failed", execution_status="failed", errors=[str(exc)])
        return base

    def context(state):
        p = state["parsed"]
        focused = state.get("output_format") == "json"
        targets = (state["plan"].stakeholders if state.get("plan")
                   else operating_organizations(p.analysis_context.domains) if focused else [])
        return {"as_of": p.as_of, "technologies": [asdict(t) for t in p.technologies],
                "analysis_context": asdict(p.analysis_context),
                "analysis_mode": "operator_impact" if focused else "stakeholder_reactions",
                "max_claims": min(12 * len(p.analysis_context.domains), 72),
                "selected_stakeholders": [t.model_dump() for t in targets],
                "stakeholder_coverage": state.get("coverage", []),
                "research_log": state.get("research_log", []),
                "research_coverage": [
                    {"domain_id": d.id, "tech_id": t.id,
                     "search_attempted": (d.id, t.id) in state.get("searched_pairs", [])}
                    for d in p.analysis_context.domains for t in p.technologies],
                "summary": p.summary,
                "evidence": [{**asdict(e), "quote_options": quote_options(e)}
                             for e in state["evidence"].values()],
                "input_gaps": state["gaps"], "input_requests": p.metadata.get("추가 요청 및 정보 공백", ""),
                "tool_errors": state["errors"],
                "remaining_budget": {k: state["budget"].remaining(k) for k in ("search", "fetch", "llm")}}

    def ask(state, schema, system, payload):
        if not state["budget"].take("llm"):
            raise RuntimeError("llm_budget_exhausted")
        result = model.generate(schema=schema, system=system, payload=payload)
        return result if isinstance(result, schema) else schema.model_validate(result)

    def clean_questions(state, questions, targets=None):
        ids = {t.id for t in state["parsed"].technologies}
        domain_ids = {d.id for d in state["parsed"].analysis_context.domains}
        targets = targets if targets is not None else state["plan"].stakeholders
        role_ids = {(t.domain_id, t.id) for t in targets}
        cleaned = []
        for question in questions:
            if not question.domain_id and len(domain_ids) == 1:
                question = question.model_copy(update={"domain_id": next(iter(domain_ids))})
            if (question.tech_id in ids and question.domain_id in domain_ids
                    and (question.domain_id, question.group) in role_ids
                    and 0 < len(question.query.strip()) <= 500):
                cleaned.append(question)
        return cleaned

    def plan(state):
        errors = list(state["errors"])
        try:
            result = ask(state, ResearchPlan, prompts.PLAN, context(state))
        except Exception as exc:  # noqa: BLE001 - isolate failures from an injected provider
            if getattr(exc, "fatal", False):
                errors.append(getattr(exc, "public_message", "모델 인증 또는 접근 권한 오류"))
                return {"status": "failed", "execution_status": "failed", "errors": errors,
                        "trace": state["trace"] + ["plan"], "budget": state["budget"]}
            errors.append(f"조사 계획 생성 실패 ({type(exc).__name__}); 기본 질문 사용")
            result = ResearchPlan(questions=[])
        if state.get("output_format") == "json":
            targets = operating_organizations(state["parsed"].analysis_context.domains)
            origin, selection_issues = "domain_operator", []
            # Returned planning roles cannot expand the agreed analysis scope.
            result.questions = [q.model_copy(update={"group": "operator"}) for q in result.questions]
        else:
            targets, origin, selection_issues = select_targets(
                result.stakeholders, state["parsed"].analysis_context.domains)
        questions = clean_questions(state, result.questions, targets)
        # Represent every requested domain/technology pair; the research node
        # spends one shared budget and reports pairs it could not investigate.
        balanced = []
        for domain in state["parsed"].analysis_context.domains:
            roles = [t for t in targets if t.domain_id == domain.id]
            default_role = next((t for t in roles if t.id == "developer"), roles[0])
            for tech in state["parsed"].technologies:
                own = [q for q in questions if q.tech_id == tech.id and q.domain_id == domain.id]
                balanced.append(own[0] if own else SearchQuestion(
                    tech_id=tech.id, domain_id=domain.id, group=default_role.id,
                    query=f'"{tech.name[:120]}" "{domain.name[:120]}" implementation deployment limitations',
                    reason=f"{domain.name}: 공개 구현·도입 조건 확인"))
        if state.get("output_format") == "json":
            # A model can return no questions. Keep the related-family search
            # symmetric instead of falling back only to each exact paper name.
            for domain in state["parsed"].analysis_context.domains:
                for tech in state["parsed"].technologies:
                    family_query = ("KV cache quantization compression accuracy inference serving documentation"
                                    if tech.kind.upper() == "SW" else
                                    "CXL memory pooling KV cache offloading inference deployment")
                    balanced.append(SearchQuestion(
                        tech_id=tech.id, domain_id=domain.id, group="operator", query=family_query,
                        reason=f"{domain.name}: 관련 기술 계열의 운영 이익과 통합 제약 확인"))
        balanced += [q for q in questions if q not in balanced]
        return {"plan": ResearchPlan(questions=balanced, stakeholders=targets), "errors": errors,
                "selection_origin": origin, "gaps": _unique([*state["gaps"], *selection_issues]),
                "trace": state["trace"] + ["plan"], "budget": state["budget"]}

    def research(state):
        budget = state["budget"]
        evidence, errors, gaps = dict(state["evidence"]), list(state["errors"]), list(state["gaps"])
        p = state["parsed"]
        round_number = state["round"]
        questions = state["plan"].questions
        if "validate" in state["trace"]:
            round_number += 1
            # Finish reviewing already collected documents before buying more searches.
            questions = (clean_questions(state, state["review"].queries)
                         if state.get("review") and not state.get("pending_source_ids") else [])
        limit = min(budget.remaining("search"), 4 if round_number == 0 else 2)
        if web is None:
            questions = []
        seen = {e.url: e for e in evidence.values()}
        searched = set(state.get("searched_queries", []))
        searched_pairs = list(state.get("searched_pairs", []))
        research_log = list(state.get("research_log", []))
        attempted = 0
        for question in questions:
            if attempted >= limit:
                break
            if _normal(question.query) in searched:
                continue
            if not budget.take("search"):
                break
            attempted += 1
            searched.add(_normal(question.query))
            pair = (question.domain_id, question.tech_id)
            if pair not in searched_pairs:
                searched_pairs.append(pair)
            try:
                hits = web.search(question.query, max_results=3)
                research_log.append({"domain_id": question.domain_id, "tech_id": question.tech_id,
                                     "group": question.group, "query": question.query, "status": "searched"})
            except Exception as exc:  # noqa: BLE001 - preserve partial results on provider failure
                research_log.append({"domain_id": question.domain_id, "tech_id": question.tech_id,
                                     "group": question.group, "query": question.query, "status": "failed"})
                errors.append(f"외부 검색 실패 ({type(exc).__name__}) / {question.domain_id}/{question.tech_id}")
                continue
            if not hits:
                gaps.append(f"{question.domain_id}/{question.tech_id}/{question.group}: 해당 검색에서 원문 후보를 찾지 못함")
            technology = next(t for t in p.technologies if t.id == question.tech_id)
            # Existing input URLs still pass through the dedup branch without changing their ownership.
            candidate_filter = (discovery_candidate if state.get("output_format") == "json"
                                else _candidate_matches)
            candidates = [h for h in hits if h.url in seen or candidate_filter(technology, h)]
            if hits and not candidates:
                gaps.append(f"{question.domain_id}/{question.tech_id}/{question.group}: 검색 후보가 입력 논문 중복 또는 대상 기술 계열과의 관련성 부족으로 제외됨")
            for hit in candidates[:2]:
                if hit.url in seen:
                    existing = seen[hit.url]
                    if existing.source_type == "web":
                        existing.search_queries = _unique([*existing.search_queries, question.query])
                        if question.tech_id not in existing.tech_ids:
                            # A query association is not proof of source relevance.
                            existing.tech_ids = [*existing.tech_ids, question.tech_id]
                    continue
                if not budget.take("fetch"):
                    break
                try:
                    page = web.fetch(hit.url)
                    if not page.text.strip():
                        raise ValueError("empty_source")
                    publication = page.published_at
                    match = re.search(r"\d{4}-\d{2}-\d{2}", publication)
                    if match and match.group() > p.as_of:
                        gaps.append(f"평가 기준일 이후 자료 제외: {page.title[:100]}")
                    if page.url in seen:
                        existing = seen[page.url]
                        if existing.source_type == "web":
                            existing.search_queries = _unique([*existing.search_queries, question.query])
                            if question.tech_id not in existing.tech_ids:
                                existing.tech_ids = [*existing.tech_ids, question.tech_id]
                        continue
                    counter = len(evidence) + 1
                    namespace = f"STK-{p.run_id}"
                    if state.get("normalized_input") is not None:
                        namespace += f"-R{state['normalized_input'].round}"
                    eid = f"{namespace}-E{counter:03d}"
                    occupied = {key.casefold() for key in evidence}
                    while eid.casefold() in occupied:
                        counter += 1
                        eid = f"{namespace}-E{counter:03d}"
                    excerpt = page.text[:config.page_chars]
                    record = Evidence(id=eid, tech_ids=[question.tech_id], title=page.title,
                                      url=page.url, location=page.location, excerpt=excerpt,
                                      publisher=page.publisher, published_at=publication,
                                      retrieved_at=datetime.now(UTC).date().isoformat(),
                                      source_type="web", scope="unclassified",
                                      author=getattr(page, "author", "미표기"), requested_url=hit.url,
                                      metadata_provenance=dict(getattr(page, "metadata_provenance", {})),
                                      search_queries=[question.query],
                                      content_sha256=sha256(excerpt.encode("utf-8")).hexdigest())
                    evidence[eid] = record
                    seen[hit.url] = record
                    seen[page.url] = record
                except Exception as exc:  # noqa: BLE001 - one failed page must not discard other evidence
                    errors.append(f"원문 조회 실패 ({type(exc).__name__}) / {question.domain_id}/{question.tech_id}")
        evidence = (assess_operator_sources(evidence, p.as_of, p.technologies)
                    if state.get("output_format") == "json" else
                    assess_web_sources(evidence, [], p.as_of, technologies=p.technologies,
                                       preserve_existing=True))
        return {"evidence": evidence, "errors": _unique(errors), "gaps": _unique(gaps),
                "pending_source_ids": pending_web_source_ids(evidence),
                "budget": budget, "round": round_number, "searched_queries": sorted(searched),
                "searched_pairs": searched_pairs,
                "research_log": research_log,
                "trace": state["trace"] + ["research"]}

    def analyze(state):
        errors = list(state["errors"])
        payload = context(state)
        payload["feedback"] = state["review"].model_dump() if state.get("review") else {}
        payload["mechanical_rejections"] = state.get("rejected", [])
        payload["required_source_review_ids"] = pending_web_source_ids(state["evidence"])
        if state.get("review") and state.get("draft"):
            payload["previous_draft"] = state["draft"].model_dump()
        try:
            draft = ask(state, Assessment, prompts.ANALYZE, payload)
            if len(draft.claims) > payload["max_claims"]:
                raise ValueError("too_many_claims")
            resolve_support_quotes(draft, state["evidence"])
            evidence = (assess_operator_sources(state["evidence"], state["parsed"].as_of,
                                                state["parsed"].technologies)
                        if state.get("output_format") == "json" else
                        assess_web_sources(state["evidence"], draft.source_reviews, state["parsed"].as_of,
                                           technologies=state["parsed"].technologies, preserve_existing=True))
            for claim in draft.claims:
                domains = state["parsed"].analysis_context.domains
                if not claim.domain_id and len(domains) == 1:
                    claim.domain_id = domains[0].id
                if claim.kind == "unknown":
                    # An unverified sentence must not retain invented facts in the comparison table.
                    claim.text = f"미확인 — {ASPECT_LABELS[claim.aspect]}의 근거를 이번 조사에서 확보하지 못했습니다."
                    claim.condition = "입력과 조회 범위에 한정하며 공개 자료 전체의 부재를 의미하지 않습니다."
            return {"draft": draft, "evidence": evidence, "rejected": [], "errors": errors,
                    "pending_source_ids": pending_web_source_ids(evidence), "budget": state["budget"],
                    "trace": state["trace"] + ["analyze"]}
        except Exception as exc:  # noqa: BLE001 - preserve the previous draft if a provider fails
            errors.append(f"분석 생성 실패 ({type(exc).__name__})")
            return {"errors": errors, "budget": state["budget"],
                    "trace": state["trace"] + ["analyze"]}

    def validate(state):
        draft, errors = state["draft"], list(state["errors"])
        if draft is None:
            return {"status": "failed", "execution_status": "failed", "trace": state["trace"] + ["validate"]}
        p = state["parsed"]
        bad, issues = validate_claims(draft, state["evidence"], {t.id for t in p.technologies},
                                     {d.id for d in p.analysis_context.domains},
                                     {(t.domain_id, t.id) for t in state["plan"].stakeholders},
                                     allow_family_inference=state.get("output_format") == "json")
        pending = pending_web_source_ids(state["evidence"])
        issues.extend(f"출처 검토 미완료: {eid} — 기존 본문으로 출처 평가를 보완해야 함" for eid in pending)
        bad = _unique([*bad, *state["rejected"]])
        review = Review(rejected_claim_indices=[], issues=[], queries=[])
        review_succeeded = False
        if state["budget"].remaining("llm"):
            try:
                payload = context(state)
                indexed_draft = draft.model_dump()
                indexed_draft["claims"] = [{"claim_index": i, **claim.model_dump()}
                                           for i, claim in enumerate(draft.claims)]
                payload.update(draft=indexed_draft, mechanical_issues=issues,
                               review_candidate_indices=[i for i in range(len(draft.claims)) if i not in bad])
                review = ask(state, Review, prompts.REVIEW, payload)
                if any(i < 0 or i >= len(draft.claims) for i in review.rejected_claim_indices):
                    raise ValueError("invalid_review_index")
                bad = _unique([*bad, *review.rejected_claim_indices])
                review_succeeded = True
            except Exception as exc:  # noqa: BLE001 - mark failed semantic validation explicitly
                errors.append(f"의미 검토 실패 ({type(exc).__name__}); 결과를 부분 완료로 표시")
        else:
            errors.append("의미 검토 생략: LLM 호출 한도 소진")
        review.issues = _unique([*issues, *review.issues])
        valid = [(i, c) for i, c in enumerate(draft.claims) if i not in bad]
        coverage = coverage_for(p, state["plan"], valid, state.get("research_log", []))
        gaps = [gap for gap in state["gaps"]
                if not gap.startswith(("외부 조사 미수행:", "출처 검토 미완료:"))]
        gaps.extend(issue for issue in issues if issue.startswith("출처 검토 미완료:"))
        gaps.extend(f"외부 조사 미수행: {d.id}({d.name})/{t.id} — 공유 호출 한도·검색 계획·도구 가용성의 제한"
                    for d in p.analysis_context.domains for t in p.technologies
                    if (d.id, t.id) not in state.get("searched_pairs", []))
        execution_status = ("completed" if not errors and not pending and review_succeeded
                            and state["selection_origin"] in {"model", "domain_operator"} else "partial")
        evidence_status = aggregate_evidence_status(p, coverage)
        status = "completed" if execution_status == "completed" and evidence_status == "direct_available" else "partial"
        return {"review": review, "rejected": bad, "status": status, "errors": _unique(errors),
                "gaps": _unique(gaps),
                "coverage": coverage, "execution_status": execution_status,
                "evidence_status": evidence_status, "review_succeeded": review_succeeded,
                "pending_source_ids": pending,
                "budget": state["budget"], "trace": state["trace"] + ["validate"]}

    def after_validation(state):
        if not state.get("draft") or state["round"] >= config.repair_limit:
            return "render"
        if state["budget"].remaining("llm") < 2:
            return "render"
        repair_claims = bool(state.get("rejected") or state.get("pending_source_ids"))
        search_possible = (web is not None and state["budget"].remaining("search")
                           and state["budget"].remaining("fetch") and state.get("review")
                           and state["review"].queries)
        return "research" if repair_claims or search_possible else "render"

    def render(state):
        current = {**state, "trace": state["trace"] + ["render"]}
        if state.get("output_format") == "json":
            return {"trace": current["trace"]}
        return {"output_md": render_output(current), "trace": current["trace"]}

    builder = StateGraph(AgentState)
    for name, node in [("prepare", prepare), ("plan", plan), ("research", research),
                       ("analyze", analyze), ("validate", validate), ("render", render)]:
        builder.add_node(name, node)
    builder.add_edge(START, "prepare")
    builder.add_conditional_edges("prepare", lambda s: "render" if s["status"] == "failed" else "plan")
    builder.add_conditional_edges("plan", lambda s: "render" if s["status"] == "failed" else "research")
    builder.add_edge("research", "analyze")
    builder.add_edge("analyze", "validate")
    builder.add_conditional_edges("validate", after_validation)
    builder.add_edge("render", END)
    return builder.compile()
