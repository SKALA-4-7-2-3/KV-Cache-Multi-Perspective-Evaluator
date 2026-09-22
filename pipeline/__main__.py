"""PDFs + natural-language request → saved/live RAG → four agents → report."""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time

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
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--as-of", default=datetime.now().date().isoformat())
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--draft", action="store_true", help="Render actual eight-cell results as an explicitly unreviewed draft")
    parser.add_argument("--rerun", nargs="*", default=[], choices=["domain", "stakeholders", "market", "review", "report"],
                        help="With --resume, rerun selected stages while keeping other successful results")
    parser.add_argument("--stop-after", choices=["prepare", "domain", "stakeholders", "market", "review", "report"], default="report")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(args.env_file, override=True)
    load_dotenv(ROOT / ".env", override=False)
    load_dotenv(ROOT / "agent/stakeholder/.env", override=False)
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
    reuse_live = bool(previous and rag_mode == "live" and previous.get("research_executed"))
    research_source = resolve_research(sources=pdfs, instruction=request["original_request"],
        output_dir=output / "rag",
        saved_path=Path(previous["research_source"]) if reuse_live else saved_research,
        run_rag=rag_mode == "live" and not reuse_live)
    from .research_input import load_saved_research, to_domain_state
    bundle = load_saved_research(research_source)
    identity = digest({"research": bundle["run"], "evidence": bundle["evidence"], "request": request,
                       "model": args.model, "as_of": args.as_of})
    if previous:
        if previous["input_sha256"] != identity:
            raise ValueError("Resume input/model differs; choose a new output directory")
        manifest = previous
    else:
        manifest = {"run_id": "integration-" + re.sub(r"[^A-Za-z0-9_-]", "-", output.name),
                    "input_sha256": identity, "model": args.model, "as_of": args.as_of,
                    "research_source": str(research_source), "research_executed": rag_mode == "live",
                    "pipeline_input": pipeline_input,
                    "mode": "live", "python": __import__("sys").version.split()[0], "stages": {}}
    save(output / "request.json", request)
    save(output / "pipeline.input.json", pipeline_input)
    save(output / "research.bundle.json", bundle)
    save(output / "research.context_manifest.json", bundle["context_manifest"])
    save(output / "papers.compat.json", bundle["papers"])
    save(manifest_path, manifest)
    print(f"prepare: RAG mode={rag_mode}; loaded research; output={output}", flush=True)
    if args.stop_after == "prepare":
        return 0
    for name in ["OPENAI_API_KEY", "TAVILY_API_KEY"]:
        if not os.environ.get(name):
            raise RuntimeError(f"Missing configuration: {name}")

    def stage(name, operation, *, stage_input=None, code_paths=()):
        target = output / f"{name}.output.json"
        code = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in code_paths for p in sorted(folder.rglob("*.py")) if ".venv" not in p.parts}
        wrapper = ROOT / "pipeline" / ({"review": "review_bridge.py", "report": "reporting.py"}.get(name, "runtime.py"))
        code[str(wrapper.relative_to(ROOT))] = hashlib.sha256(wrapper.read_bytes()).hexdigest()
        stamp = digest({"input": stage_input, "code": code})
        entry = manifest["stages"].get(name, {})
        if args.resume and name not in args.rerun and target.exists() and entry.get("status") == "finished" and entry.get("stage_sha256") == stamp:
            print(f"{name}: reusing saved output", flush=True)
            return json.loads(target.read_text())
        print(f"{name}: starting", flush=True)
        started = time.monotonic()
        manifest["stages"][name] = {"status": "running", "stage_sha256": stamp}
        save(manifest_path, manifest)
        try:
            result = operation()
            save(target, result)
            manifest["stages"][name].update(status="finished", seconds=round(time.monotonic() - started, 2))
            print(f"{name}: saved ({manifest['stages'][name]['seconds']}s)", flush=True)
            return result
        except Exception as exc:
            message = re.sub(r"(?:sk-|tvly-)[A-Za-z0-9_-]+", "[redacted]", str(exc))
            manifest["stages"][name].update(status="failed", error=f"{type(exc).__name__}: {message}")
            print(f"{name}: {type(exc).__name__}: {message}", flush=True)
            raise
        finally:
            save(manifest_path, manifest)

    from .runtime import run_domain, run_stakeholders, run_market
    results = {}
    domain_input = to_domain_state(bundle, request, run_id=manifest["run_id"], as_of=args.as_of)
    save(output / "domain.input.json", domain_input)
    results["domain"] = stage("domain", lambda: run_domain(domain_input, model=args.model),
                               stage_input=domain_input, code_paths=[ROOT / "agent/domain/src"])
    if args.stop_after == "domain": return 0
    results["stakeholders"] = stage("stakeholders", lambda: run_stakeholders(bundle["papers"], request,
        run_id=manifest["run_id"], as_of=args.as_of, model=args.model),
        stage_input=[bundle["papers"], request], code_paths=[ROOT / "agent/stakeholder/stakeholder_agent"])
    if args.stop_after == "stakeholders": return 0
    results["market"] = stage("market", lambda: run_market(bundle["papers"], request, as_of=args.as_of, model=args.model),
        stage_input=[bundle["papers"], request], code_paths=[ROOT / "agent/market/market_agent"])
    if args.stop_after == "market": return 0
    from .review_bridge import build_review_state, run_review
    review_input = build_review_state(bundle, request, results, run_id=manifest["run_id"], as_of=args.as_of)
    save(output / "review.input.json", review_input)
    review = stage("review", lambda: run_review(review_input, model=args.model, draft=args.draft),
        stage_input={"state": review_input, "draft": args.draft}, code_paths=[ROOT / "agent/review/team_review"])
    markdown = review["report_input_md"]
    (output / "review.output.md").write_text(markdown)
    if args.stop_after == "review": return 0
    from .reporting import generate_report
    artifacts = stage("report", lambda: generate_report(markdown, output, model=args.model,
        draft=args.draft, attribution_first=True),
        stage_input={"markdown": markdown, "draft": args.draft, "attribution_first": True},
        code_paths=[ROOT / "report/src"])
    manifest["status"] = "annotated_draft_generated"
    manifest["artifacts"] = artifacts
    save(manifest_path, manifest)
    print(f"report: {artifacts['pdf_path']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
