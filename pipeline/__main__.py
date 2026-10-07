"""PDFs + request → saved/live RAG → scoped workers → reviewed report quality."""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

from . import ROOT


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="PDFs + request → RAG (saved by default) → agents → report")
    parser.add_argument("--input", type=Path, default=ROOT / "config/pipeline.json", help="PDFs, request and RAG mode")
    parser.add_argument("--instruction", help="Override the natural-language report request")
    parser.add_argument("--pdf", type=Path, action="append", help="PDF input; repeat for both papers")
    parser.add_argument("--run-rag", action="store_true", help="Explicitly run slow RAG from PDFs instead of reusing saved output")
    parser.add_argument("--research", type=Path, help="Override the saved RAG output directory")
    parser.add_argument("--request", type=Path, help="Use an existing structured request JSON")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/integration" / datetime.now().strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--model", help="API default: gpt-4.1-mini; Codex default: saved CLI model")
    parser.add_argument("--model-provider", choices=["openai_api", "codex_cli_chatgpt"],
                        help="Use OpenAI API or the locally authenticated Codex CLI")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--as-of", default=datetime.now().date().isoformat())
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--extend-budget", action="store_true", help="With --resume, explicitly raise saved limits without resetting usage")
    parser.add_argument("--draft", action="store_true", help="Render actual eight-cell results as an explicitly unreviewed draft")
    parser.add_argument("--rerun", nargs="*", default=[], choices=["domain", "stakeholders", "market", "trl", "review", "report", "quality"],
                        help="With --resume, rerun selected stages while keeping other successful results")
    parser.add_argument("--stop-after", choices=["prepare", "domain", "stakeholders", "market", "trl", "review", "report", "quality"], default="quality")
    parser.add_argument("--report-model", help="Report writing model; defaults to --model")
    parser.add_argument("--judge-model", help="Independent report Quality model; defaults to --model")
    parser.add_argument("--max-judge-calls", type=int, default=64, help="Quality HTTP call ceiling per attempt, within the global model limit")
    parser.add_argument("--max-quality-attempts", type=int, default=3,
                        help="Completed Quality assessment ceiling; use 1 to stop after one final assessment")
    parser.add_argument("--max-tokens", type=int, default=5_000_000, help="Post-RAG actual+unconfirmed+reserved token ceiling")
    parser.add_argument("--max-model-calls", type=int, default=160, help="Post-RAG model HTTP attempt limit")
    parser.add_argument("--max-search-calls", type=int, default=24, help="Post-RAG web search HTTP attempt limit")
    parser.add_argument("--max-extract-calls", type=int, default=48, help="Post-RAG web extraction HTTP attempt limit")
    parser.add_argument("--max-fetch-calls", type=int, default=48, help="Post-RAG other HTTP attempt limit")
    parser.add_argument("--max-seconds", type=int, default=1800, help="Post-RAG elapsed-time admission and HTTP timeout limit")
    args = parser.parse_args()
    if args.extend_budget and not args.resume:
        parser.error("--extend-budget requires --resume")
    if args.max_quality_attempts < 1:
        parser.error("--max-quality-attempts must be positive")
    from dotenv import load_dotenv
    load_dotenv(args.env_file, override=True)
    load_dotenv(ROOT / ".env", override=False)
    load_dotenv(ROOT / "agent/stakeholder/.env", override=False)
    if args.model_provider:
        os.environ["KV_MODEL_PROVIDER"] = args.model_provider
    from .governance import model_provider
    provider = model_provider()
    if args.model is None:
        args.model = "codex-default" if provider == "codex_cli_chatgpt" else "gpt-4.1-mini"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    from .inputs import load_inputs
    from rag.runner import resolve_research
    request, pdfs, saved_research, rag_mode = load_inputs(args.input,
        instruction=args.instruction, pdfs=args.pdf, request_path=args.request,
        research_path=args.research, run_rag=args.run_rag)
    pipeline_input = {"pdfs": [str(path) for path in pdfs],
        "instruction": request["original_request"], "rag_mode": rag_mode,
        "saved_research": str(saved_research),
        "source_note": ("RAG를 재실행하지 않고 기존 두 논문 분석을 재사용합니다. 현재 자연어 요청은 하위 평가·종합·보고서에 적용합니다."
                        if rag_mode == "saved" else "입력 PDF와 현재 자연어 요청으로 RAG를 실행합니다.")}
    manifest_path = output / "run.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if previous and not args.resume:
        raise ValueError("Output already exists; use --resume or a new --output directory")
    if previous and json.loads((output / "request.json").read_text()) != request:
        raise ValueError("Resume request differs; choose a new output directory")
    if previous and previous.get("pipeline_input") and any(
        previous["pipeline_input"].get(key) != pipeline_input[key] for key in ("pdfs", "rag_mode")
    ):
        raise ValueError("Resume PDF inputs or RAG mode differs; choose a new output directory")
    # Persist the run identity before an optional live RAG can send a request.
    prepared_request_hash = digest({"request":request,"input":pipeline_input,
        "pdf_hashes":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in pdfs if p.is_file()}})
    if previous and previous.get("prepared_request_sha256") not in {None,prepared_request_hash}:
        raise ValueError("Resume source bytes or request differs; choose a new output directory")
    if previous is None:
        from uuid import uuid4
        save(manifest_path,{"run_id":"integration-"+uuid4().hex[:16],"status":"preparing",
             "prepared_request_sha256":prepared_request_hash,"pipeline_input":pipeline_input})
        save(output/"request.json",request)
    reuse_live = bool(previous and rag_mode == "live" and previous.get("research_executed"))
    preparing_run = json.loads(manifest_path.read_text())
    research_source = resolve_research(sources=pdfs, instruction=request["original_request"],
        output_dir=output / "rag",
        saved_path=Path(previous["research_source"]) if reuse_live else saved_research,
        run_rag=rag_mode == "live" and not reuse_live, job_id=preparing_run["run_id"]+"-rag")
    from .research_input import load_saved_research
    bundle = load_saved_research(research_source)
    identity_data = {"research": bundle["run"], "evidence": bundle["evidence"], "request": request,
                     "model": args.model, "as_of": args.as_of}
    if provider != "openai_api":
        identity_data["model_provider"] = provider
    identity = digest(identity_data)
    if previous and previous.get("input_sha256"):
        if previous["input_sha256"] != identity:
            raise ValueError("Resume input/model differs; choose a new output directory")
        manifest = previous
    else:
        manifest = {"run_id": preparing_run["run_id"], "prepared_request_sha256":prepared_request_hash,
                    "input_sha256": identity, "model": args.model, "as_of": args.as_of,
                    "research_source": str(research_source), "research_executed": rag_mode == "live",
                    "pipeline_input": pipeline_input,
                    "mode": "live", "python": __import__("sys").version.split()[0], "stages": {}}
    save(output / "request.json", request)
    save(output / "pipeline.input.json", pipeline_input)
    save(output / "research.bundle.json", bundle)
    save(output / "research.context_manifest.json", bundle["context_manifest"])
    save(output / "papers.compat.json", bundle["papers"])
    manifest["model_provider"] = provider
    save(manifest_path, manifest)
    print(f"prepare: RAG mode={rag_mode}; loaded research; output={output}", flush=True)
    if args.stop_after == "prepare":
        return 0
    for name in (["OPENAI_API_KEY", "TAVILY_API_KEY"] if provider == "openai_api" else ["TAVILY_API_KEY"]):
        if not os.environ.get(name):
            raise RuntimeError(f"Missing configuration: {name}")

    from .governance import BudgetLedger, configure
    from .graph import PipelineContext, build_graph, initial_state, quality_resume_state
    from .checkpoint import SQLiteCheckpoint
    ledger = BudgetLedger(output, limits={"tokens":args.max_tokens,"llm":args.max_model_calls,
        "search":args.max_search_calls,"extract":args.max_extract_calls,"fetch":args.max_fetch_calls,
        "seconds":args.max_seconds},allow_budget_increase=args.extend_budget)
    configure(ledger)
    context = PipelineContext(output,bundle,request,manifest["run_id"],args.as_of,args.model,
        draft=args.draft,stop_after=args.stop_after,report_model=args.report_model,
        judge_model=args.judge_model,max_judge_calls=args.max_judge_calls,
        max_quality_attempts=args.max_quality_attempts)
    report_settings = {"model":args.report_model or args.model,"draft":args.draft}
    old_settings = manifest.get("report_settings",report_settings)
    if old_settings["model"] != report_settings["model"]: args.rerun.append("report")
    if old_settings["draft"] != report_settings["draft"]: args.rerun.append("review")
    manifest["report_settings"] = report_settings
    quality_settings = {"model": args.judge_model or args.model, "max_judge_calls": args.max_judge_calls}
    old_quality_settings = manifest.get("quality_settings", {"model": args.model, "max_judge_calls": 64})
    if old_quality_settings != quality_settings:
        args.rerun.append("quality")
    manifest["quality_settings"] = quality_settings
    manifest["quality_attempt_limit"] = args.max_quality_attempts
    order = ["trl","review","report","quality"]
    invalidated = set()
    for name in args.rerun:
        if name in order: invalidated.update(order[order.index(name):])
    context.store.invalidate(invalidated)
    checkpoint = SQLiteCheckpoint(output / "checkpoint.sqlite")
    graph = build_graph(context,checkpoint)
    configuration = {"configurable":{"thread_id":manifest["run_id"]},"max_concurrency":3,
        "recursion_limit":128,"run_name":"KV-Cache Orchestrator–Workers",
        "tags":["kv-cache","orchestrator-workers"],"metadata":{
            "evaluation_run_id":manifest["run_id"],"input_sha256":identity,"code_sha256":context.code_hash,
            "model_provider": provider,
            "judge_model":args.judge_model or args.model,"report_model":args.report_model or args.model}}
    snapshot = graph.get_state(configuration)
    old_code = manifest.get("orchestration_code_sha256")
    from .artifacts import role_fingerprints, stage_fingerprint
    role_hashes = role_fingerprints(ROOT)
    old_role_hashes = manifest.get("role_code_sha256",{})
    stage_hashes = {name: stage_fingerprint(ROOT,name) for name in ("trl","review","report","quality")}
    old_stage_hashes = manifest.get("stage_code_sha256",{})
    manifest["orchestration_code_sha256"] = context.code_hash
    manifest["role_code_sha256"] = role_hashes
    manifest["engine"] = "orchestrator-workers"
    manifest["status"] = "running"
    manifest["budget_limits"] = ledger.limits
    manifest["budget_scope"] = "Downstream API calls after saved/live RAG loading; live RAG subprocess excluded"
    manifest["quality_call_limit_per_attempt"] = args.max_judge_calls
    save(manifest_path,manifest)
    if previous and args.resume and snapshot.values and old_code == context.code_hash and not args.rerun:
        if snapshot.next:
            invocation = None
        else:
            # Hash-check every accepted output and the final files before reuse.
            for ref in snapshot.values.get("accepted_refs",{}).values(): context.store.get(ref)
            saved_report = snapshot.values.get("report_ref")
            if saved_report:
                from hashlib import sha256
                saved_report = context.store.get(saved_report)
                for kind in ("pdf","tex"):
                    path = Path(saved_report[f"{kind}_path"])
                    if not path.exists() or sha256(path.read_bytes()).hexdigest() != saved_report.get(f"{kind}_sha256"):
                        raise ValueError("Final report artifact changed; rerun report and quality")
            if snapshot.values.get("phase") == "stopped" and args.stop_after != previous.get("stop_after"):
                invocation = initial_state(context,accepted_refs=snapshot.values.get("accepted_refs"),
                                           revision=snapshot.values.get("plan_revision",0))
            else:
                invocation = "complete"
    else:
        prior_refs = {role:ref for role,ref in snapshot.values.get("accepted_refs",{}).items()
            if old_code == context.code_hash or old_role_hashes.get(role) == role_hashes.get(role)}
        from .contracts import CATALOG, all_cells
        selected = [r for r in args.rerun if r in CATALOG]
        pending = all_cells(selected) if selected else None
        quality_only = (previous and args.resume and not snapshot.next and args.stop_after == "quality"
            and set(args.rerun) == {"quality"}
            and prior_refs == snapshot.values.get("accepted_refs",{})
            and all(old_stage_hashes.get(name) == stage_hashes[name] for name in ("trl","review","report")))
        pending_report_repair = (previous and args.resume and not args.rerun
            and snapshot.next == ("report",) and snapshot.values.get("phase") == "report_repair"
            and prior_refs == snapshot.values.get("accepted_refs",{})
            and all(old_stage_hashes.get(name) == stage_hashes[name] for name in ("trl","review"))
            and old_stage_hashes.get("report") is not None
            and old_stage_hashes["report"] != stage_hashes["report"])
        if pending_report_repair:
            # Verify the prior files using the same contract, but keep the
            # checkpoint's repair feedback and counters instead of rejudging.
            quality_resume_state(context,snapshot.values)
            context.store.get(snapshot.values["quality_ref"])
            invocation = None
        else:
            invocation = (quality_resume_state(context,snapshot.values) if quality_only else
                initial_state(context,accepted_refs=prior_refs,pending_cells=pending,
                              revision=snapshot.values.get("plan_revision",0)))
    try:
        result = snapshot.values if invocation == "complete" else graph.invoke(invocation,configuration)
        context.store.put("state.final.json",result)
        completed_stage_hashes = dict(old_stage_hashes)
        if result.get("review_ref") and result.get("review_input_ref"):
            completed_stage_hashes.update(trl=stage_hashes["trl"],review=stage_hashes["review"])
        if result.get("report_ref"):
            completed_stage_hashes["report"] = stage_hashes["report"]
        if result.get("quality_ref"):
            completed_stage_hashes["quality"] = stage_hashes["quality"]
        manifest["stage_code_sha256"] = completed_stage_hashes
        manifest.update(status=result["phase"],termination_reason=result.get("termination_reason"),
            state_ref=context.store.put("state.result.json",result),stop_after=args.stop_after)
        if result.get("report_ref"):
            manifest["artifacts"] = context.store.get(result["report_ref"])
            print(f"report: {manifest['artifacts']['pdf_path']}",flush=True)
        if result.get("quality_ref"):
            manifest["quality"] = context.store.get(result["quality_ref"])
            print(f"quality: {result['phase']}",flush=True)
        return 0 if result["phase"] in {"stopped","content_quality_pass"} else 2
    except Exception as exc:
        from .graph import _error
        manifest.update(status="execution_failed",error=_error(exc))
        raise
    finally:
        manifest["usage"] = ledger.snapshot()
        save(manifest_path,manifest)
        configure(None)
        checkpoint.close()


if __name__ == "__main__":
    raise SystemExit(main())
