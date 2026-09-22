"""전달 폴더에서 python check_report_input.py [--for-submission]으로 검사."""
import argparse
from pathlib import Path

from team_review import read_report_input


def main():
    parser = argparse.ArgumentParser(description="후단 Agent 입력 검사. API 호출 없음.")
    parser.add_argument("input", nargs="?", type=Path, default=Path(__file__).with_name("review.output.md"))
    parser.add_argument("--for-submission", action="store_true", help="실제 최종 실행 입력인지 검사. unknown을 명시한 partial은 허용, 모의·차단·보완 중은 거부")
    args = parser.parse_args()
    try:
        header, _ = read_report_input(args.input.read_text(encoding="utf-8"), for_submission=args.for_submission)
    except (OSError, ValueError) as exc:
        print(f"검사 실패: {exc}")
        return 2
    print(f"입력 검사 통과: {header['review_status']} / {header['report_generation']}, demo={header.get('demo')}")
    print("형식·인용 연결과 생성 시 자동 의미 검사 통과 기록을 확인했습니다. 실행 중 사람 승인 단계는 없습니다.")
    print("자료 자체의 진실성 및 최종 제출 적합성을 보증하는 검사는 아닙니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
