from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .compiler import LatexCompileError
from .generator import GenerationError, ReportAgent
from .parser import InputContractError, parse_report_input
from .prompt import build_generation_prompt


def _read_source(path: str) -> str:
    if path == "-":
        if sys.stdin.isatty():
            print("review.output.md 전체를 붙여넣고 Ctrl-D를 누르세요.", file=sys.stderr)
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _write_text(path: str, content: str) -> None:
    if path == "-":
        sys.stdout.write(content)
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "review.output.md를 Overleaf 호환 한국어 LaTeX와 최종 PDF 보고서로 변환합니다."
        )
    )
    parser.add_argument("--input", default="-", help="입력 MD 경로. '-'는 stdin")
    parser.add_argument(
        "--output",
        dest="tex_output",
        default="output/tex/kv-cache-technology-evaluation-report.tex",
        help="Overleaf에 업로드할 .tex 경로",
    )
    parser.add_argument(
        "--pdf-output",
        default="output/pdf/kv-cache-technology-evaluation-report.pdf",
        help="컴파일된 최종 .pdf 경로",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        help="OpenAI model ID",
    )
    parser.add_argument("--repair-attempts", type=int, default=1)
    parser.add_argument("--max-output-tokens", type=int, default=12_000)
    parser.add_argument(
        "--prompt-only",
        metavar="PATH",
        help="API를 호출하지 않고 생성 prompt를 PATH에 저장. '-'는 stdout",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        source = _read_source(args.input)
        if args.prompt_only:
            parsed = parse_report_input(source)
            _write_text(args.prompt_only, build_generation_prompt(parsed) + "\n")
            return 0

        agent = ReportAgent(
            model=args.model,
            max_output_tokens=args.max_output_tokens,
        )
        artifacts = agent.generate_pdf(
            source,
            tex_path=args.tex_output,
            pdf_path=args.pdf_output,
            repair_attempts=args.repair_attempts,
        )

        print(f"Overleaf용 LaTeX 생성 완료: {artifacts.tex_path}", file=sys.stderr)
        print(f"모델 호출 횟수: {artifacts.generation.attempts}", file=sys.stderr)
        for warning in artifacts.generation.parsed_input.warnings:
            print(f"주의: {warning}", file=sys.stderr)

        print(f"최종 PDF 생성 완료: {artifacts.pdf_path}", file=sys.stderr)
        return 0
    except (InputContractError, GenerationError, LatexCompileError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
