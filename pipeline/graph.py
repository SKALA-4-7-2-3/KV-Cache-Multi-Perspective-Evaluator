"""Orchestrator–Workers with persisted plans, terminal join and quality feedback.

The shared State contains controls and hash-checked references. Workers only emit
their own outcome. One aggregator writes accepted role results. Routing functions
read saved controls; they never call a model or a search tool.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import time

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from . import ROOT
from .artifacts import ArtifactStore, digest, fingerprint, stage_fingerprint
from .contracts import CATALOG, GraphState, TaskSpec, all_cells
from .governance import task_context


def _error(exc):
    return re.sub(r"(?:sk-|tvly-)[A-Za-z0-9_-]+", "[redacted]", f"{type(exc).__name__}: {exc}")[:2000]


@dataclass
class PipelineContext:
    output_dir: Path
    bundle: dict
    request: dict
    run_id: str
    as_of: str
    model: str
    draft: bool = False
    stop_after: str = "quality"
    worker: object = None
    planner: object = None
    review: object = None
    trl: object = None
    report: object = None
    quality: object = None
    max_replans: int = 2
    max_quality_attempts: int = 3
    max_judge_calls: int = 64
    report_model: str | None = None
    judge_model: str | None = None

    def __post_init__(self):
        self.output_dir = Path(self.output_dir).resolve()
        self.store = ArtifactStore(self.output_dir)
        self.code_hash = fingerprint(ROOT)
        self.input_hash = digest([self.bundle,self.request,self.model,self.as_of])

    def stage(self, name, inputs, operation, *, validate=None):
        stage_code_hash = stage_fingerprint(ROOT,name)
        stamp = digest([inputs,stage_code_hash,self.model,self.as_of])
        started = time.monotonic()
        print(f"{name}: starting",flush=True)
        with task_context(name):
            value,ref,reused = self.store.cached(name,stamp,operation,validate=validate)
        self.store.event("stage",name=name,reused=reused,seconds=round(time.monotonic()-started,3),
                         stage_code_sha256=stage_code_hash,output_ref=ref)
        print(f"{name}: {'reused' if reused else 'saved'}",flush=True)
        return value,ref


def initial_state(context, *, accepted_refs=None, pending_cells=None, revision=0):
    accepted_refs = dict(accepted_refs or {})
    for ref in accepted_refs.values(): context.store.get(ref)
    roles = ([context.stop_after] if context.stop_after in CATALOG else list(CATALOG))
    needed = all_cells([role for role in roles if role not in accepted_refs]) if pending_cells is None else pending_cells
    return {"run_id":context.run_id,
        "input_refs":{"bundle":context.store.put("research.bundle.json",context.bundle),
                      "request":context.store.put("request.json",context.request)},
        "plan_revision":revision,"tasks":[],"task_outcomes":{},"accepted_refs":accepted_refs,
        "pending_cells":needed,"feedback":[],"quality_attempt":0,"replan_count":0,
        "phase":"plan","termination_reason":None}


def quality_resume_state(context, state):
    """Rejudge the latest completed report without rebuilding an earlier revision."""
    resumed = dict(state)
    for name in ("review_ref", "review_input_ref", "report_ref"):
        if not resumed.get(name):
            raise ValueError(f"Quality-only resume has no latest {name}")
        context.store.get(resumed[name])
    report = context.store.get(resumed["report_ref"])
    for kind in ("pdf", "tex"):
        path = Path(report[f"{kind}_path"])
        if not path.exists() or sha256(path.read_bytes()).hexdigest() != report.get(f"{kind}_sha256"):
            raise ValueError("Final report artifact changed; rerun report and quality")
    resumed.update(run_id=context.run_id, phase="quality", termination_reason=None,
                   feedback=[], pending_cells=[])
    return resumed


def current_outcomes(state):
    result = {}
    for task in state.get("tasks",[]):
        matched = [o for o in state.get("task_outcomes",{}).values()
                   if o["task_id"] == task["task_id"] and o["plan_revision"] == task["plan_revision"]]
        result[task["task_id"]] = max(matched,key=lambda o:o["task_attempt"]) if matched else None
    return result


def dispatch(state):
    outcomes = current_outcomes(state)
    ready = [task for task in state["tasks"] if not outcomes[task["task_id"]] and all(
        outcomes.get(dep) and outcomes[dep]["status"] == "finished" for dep in task["dependency_ids"])]
    return [Send("worker",{"task":task,"accepted_refs":state["accepted_refs"]}) for task in ready] or "aggregate"


def after_aggregate(state):
    if state["phase"] in {"stopped","review_required"}: return END
    if state["phase"] == "dispatch": return "dispatch"
    if state["phase"] == "plan": return "plan"
    return "review"


def after_review(state):
    if state["phase"] in {"stopped","review_required"}: return END
    return "plan" if state["phase"] == "plan" else "report"


def after_report(state):
    return END if state["phase"] == "stopped" else "quality"


def quality_gate(state):
    if state["phase"] == "report_repair": return "report"
    if state["phase"] == "plan": return "plan"
    return END


def graph_entry(state):
    return "quality" if state.get("phase") == "quality" else "plan"


_ALIASES = {
    "market":{"ecosystem":["ecosystem_support","standardization"],"cost":["business_value"],"customer_value":["business_value"]},
    "domain":{"latency":["latency_predictability"],"hardware_dependency":["dedicated_hardware_dependency"],"deployment":["deployment_complexity"]},
}


def feedback_cells(requests):
    cells = set()
    for req in requests:
        role = req.get("role")
        if role not in CATALOG: continue
        techs = req.get("technology_ids") or ["SW-01","HW-01"]
        criteria = req.get("criterion_ids") or list(CATALOG[role])
        mapped = set()
        for criterion in criteria:
            if role == "stakeholders": mapped.add("stakeholder_impact")
            else: mapped.update(_ALIASES.get(role,{}).get(criterion,[criterion]))
        for tech in techs:
            for criterion in mapped:
                if tech in {"SW-01","HW-01"} and criterion in CATALOG[role]:
                    cells.add((role,tech,criterion))
    return [{"role":role,"technology_id":tech,"criterion_id":criterion} for role,tech,criterion in sorted(cells)]


def build_graph(context, checkpointer=None):
    ctx = context

    def plan(state):
        from .planner import create_plan
        revision = state["plan_revision"]+1
        planner = ctx.planner or create_plan
        tasks = planner(state["pending_cells"],run_id=ctx.run_id,revision=revision,model=ctx.model,
                        request=ctx.request,feedback=state.get("feedback",[]))
        tasks = [TaskSpec.model_validate(t).model_dump(mode="json") for t in tasks]
        expected = {(c["role"],c["technology_id"],c["criterion_id"]) for c in state["pending_cells"]}
        actual = [(t["role"],c["technology_id"],c["criterion_id"]) for t in tasks for c in t["active_cells"]]
        if set(actual) != expected or len(actual) != len(set(actual)):
            raise ValueError("Task plan must cover only and all eligible cells")
        ctx.store.put(f"plans/plan-{revision}.json",{"revision":revision,"tasks":tasks,"eligible_cells":state["pending_cells"]})
        ctx.store.event("plan_saved",revision=revision,roles=[t["role"] for t in tasks],scope=state["pending_cells"])
        return {"plan_revision":revision,"tasks":tasks,"phase":"dispatch"}

    def worker(state):
        from .worker_adapters import execute_worker
        task = TaskSpec.model_validate(state["task"]).model_dump(mode="json")
        prior_ref = state["accepted_refs"].get(task["role"])
        prior = ctx.store.get(prior_ref) if prior_ref else None
        stamp = digest([task,prior_ref,ctx.input_hash,ctx.code_hash])
        started = time.monotonic()
        ctx.store.event("worker_started",task_id=task["task_id"],role=task["role"],scope=task["active_cells"])
        for attempt in (1,2):
            try:
                with task_context(task["task_id"]):
                    value,ref,reused = ctx.store.cached(f"task-{task['task_id']}",stamp,lambda:(ctx.worker or execute_worker)(
                        task,ctx.bundle,ctx.request,run_id=ctx.run_id,as_of=ctx.as_of,model=ctx.model,prior=prior))
                domain_delta = value.get("assessments",{})
                nested_domain = domain_delta.get("domain",{}) if isinstance(domain_delta,dict) else {}
                failed = (value.get("execution_status") == "failed" or value.get("status") == "failed"
                    or value.get("result",{}).get("execution_status") == "failed" or nested_domain.get("status") == "failed")
                if failed: raise RuntimeError("Worker returned explicit failed execution; candidate preserved in task artifact")
                outcome = {"task_id":task["task_id"],"plan_revision":task["plan_revision"],"task_attempt":attempt,
                    "role":task["role"],"status":"finished","result_ref":ref,"reused":reused,
                    "seconds":round(time.monotonic()-started,3)}
                break
            except Exception as exc:
                retryable = type(exc).__name__ in {"TimeoutError","ConnectError","APITimeoutError","APIConnectionError","RateLimitError"}
                ctx.store.event("worker_attempt_failed",task_id=task["task_id"],attempt=attempt,error=_error(exc),retryable=retryable)
                if attempt == 1 and retryable: continue
                outcome = {"task_id":task["task_id"],"plan_revision":task["plan_revision"],"task_attempt":attempt,
                    "role":task["role"],"status":"failed","error":_error(exc),"retryable":retryable,
                    "seconds":round(time.monotonic()-started,3)}
                break
        ctx.store.put(f"tasks/{task['task_id']}.outcome.json",outcome)
        ctx.store.event("worker_terminal",**outcome)
        key = f"{task['plan_revision']}:{task['task_id']}:{outcome['task_attempt']}"
        return {"task_outcomes":{key:outcome}}

    def aggregate(state):
        from .worker_adapters import merge_role_result
        outcomes = current_outcomes(state)
        updates = {}
        for task in state["tasks"]:
            if outcomes[task["task_id"]]: continue
            failed_dep = [d for d in task["dependency_ids"] if outcomes.get(d) and outcomes[d]["status"] != "finished"]
            if failed_dep:
                outcome = {"task_id":task["task_id"],"plan_revision":task["plan_revision"],"task_attempt":1,
                    "role":task["role"],"status":"blocked_dependency","dependency_ids":failed_dep}
                updates[f"{task['plan_revision']}:{task['task_id']}:1"] = outcome
                outcomes[task["task_id"]] = outcome
                ctx.store.event("worker_terminal",**outcome)
        if any(value is None for value in outcomes.values()):
            if not any(not outcomes[t["task_id"]] and all(outcomes.get(d) and outcomes[d]["status"] == "finished"
                       for d in t["dependency_ids"]) for t in state["tasks"]):
                return {"task_outcomes":updates,"phase":"review_required","termination_reason":"dependency_deadlock"}
            return {"task_outcomes":updates,"phase":"dispatch"}
        accepted = dict(state["accepted_refs"])
        failures = []
        for task in state["tasks"]:
            outcome = outcomes[task["task_id"]]
            if outcome["status"] != "finished":
                failures.append(task)
                continue
            incoming = ctx.store.get(outcome["result_ref"])
            previous = ctx.store.get(accepted[task["role"]]) if task["role"] in accepted else None
            merged = merge_role_result(task["role"],previous,incoming,task["active_cells"])
            accepted[task["role"]] = ctx.store.put(f"accepted/{task['role']}-r{state['plan_revision']}.json",merged)
            ctx.store.put(f"{task['role']}.output.json",merged)
        ctx.store.event("join_complete",revision=state["plan_revision"],terminal_tasks=len(outcomes),failures=len(failures))
        if failures:
            if state["replan_count"] < ctx.max_replans:
                cells = [{"role":t["role"],**cell} for t in failures for cell in t["active_cells"]]
                return {"task_outcomes":updates,"accepted_refs":accepted,"pending_cells":cells,
                    "feedback":[{"role":t["role"],"instructions":"Prior task failed; repair the recorded execution error within this scope."} for t in failures],
                    "replan_count":state["replan_count"]+1,"phase":"plan"}
            return {"task_outcomes":updates,"accepted_refs":accepted,"phase":"review_required","termination_reason":"worker_failure_limit"}
        return {"task_outcomes":updates,"accepted_refs":accepted,
                "phase":"stopped" if ctx.stop_after in CATALOG else "review"}

    def review(state):
        from .review_bridge import build_review_state,run_review
        from .trl import generate_trl_assessment
        results = {role:ctx.store.get(ref) for role,ref in state["accepted_refs"].items()}
        rev_input = build_review_state(ctx.bundle,ctx.request,results,run_id=ctx.run_id,as_of=ctx.as_of)
        technical_feedback = [r["instructions"] for r in state.get("feedback",[]) if r.get("role") == "technical"]
        if technical_feedback: rev_input["config"]["trl_feedback"] = technical_feedback
        def draft_trl():
            if ctx.trl:
                return ctx.trl(rev_input,model=ctx.model)
            return generate_trl_assessment(rev_input,model=ctx.model,
                cache_dir=ctx.output_dir/"trl-drafts")
        rev_input["assessments"]["technical"],trl_ref = ctx.stage("trl",rev_input,draft_trl)
        ctx.store.put("trl.output.json",rev_input["assessments"]["technical"])
        rev_input["review"]["round"] = min(1,state["replan_count"])
        input_ref = ctx.store.put("review.input.json",rev_input)
        if ctx.stop_after == "trl": return {"review_input_ref":input_ref,"phase":"stopped"}
        result,ref = ctx.stage("review",[rev_input,ctx.draft],lambda:(ctx.review or run_review)(rev_input,model=ctx.model,draft=ctx.draft))
        ctx.store.put("review.output.json",result)
        (ctx.output_dir/"review.output.md").write_text(result["report_input_md"],encoding="utf-8")
        requests = [{"target":"upstream","role":i["role"],
                     "technology_ids":[i["technology_id"]] if i.get("technology_id") else [],
                     "criterion_ids":[i["criterion_id"]] if i.get("criterion_id") else [],"instructions":i["message"]}
                    for i in result.get("review",{}).get("checks",[]) if i.get("repairable") and i.get("role")]
        if result.get("review",{}).get("next") == "repair":
            cells = feedback_cells(requests)
            if state["replan_count"] < ctx.max_replans and (cells or any(r["role"] == "technical" for r in requests)):
                return {"review_ref":ref,"review_input_ref":input_ref,"pending_cells":cells,"feedback":requests,
                    "replan_count":state["replan_count"]+1,"phase":"plan"}
            return {"review_ref":ref,"review_input_ref":input_ref,"phase":"review_required","termination_reason":"review_not_ready"}
        return {"review_ref":ref,"review_input_ref":input_ref,"phase":"stopped" if ctx.stop_after == "review" else "report"}

    def report(state):
        from .reporting import generate_report
        review_result = ctx.store.get(state["review_ref"])
        markdown = review_result["report_input_md"]
        prior = ctx.store.get(state["report_ref"]) if state.get("report_ref") else None
        requests = state.get("feedback",[]) if state["phase"] == "report_repair" else []
        report_dir = ctx.output_dir/"reports"/f"revision-{state['quality_attempt']+1}"
        def operation():
            options = {"model":ctx.report_model or ctx.model,"draft":ctx.draft,"attribution_first":True}
            if requests:
                options.update(revision_feedback=[r["instructions"] for r in requests],
                    revision_candidate=Path(prior["tex_path"]).read_text(),source_coverage_repair=False)
            value = (ctx.report or generate_report)(markdown,report_dir,**options)
            for kind in ("tex","pdf"):
                path = Path(value[f"{kind}_path"])
                if path.exists(): value[f"{kind}_sha256"] = sha256(path.read_bytes()).hexdigest()
            return value
        def valid(value):
            return all(Path(value[f"{kind}_path"]).exists() and sha256(Path(value[f"{kind}_path"]).read_bytes()).hexdigest() == value.get(f"{kind}_sha256") for kind in ("tex","pdf"))
        value,ref = ctx.stage(f"report-{state['quality_attempt']+1}",[markdown,requests,prior if requests else None,ctx.report_model],operation,validate=valid)
        ctx.store.put("report.output.json",value)
        return {"report_ref":ref,"phase":"stopped" if ctx.stop_after == "report" else "quality"}

    def quality(state):
        from .report_quality import evaluate_report
        report_result = ctx.store.get(state["report_ref"])
        review_result = ctx.store.get(state["review_ref"])
        rev_input = ctx.store.get(state["review_input_ref"])
        rev_input["synthesis"] = review_result.get("synthesis",{})
        attempt = state["quality_attempt"]+1
        judge_model = ctx.judge_model or ctx.model
        result,ref = ctx.stage(f"quality-{attempt}",[state["report_ref"],state["review_ref"],state["review_input_ref"],judge_model,ctx.max_judge_calls],
            lambda:(ctx.quality or evaluate_report)(tex_path=report_result["tex_path"],pdf_path=report_result["pdf_path"],
                review_input=rev_input,report_markdown=review_result["report_input_md"],model=judge_model,
                output_dir=ctx.output_dir/"quality"/f"attempt-{attempt}",attempt=attempt,
                max_judge_calls=ctx.max_judge_calls))
        ctx.store.put("quality.json",result)
        route = result["route"]
        phase,reason = "review_required",result.get("failure_type") or "quality_not_passed"
        requests = result.get("repair_requests",[])
        if route == "passed": phase,reason = "content_quality_pass",None
        elif attempt >= ctx.max_quality_attempts: phase,reason = "failed_quality","quality_attempt_limit"
        elif route == "report_repair": phase,reason = "report_repair",None
        elif route == "upstream_replan" and state["replan_count"] < ctx.max_replans:
            cells = feedback_cells(requests)
            if cells or any(r.get("role") == "technical" for r in requests): phase,reason = "plan",None
        ctx.store.event("quality_route",attempt=attempt,route=route,phase=phase)
        return {"quality_ref":ref,"quality_attempt":attempt,"feedback":requests,
            "pending_cells":feedback_cells(requests) if phase == "plan" else [],
            "replan_count":state["replan_count"]+(1 if phase == "plan" else 0),"phase":phase,"termination_reason":reason}

    graph = StateGraph(GraphState)
    for name,action in (("plan",plan),("dispatch",lambda state:{}),("worker",worker),("aggregate",aggregate),
                        ("review",review),("report",report),("quality",quality)):
        graph.add_node(name,action)
    graph.add_conditional_edges(START,graph_entry,["plan","quality"])
    graph.add_edge("plan","dispatch")
    graph.add_conditional_edges("dispatch",dispatch,["worker","aggregate"])
    graph.add_edge("worker","aggregate")
    graph.add_conditional_edges("aggregate",after_aggregate,["dispatch","plan","review",END])
    graph.add_conditional_edges("review",after_review,["plan","report",END])
    graph.add_conditional_edges("report",after_report,["quality",END])
    graph.add_conditional_edges("quality",quality_gate,["report","plan",END])
    return graph.compile(checkpointer=checkpointer)
