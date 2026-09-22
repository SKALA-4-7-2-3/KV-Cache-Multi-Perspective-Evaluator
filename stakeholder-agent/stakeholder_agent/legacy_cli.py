"""Command-line entry point; .env loading is explicit and scoped."""

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from .config import AgentConfig
from .legacy import run_detailed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="논문 RAG Markdown → 이해관계자 조사 Markdown")
    parser.add_argument("--input", required=True, help="입력 MD 파일, 표준입력은 -")
    parser.add_argument("--output", help="출력 MD 파일. 생략하면 표준출력")
    parser.add_argument("--env-file", help="명시적으로 읽을 .env 경로 (기존 환경변수 우선)")
    parser.add_argument("--model", help="기본값은 STAKEHOLDER_MODEL 또는 gpt-4.1")
    parser.add_argument("--demo", action="store_true", help="실제 검색·LLM 없는 오프라인 연결 검증")
    parser.add_argument("--search-limit", type=int)
    parser.add_argument("--fetch-limit", type=int)
    parser.add_argument("--llm-limit", type=int)
    args = parser.parse_args(argv)
    try:
        if args.env_file:
            if not Path(args.env_file).is_file():
                parser.error("지정한 환경 설정 파일을 찾을 수 없습니다.")
            from dotenv import load_dotenv
            load_dotenv(args.env_file, override=False)
        config = AgentConfig.from_env()
        updates = {k: v for k, v in {"model": args.model, "search_limit": args.search_limit,
                   "fetch_limit": args.fetch_limit, "llm_limit": args.llm_limit}.items() if v is not None}
        config = replace(config, **updates)
        text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        result = run_detailed(text, config=config, mode="fixture" if args.demo else "live")
        if args.output:
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(result["output_md"], encoding="utf-8")
            print(f"status={result['status']} / {destination}", file=sys.stderr)
        else:
            print(result["output_md"])
        return 2 if result["status"] == "failed" else 0
    except (OSError, ValueError) as exc:
        print(f"실행 설정 또는 파일 처리 실패 ({type(exc).__name__})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
