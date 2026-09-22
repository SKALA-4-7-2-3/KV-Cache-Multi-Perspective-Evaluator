"""Connect the real Review Markdown handoff to the existing report agent."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def generate_report(markdown: str, output_dir: Path, *, model: str, draft: bool = False) -> dict:
    """Generate LaTeX and PDF, repairing compilation errors with the same agent.

    All attempts and errors remain beside the PDF. An unsuccessful API call,
    input contract, or compilation raises rather than returning a success stub.
    """

    repository = Path(__file__).resolve().parents[1]
    report_source = str(repository / "report-agent" / "src")
    if report_source not in sys.path:
        sys.path.insert(0, report_source)

    from report_agent.compiler import (
        LatexCompileError,
        compile_latex,
        find_latex_compiler,
    )
    from report_agent.generator import GenerationError, ReportAgent, _strip_code_fence
    from report_agent.prompt import SYSTEM_INSTRUCTIONS, build_repair_prompt
    from report_agent.validator import validate_latex

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review.output.md").write_text(markdown, encoding="utf-8")
    tex_path = output_dir / "report.tex"
    pdf_path = output_dir / "report.pdf"
    compiler = find_latex_compiler("xelatex") or find_latex_compiler("tectonic")
    if compiler is None:
        raise LatexCompileError(
            "PDF 컴파일러가 없습니다. xelatex/tectonic을 설치하거나 "
            "XELATEX_BIN/TECTONIC_BIN 경로를 설정하세요."
        )

    agent = ReportAgent(model=model, max_output_tokens=16_000)
    response_count = 0
    original_responder = agent._responder

    def recorded_response(instructions: str, prompt: str) -> str:
        nonlocal response_count
        response_count += 1
        if draft:
            instructions += (
                "\n이번 요청은 명시적으로 허용된 검증 전 통합 실행 초안이다. 제목에 '통합 실행 초안'을 넣고 "
                "첫 페이지에 '검증 전 초안: 종합 의견 자동 검토 미통과, 정밀 검증 미실시'를 명확하게 표시한다. "
                "원래 blocked/failed/rejected 상태를 통과로 바꾸거나 숨기지 않는다. "
                "반려된 종합 의견을 새로 만들지 말고 실제 관점별 평가를 근거와 함께 정리한다. "
                "시사점은 확인 가능한 평가 결과와 판단 보류 이유의 요약으로 제한한다. "
                "중간 전달 규격과 디버그 문구를 나열하지 말고 독자가 읽을 수 있는 한국어 보고서를 작성한다. "
                "본문은 핵심 내용을 중심으로 간결하게 작성한다."
            )
        candidate = original_responder(instructions, prompt)
        (output_dir / f"report.attempt-{response_count}.tex").write_text(
            _strip_code_fence(candidate) + "\n", encoding="utf-8"
        )
        return candidate

    agent._responder = recorded_response
    compilation_errors: list[str] = []
    try:
        generated = agent.generate(markdown, repair_attempts=2, allow_unreviewed=draft)
        candidate = generated.latex
        # A compile failure is actionable feedback, so give the report agent
        # a bounded repair loop without repeating any upstream API calls.
        for compile_attempt in range(3):
            tex_path.write_text(candidate, encoding="utf-8")
            try:
                compile_latex(tex_path, pdf_path)
                break
            except LatexCompileError as exc:
                compilation_errors.append(str(exc))
                (output_dir / f"report.compile-error-{compile_attempt + 1}.txt").write_text(
                    str(exc), encoding="utf-8"
                )
                if compile_attempt == 2:
                    raise
                repair_prompt = build_repair_prompt(
                    generated.parsed_input,
                    candidate,
                    ["실제 PDF 컴파일 오류를 수정하세요:\n" + str(exc)],
                )
                candidate = _strip_code_fence(
                    recorded_response(SYSTEM_INSTRUCTIONS, repair_prompt)
                ) + "\n"
                validation = validate_latex(candidate, generated.parsed_input)
                if not validation.valid:
                    raise GenerationError(
                        "컴파일 오류 수정 후 LaTeX 구조 오류:\n"
                        + "\n".join(validation.issues)
                    )
    except Exception as exc:
        (output_dir / "report.error.json").write_text(
            json.dumps(
                {"type": type(exc).__name__, "message": str(exc), "attempts": response_count},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        raise

    result = {
        "tex_path": str(tex_path),
        "pdf_path": str(pdf_path),
        "attempts": response_count,
        "compiler": compiler,
        "compile_attempts": len(compilation_errors) + 1,
        "model": model,
        "render_mode": "unreviewed_draft" if draft else "reviewed_report",
    }
    (output_dir / "report.result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
