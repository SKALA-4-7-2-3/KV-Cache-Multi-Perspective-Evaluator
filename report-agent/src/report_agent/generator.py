from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .compiler import compile_latex
from .parser import ParsedReportInput, parse_report_input
from .prompt import SYSTEM_INSTRUCTIONS, build_generation_prompt, build_repair_prompt
from .validator import ValidationResult, validate_latex


class GenerationError(RuntimeError):
    """Raised when the model cannot produce a valid LaTeX document."""


Responder = Callable[[str, str], str]


@dataclass(frozen=True)
class GenerationResult:
    latex: str
    parsed_input: ParsedReportInput
    validation: ValidationResult
    attempts: int


@dataclass(frozen=True)
class ReportArtifacts:
    generation: GenerationResult
    tex_path: Path
    pdf_path: Path


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```latex") and stripped.endswith("```"):
        return stripped[len("```latex") : -3].strip()
    if stripped.startswith("```tex") and stripped.endswith("```"):
        return stripped[len("```tex") : -3].strip()
    return stripped


class ReportAgent:
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        *,
        responder: Responder | None = None,
        max_output_tokens: int = 12_000,
    ) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._responder = responder or self._openai_response

    def _openai_response(self, instructions: str, prompt: str) -> str:
        from openai import OpenAI, OpenAIError

        client = OpenAI()
        try:
            response = client.responses.create(
                model=self.model,
                instructions=instructions,
                input=prompt,
                max_output_tokens=self.max_output_tokens,
                store=False,
            )
        except OpenAIError as exc:
            raise GenerationError(
                f"OpenAI API 호출 실패({type(exc).__name__}). API 키와 모델 접근 권한을 확인하세요."
            ) from exc
        if not response.output_text:
            raise GenerationError("모델 응답에 output_text가 없습니다.")
        return response.output_text

    def generate(self, source_markdown: str, *, repair_attempts: int = 1) -> GenerationResult:
        parsed = parse_report_input(source_markdown)
        prompt = build_generation_prompt(parsed)
        candidate = _strip_code_fence(self._responder(SYSTEM_INSTRUCTIONS, prompt))
        validation = validate_latex(candidate, parsed)
        attempts = 1

        while not validation.valid and attempts <= repair_attempts:
            repair_prompt = build_repair_prompt(parsed, candidate, list(validation.issues))
            candidate = _strip_code_fence(
                self._responder(SYSTEM_INSTRUCTIONS, repair_prompt)
            )
            validation = validate_latex(candidate, parsed)
            attempts += 1

        if not validation.valid:
            message = "\n".join(f"- {issue}" for issue in validation.issues)
            raise GenerationError(f"LaTeX 결과 검증 실패:\n{message}")

        return GenerationResult(
            latex=candidate + "\n",
            parsed_input=parsed,
            validation=validation,
            attempts=attempts,
        )

    def generate_pdf(
        self,
        source_markdown: str,
        *,
        tex_path: str | Path = "output/tex/kv-cache-technology-evaluation-report.tex",
        pdf_path: str | Path = "output/pdf/kv-cache-technology-evaluation-report.pdf",
        repair_attempts: int = 1,
    ) -> ReportArtifacts:
        """Generate, validate, persist, and compile one complete PDF report."""

        result = self.generate(source_markdown, repair_attempts=repair_attempts)
        tex_destination = Path(tex_path).resolve()
        pdf_destination = Path(pdf_path).resolve()
        tex_destination.parent.mkdir(parents=True, exist_ok=True)
        tex_destination.write_text(result.latex, encoding="utf-8")
        compiled_pdf = compile_latex(tex_destination, pdf_destination)
        return ReportArtifacts(
            generation=result,
            tex_path=tex_destination,
            pdf_path=compiled_pdf,
        )
