"""python -m team_review --input team.input.md [--synthesize]"""

import argparse
import json
from pathlib import Path

from .demo import SCENARIOS, make_input
from .markdown import review_agent_node, review_handoff_node, read_report_input
from .input_markdown import parse_input_markdown, render_input_markdown
from .contract import config_of
import yaml
from .rubric import ROLES, instructions_for


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="기본은 API 없는 진단. --synthesize는 생성·의미 검사, 필요 시 한 번 수정")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", choices=(*SCENARIOS, "all"))
    source.add_argument("--input", type=Path)
    source.add_argument("--instructions", choices=ROLES)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--synthesize", action="store_true")
    parser.add_argument("--env-file", type=Path, help="명시한 .env만 로드. 키는 출력하지 않음")
    parser.add_argument("--debug-json", action="store_true", help="개발 점검용 JSON 추가 저장")
    args = parser.parse_args(argv)
    if args.env_file:
        from dotenv import load_dotenv
        if not args.env_file.is_file():
            parser.error("명시한 환경 파일을 찾을 수 없습니다.")
        # 사용자가 명시한 파일이 셸의 오래된 키보다 우선한다. 파일 자체는 변경하지 않는다.
        load_dotenv(args.env_file, override=True)
    if args.instructions:
        print(instructions_for(args.instructions))
        return 0
    if args.input:
        try:
            raw = args.input.read_text(encoding="utf-8")
            data = parse_input_markdown(raw) if args.input.suffix.lower() == ".md" else json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("최상위 입력은 JSON object여야 합니다.")
        except (OSError, ValueError, yaml.YAMLError) as exc:
            # 디코딩 오류에 원본 입력/키를 포함하지 않는다.
            print(f"입력 파일 확인 실패: {type(exc).__name__}")
            return 2
        cases = [("review", data)]
    else:
        cases = [(s, make_input(s)) for s in (SCENARIOS if args.demo == "all" else (args.demo,))]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    exit_code = 0
    for name, data in cases:
        try:
            output = review_agent_node(data) if args.synthesize else review_handoff_node(data)
        except (ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
            diagnostic = args.output_dir / f"{name}.diagnostic.md"
            diagnostic.write_text(f"# 보고서 생성 차단\n\n출력 계약 검사 실패: {type(exc).__name__}. 기존 출력 파일을 사용하지 마세요.\n", encoding="utf-8")
            print(f"출력 실패: {diagnostic}")
            return 2
        if args.demo:
            (args.output_dir / f"{name}.input.md").write_text(render_input_markdown(data), encoding="utf-8")
        if args.debug_json:
            path = args.output_dir / f"{name}.output.json"
            path.write_text(json.dumps({k: v for k, v in output.items() if k != 'report_input_md'}, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path = args.output_dir / f"{name}.output.md"
        md_path.write_text(output["report_input_md"], encoding="utf-8")
        header, _ = read_report_input(output["report_input_md"], require_allowed=False)
        print(f"{name}: {header['review_status']} / {header['report_generation']}, cells={header['valid_perspective_cells']}, criteria={header['valid_criterion_blocks']}, {md_path}")
        if args.input and header["report_generation"] == "blocked":
            exit_code = 2
        if args.synthesize and output["synthesis"]["integrated"]["status"] == "failed":
            exit_code = 2
    if args.demo:
        print("DUMMY: 데모 값은 실제 기술 평가·논문 성능·TRL이 아닙니다.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
