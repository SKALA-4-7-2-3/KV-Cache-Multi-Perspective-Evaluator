"""Reuse saved research by default; run the original RAG only when requested.

This module uses only the standard library. The heavy research dependencies
remain in rag/.venv and are never imported into the report pipeline process.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4


def resolve_research(
    *,
    sources: list[Path],
    instruction: str,
    output_dir: Path,
    saved_path: Path,
    run_rag: bool = False,
) -> Path:
    """Return a directory containing run.json for the existing downstream loader."""
    if not run_rag:
        saved = Path(saved_path).expanduser().resolve()
        if saved.name == "run.json":
            saved = saved.parent
        if not (saved / "run.json").is_file():
            raise FileNotFoundError(f"저장된 RAG 결과를 찾을 수 없습니다: {saved / 'run.json'}")
        return saved

    if not instruction.strip():
        raise ValueError("새 RAG 실행에는 자연어 분석 요청이 필요합니다.")
    documents = [Path(source).expanduser().resolve() for source in sources]
    if not documents:
        raise ValueError("새 RAG 실행에는 입력 PDF 경로가 필요합니다.")
    missing = [str(path) for path in documents if not path.is_file()]
    if missing:
        raise FileNotFoundError("RAG 입력 파일을 찾을 수 없습니다: " + ", ".join(missing))
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("새 RAG 실행에는 uv가 필요합니다.")

    rag_dir = Path(__file__).resolve().parent
    destination = Path(output_dir).expanduser().resolve()
    job_id = "pipeline-" + uuid4().hex[:16]
    job_dir = destination / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    command = [uv, "run", "--frozen", "--project", str(rag_dir), "paper-review", "research",
               "--instruction", instruction, "--language", "ko", "--job-id", job_id]
    for path in documents:
        command.extend(["--source", str(path)])
    environment = os.environ.copy()
    environment["PRA_OUTPUT_DIR"] = str(destination)
    # A parent pipeline virtualenv must not become the heavy RAG environment.
    environment.pop("VIRTUAL_ENV", None)
    environment.pop("UV_PROJECT_ENVIRONMENT", None)
    stdout_path, stderr_path = job_dir / "cli.stdout.json", job_dir / "cli.stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        completed = subprocess.run(command, cwd=rag_dir, env=environment,
                                   stdout=stdout, stderr=stderr, check=False)
    result = job_dir / "technical"
    if completed.returncode or not (result / "run.json").is_file():
        raise RuntimeError(
            f"RAG 실행이 완료되지 않았습니다. 실행 기록: {job_dir}. "
            "처음 실행한다면 rag에서 uv run --frozen paper-review models pull bge-m3로 "
            "고정 임베딩 모델을 준비하세요."
        )
    return result
