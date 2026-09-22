"""Resumeable, sequential saved-research to report execution."""

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
    parser = argparse.ArgumentParser(description="Saved Research → evaluation → report (live APIs)")
    parser.add_argument("--research", type=Path, default=ROOT / "examples/results/technical-bge-e2e-two-papers")
    parser.add_argument("--request", type=Path, default=ROOT / "stakeholder-agent/examples/request.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/integration" / datetime.now().strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--env-file", type=Path, default=ROOT / "stakeholder-agent/.env")
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
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    request = json.loads(args.request.read_text())
    from .research_input import load_saved_research, to_domain_state
    bundle = load_saved_research(args.research.resolve())
    identity = digest({"research": bundle["run"], "evidence": bundle["evidence"], "request": request,
                       "model": args.model, "as_of": args.as_of})
    manifest_path = output / "run.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if not args.resume:
            raise ValueError("Output already exists; use --resume or a new --output directory")
        if previous["input_sha256"] != identity:
            raise ValueError("Resume input/model differs; choose a new output directory")
        manifest = previous
    else:
        manifest = {"run_id": "integration-" + re.sub(r"[^A-Za-z0-9_-]", "-", output.name),
                    "input_sha256": identity, "model": args.model, "as_of": args.as_of,
                    "research_source": str(args.research.resolve()), "research_executed": False,
                    "mode": "live", "python": __import__("sys").version.split()[0], "stages": {}}
    save(output / "request.json", request)
    save(output / "research.bundle.json", bundle)
    save(output / "research.context_manifest.json", bundle["context_manifest"])
    save(output / "papers.compat.json", bundle["papers"])
    save(manifest_path, manifest)
    print(f"prepare: loaded saved research; output={output}", flush=True)
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
                               stage_input=domain_input, code_paths=[ROOT / "domain-agent/src"])
    if args.stop_after == "domain": return 0
    results["stakeholders"] = stage("stakeholders", lambda: run_stakeholders(bundle["papers"], request,
        run_id=manifest["run_id"], as_of=args.as_of, model=args.model),
        stage_input=[bundle["papers"], request], code_paths=[ROOT / "stakeholder-agent/stakeholder_agent"])
    if args.stop_after == "stakeholders": return 0
    results["market"] = stage("market", lambda: run_market(bundle["papers"], request, as_of=args.as_of, model=args.model),
        stage_input=[bundle["papers"], request], code_paths=[ROOT / "market-research-agent/market_agent"])
    if args.stop_after == "market": return 0
    from .review_bridge import build_review_state, run_review
    review_input = build_review_state(bundle, request, results, run_id=manifest["run_id"], as_of=args.as_of)
    save(output / "review.input.json", review_input)
    review = stage("review", lambda: run_review(review_input, model=args.model, draft=args.draft),
        stage_input={"state": review_input, "draft": args.draft}, code_paths=[ROOT / "review-agent/team_review"])
    markdown = review["report_input_md"]
    (output / "review.output.md").write_text(markdown)
    if args.stop_after == "review": return 0
    from .reporting import generate_report
    artifacts = stage("report", lambda: generate_report(markdown, output, model=args.model, draft=args.draft),
        stage_input={"markdown": markdown, "draft": args.draft}, code_paths=[ROOT / "report-agent/src"])
    manifest["status"] = "draft_report_generated" if args.draft else "report_generated"
    manifest["artifacts"] = artifacts
    save(manifest_path, manifest)
    print(f"report: {artifacts['pdf_path']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
