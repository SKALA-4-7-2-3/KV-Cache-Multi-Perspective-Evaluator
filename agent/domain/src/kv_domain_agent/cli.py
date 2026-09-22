"""Command-line runner for standalone verification and real LLM execution."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .agent import DomainEvaluator, create_openai_structured_model
from .adapters import adapt_paper_analyses
from .mock_model import DeterministicMockModel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the RAG-free domain agent")
    parser.add_argument("--input", required=True, type=Path, help="Graph state JSON")
    parser.add_argument("--output", required=True, type=Path, help="Output JSON")
    parser.add_argument(
        "--sw-analysis",
        type=Path,
        help="Unmodified RDKV paper_analysis JSON from the technical agent",
    )
    parser.add_argument(
        "--hw-analysis",
        type=Path,
        help="Unmodified Photonic-CXL paper_analysis JSON from the technical agent",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Validate wiring offline; output is not a real technology evaluation",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("DOMAIN_AGENT_MODEL", "gpt-4.1-mini"),
        help="LLM model for real mode",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if bool(args.sw_analysis) != bool(args.hw_analysis):
        parser.error("--sw-analysis and --hw-analysis must be supplied together")

    try:
        state = json.loads(args.input.read_text(encoding="utf-8"))
        if args.sw_analysis and args.hw_analysis:
            sw_analysis = json.loads(args.sw_analysis.read_text(encoding="utf-8"))
            hw_analysis = json.loads(args.hw_analysis.read_text(encoding="utf-8"))
            state = adapt_paper_analyses(
                state,
                sw_analysis=sw_analysis,
                hw_analysis=hw_analysis,
            )

        model = DeterministicMockModel() if args.mock else create_openai_structured_model(args.model)
        result = DomainEvaluator(model, allow_demo=args.mock).evaluate(state)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"status={result.status.value} output={args.output}")
        return 0 if result.status.value != "failed" else 2
    except Exception as exc:
        print(f"error={type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
