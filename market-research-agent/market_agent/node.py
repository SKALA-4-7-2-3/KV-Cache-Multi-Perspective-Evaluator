"""시장 역할의 LangGraph와 부모 그래프에 전달할 변경분."""

import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .schemas import Analysis, CRITERIA, MarketInput, MarketResult, unknown
from .tools import Budget, ProviderError
from .collection import collect_sources
from .search_plan import initial_questions, repair_questions
from .research import annotate
from .validation import validate_analysis


class RunState(TypedDict):
    data: MarketInput
    round: int
    evidence: dict
    sources: dict
    analysis: Analysis
    last_validated: Analysis
    errors: list
    validation_errors: list
    history: list[str]
    queries: list[dict]
    fatal: bool
    model_successes: int
    result: MarketResult


def relevant_candidate(row, tech):
    """일반 제품 문서를 걸러내는 최소 검사. 사실성·동일 기술 여부는 별도 평가한다."""
    text = f"{row.get('title', '')} {row.get('content', '')}"
    # RDKV는 TV/셋톱박스 플랫폼에서도 쓰는 약어다. 이름 일치만으로 채택하지 않는다.
    if tech.approach == 'SW' and re.search(r'\brdkv\b|rdk.video', text, re.I):
        return bool(re.search(r'kv[\s_-]*cache|rate.distortion|\bllm\b|language model|quantization|attention', text, re.I))
    return bool(re.search(r"kv[\s_-]*cache|key[\s_-]*value[\s_-]*cache|\bcxl\b|compute express link|"
        r"photonic.{0,30}memory|llm.{0,30}(memory|inference)|ai[\s_-]+(server|infrastructure|accelerator)|"
        r"추론.{0,15}(메모리|인프라)|인공지능.{0,10}서버", text, re.I))


def run_market(data, web, analyst, *, mode="live", budget=None, auto_repair=True,
               round_number=0, previous=None, existing_evidence=None):
    if round_number not in {0, 1}:
        raise ValueError("round_number must be 0 or 1")
    budget = budget or Budget(data.limits)
    budget.constrain(data.limits)
    initial_evidence = {k: e.model_copy(deep=True) for k, e in {**data.evidence, **(existing_evidence or {})}.items()}
    empty = Analysis(assessments=[unknown(t, c, "미확인: 아직 시장 근거가 없습니다")
        for t in data.technologies for c in CRITERIA], followup_questions=initial_questions(data))

    def collect(state):
        questions = initial_questions(data) if state["round"] == 0 else repair_questions(
            data, state["analysis"].assessments, state["analysis"].followup_questions, state["queries"])
        update = collect_sources(state, data, web, budget, questions, relevant_candidate)
        update["analysis"] = annotate(state["analysis"], data, update["evidence"], update["queries"],
            update["errors"], budget, False)
        return update

    def assess(state):
        update = {"history": state["history"] + ["assess"]}
        if state["fatal"] or not budget.remaining("llm") or not any(e.access_status == "full_text" for e in state["evidence"].values()):
            return update
        try:
            analysis = budget.call("llm", lambda: Analysis.model_validate(analyst.analyze(data, state["evidence"],
                state["analysis"] if state['model_successes'] else None,
                state["validation_errors"] + [{'stage': 'research', 'rows': [
                    {'tech_id': r.tech_id, 'criterion_id': r.criterion_id, 'research_status': r.research_status,
                        'unknown_reasons': r.unknown_reasons, 'search_ids': r.search_ids}
                    for r in state['analysis'].assessments]}])))
            update.update(analysis=analysis, model_successes=state["model_successes"] + 1,
                errors=[e for e in state["errors"] if e["stage"] != "llm"])
        except ProviderError as exc:
            update.update(errors=state["errors"] + [{"stage": "llm", "code": exc.code}], fatal=exc.fatal)
        return update

    def validate(state):
        analysis, errors = validate_analysis(data, state["analysis"], state["evidence"])
        prior = {(r.tech_id, r.criterion_id): r for r in state.get("last_validated", analysis).assessments}
        retained = set()
        for index, row in enumerate(analysis.assessments):
            old = prior.get((row.tech_id, row.criterion_id))
            if (old and old.basis != 'unknown' and row.basis == 'unknown'
                    and 'conflicting_sources' not in row.unknown_reasons):
                analysis.assessments[index] = old.model_copy(deep=True)
                retained.add((row.tech_id, row.criterion_id))
        errors = [e for e in errors if (e.get('tech_id'), e.get('criterion_id')) not in retained]
        current = [e for e in state["errors"] if e["stage"] != "validate"] + errors
        analysis = annotate(analysis, data, state["evidence"], state["queries"], current, budget, state["model_successes"] > 0)
        if errors and not analysis.followup_questions:
            analysis = analysis.model_copy(update={"followup_questions": repair_questions(data, analysis.assessments, [], state["queries"])})
        return {"analysis": analysis, "last_validated": analysis, "validation_errors": errors, "errors": current,
            "history": state["history"] + ["validate"]}

    def route(state):
        needs_more = state["analysis"].followup_questions or state["validation_errors"] or any(r.verdict == "unknown" for r in state["analysis"].assessments)
        can_work = budget.remaining("llm") and (budget.remaining("search") or budget.remaining("extract") or state["validation_errors"])
        return "repair" if auto_repair and state["round"] == 0 and needs_more and can_work and not state["fatal"] else "finish"

    def repair(state):
        return {"round": state["round"] + 1, "history": state["history"] + ["repair"]}

    def finish(state):
        statuses = {t: "completed" if all(a.verdict != "unknown" for a in state["analysis"].assessments if a.tech_id == t)
            else "unknown" for t in data.technologies}
        failed = state["fatal"] or (state["model_successes"] == 0 and any(
            e["stage"] in {"llm", "search", "extract"} and not e['code'].startswith('budget_') for e in state["errors"]))
        status = "failed" if failed else ("completed" if all(s == "completed" for s in statuses.values()) else "unknown")
        result = MarketResult(status=status, round=state["round"], assessments=state["analysis"].assessments,
            followup_questions=state["analysis"].followup_questions, technology_status=statuses,
            errors=state["errors"], usage=dict(budget.used), mode=mode)
        return {"result": result, "history": state["history"] + ["finish"]}

    graph = StateGraph(RunState)
    for name, action in [("collect", collect), ("assess", assess), ("validate", validate), ("repair", repair), ("finish", finish)]:
        graph.add_node(name, action)
    graph.add_edge(START, "collect")
    graph.add_edge("collect", "assess")
    graph.add_edge("assess", "validate")
    graph.add_conditional_edges("validate", route, {"repair": "repair", "finish": "finish"})
    graph.add_edge("repair", "collect")
    graph.add_edge("finish", END)
    state = graph.compile().invoke({"data": data, "round": round_number, "evidence": initial_evidence,
        "sources": {}, "analysis": previous or empty, "errors": [], "validation_errors": [], "queries": [],
        "history": [], "fatal": False, "model_successes": 0}, config={"recursion_limit": 20})
    state["events"] = list(budget.events)
    state["initial_evidence_ids"] = list(initial_evidence)
    state["model"] = getattr(analyst, "model", "injected")
    state["token_usage"] = list(getattr(analyst, "usage", []))
    state['output_checks'] = list(getattr(analyst, 'output_checks', []))
    state['debug_analyses'] = list(getattr(analyst, 'debug_analyses', []))
    return state


def parent_update(state):
    evidence = {eid: e.model_dump(mode="json") for eid, e in state["evidence"].items() if eid not in state["initial_evidence_ids"]}
    documents = {e["doc_id"]: {"url": e["url"], "title": e["title"], "content_hash": e["content_hash"],
        "retrieved_at": e["retrieved_at"], "page_count": None} for e in evidence.values()}
    result = state["result"].model_dump(mode="json")
    return {"assessments": {"market": result}, "documents": documents, "evidence": evidence,
        "errors": {f'market-{result["round"]}-{i}': error for i, error in enumerate(result["errors"])}}
