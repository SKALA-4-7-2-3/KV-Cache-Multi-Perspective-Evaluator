"""JSON command-line boundary; no implicit .env discovery or source-path reads."""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from .agent import run_stakeholder
from .config import AgentConfig


def _read_json(path):
    from .json_input import _json_data
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return _json_data(text, "입력 파일")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="논문 분석 JSON 2개 + 요청 JSON → 이해관계자 분석 JSON")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--papers", nargs=2, metavar=("SW_JSON", "HW_JSON"), help="두 논문 JSON, 순서 무관")
    source.add_argument("--input", help="paper_analyses와 request를 포함한 통합 입력 JSON, 표준입력은 -")
    parser.add_argument("--request", help="최초 요청, 도메인 및 추가 맥락을 담은 request JSON")
    parser.add_argument("--output", help="출력 JSON 파일. 생략하면 표준출력")
    parser.add_argument("--as-of", help="조사 기준일 YYYY-MM-DD. 생략하면 실행일을 사용하고 기록")
    parser.add_argument("--run-id", help="상위 실행 ID. 생략하면 새 ID 발급")
    parser.add_argument("--env-file", help="명시적으로 읽을 .env 경로. 기존 환경변수 우선")
    parser.add_argument("--model", help="STAKEHOLDER_MODEL 또는 기본 모델을 덮어쓸 모델명")
    parser.add_argument("--demo", action="store_true", help="실제 검색 및 LLM 호출 없는 연결 검증")
    parser.add_argument("--search-limit", type=int)
    parser.add_argument("--fetch-limit", type=int)
    parser.add_argument("--llm-limit", type=int)
    args = parser.parse_args(argv)
    if args.papers and not args.request:
        parser.error("--papers를 사용할 때는 --request가 필요합니다.")
    try:
        if args.env_file:
            if not Path(args.env_file).is_file():
                raise FileNotFoundError("환경 설정 파일을 찾을 수 없습니다.")
            from dotenv import load_dotenv
            load_dotenv(args.env_file, override=False)
        payload = [_read_json(path) for path in args.papers] if args.papers else _read_json(args.input)
        request = _read_json(args.request) if args.request else None
        config = AgentConfig.from_env()
        settings = payload.get("config", {}) if isinstance(payload, dict) else {}
        allowed = ("model", "model_timeout", "tool_timeout", "repair_limit")
        if isinstance(settings, dict):
            from .json_input import RunConfigInput
            settings = RunConfigInput.model_validate(settings).model_dump(exclude_none=True)
            config = replace(config, **{key: settings[key] for key in allowed if key in settings})
        overrides = {key: value for key, value in {"model": args.model, "search_limit": args.search_limit,
                     "fetch_limit": args.fetch_limit, "llm_limit": args.llm_limit}.items() if value is not None}
        config = replace(config, **overrides)
        result = run_stakeholder(payload, request=request, as_of=args.as_of, run_id=args.run_id,
                                 config=config, mode="fixture" if args.demo else "live")
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")
            print(f"status={result['status']} / {destination}", file=sys.stderr)
        else:
            sys.stdout.write(text)
        return 2 if result["status"] == "failed" else 0
    except (OSError, ValueError) as exc:
        print(f"실행 설정 또는 JSON 파일 처리 실패 ({type(exc).__name__})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
