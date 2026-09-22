"""검증된 MD와 후단 검사에 필요한 파일만 묶는다. 키·환경·PDF·캐시는 제외."""
import argparse
from pathlib import Path
from shutil import copyfile
from zipfile import ZipFile, ZIP_DEFLATED

from .markdown import read_report_input


def build_handoff(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    package = Path(__file__).resolve().parent
    if destination == package or package in destination.parents:
        raise ValueError("전달 폴더를 소스 패키지 내부에 만들 수 없습니다.")
    read_report_input(source.read_text(encoding="utf-8"))
    files = {
        "review.output.md": source,
        "REPORT-HANDOFF.md": package / "REPORT-HANDOFF.md",
        "review.output.contract.final.md": package / "OUTPUT-CONTRACT.md",
        "check_report_input.py": package / "check_report_input.py",
        "requirements.txt": package / "requirements.txt",
        "team_review/SYNTHESIS-PROMPT.md": package / "SYNTHESIS-PROMPT.md",
        "team_review/GROUNDING-PROMPT.md": package / "GROUNDING-PROMPT.md",
    }
    files.update({f"team_review/{path.name}": path for path in package.glob("*.py")})
    for name, path in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(path, target)
    archive = destination.with_suffix(".zip")
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        for name in sorted(files):
            bundle.write(destination / name, name)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("outputs/review.output.md"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/report_handoff"))
    args = parser.parse_args()
    print(build_handoff(args.input, args.output_dir))


if __name__ == "__main__":
    main()
