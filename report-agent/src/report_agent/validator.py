from __future__ import annotations

import re
from dataclasses import dataclass

from .parser import ParsedReportInput
from .prompt import REQUIRED_OUTLINE, REQUIRED_SUBSECTIONS


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: tuple[str, ...]


SECTION = re.compile(r"\\section\{([^{}]+)}")
SUBSECTION = re.compile(r"\\subsection\{([^{}]+)}")
CITE = re.compile(r"\\cite\{([^{}]+)}")
BIBITEM = re.compile(r"\\bibitem(?:\[[^\]]*])?\{([^{}]+)}")
DANGEROUS_COMMAND = re.compile(
    r"\\(?:input|include|includegraphics|bibliography|addbibresource|write18|openout|read)\b"
)
KOTEX_PACKAGE = re.compile(r"\\usepackage(?:\[[^\]]*])?\{kotex}")


def _balanced_braces(text: str) -> bool:
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "%":
            newline = text.find("\n", index)
            if newline == -1:
                break
            index = newline + 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
        index += 1
    return depth == 0


def validate_latex(latex: str, parsed: ParsedReportInput) -> ValidationResult:
    issues: list[str] = []

    if "```" in latex:
        issues.append("코드 펜스가 남아 있습니다.")
    if re.search(r"<[^>]+>", latex):
        issues.append("해결되지 않은 placeholder가 있습니다.")
    if DANGEROUS_COMMAND.search(latex):
        issues.append("금지된 외부 파일·명령 제어문이 있습니다.")
    if "file://" in latex or re.search(r"(?:^|[{\s])/(?:Users|home|tmp)/", latex):
        issues.append("Overleaf에서 사용할 수 없는 로컬 경로가 있습니다.")
    if not latex.lstrip().startswith(r"\documentclass"):
        issues.append("문서가 \\documentclass로 시작하지 않습니다.")
    if r"\documentclass[11pt,a4paper]{article}" not in latex:
        issues.append("Overleaf 보고서용 A4 article 문서 규격이 아닙니다.")
    if not KOTEX_PACKAGE.search(latex):
        issues.append("Overleaf XeLaTeX용 kotex 패키지가 없습니다.")
    if r"\hypersetup{hidelinks}" not in latex:
        issues.append("인용과 URL의 색 테두리를 숨기는 hypersetup이 없습니다.")
    if r"\begin{document}" not in latex or r"\end{document}" not in latex:
        issues.append("document 환경이 완전하지 않습니다.")
    elif latex.index(r"\begin{document}") > latex.rindex(r"\end{document}"):
        issues.append("document 환경 순서가 잘못되었습니다.")
    if not _balanced_braces(latex):
        issues.append("LaTeX 중괄호가 균형을 이루지 않습니다.")

    sections = SECTION.findall(latex)
    if sections != list(REQUIRED_OUTLINE):
        issues.append(
            "필수 section 순서 또는 제목이 다릅니다: "
            + " / ".join(sections)
        )
    subsections = SUBSECTION.findall(latex)
    required_positions = []
    for title in REQUIRED_SUBSECTIONS:
        try:
            required_positions.append(subsections.index(title))
        except ValueError:
            issues.append(f"필수 subsection이 없습니다: {title}")
    if required_positions and required_positions != sorted(required_positions):
        issues.append("필수 subsection 순서가 다릅니다.")
    if r"\renewcommand{\refname}{}" not in latex:
        issues.append("REFERENCE의 기본 References 중복 제목 제거 설정이 없습니다.")

    cited: set[str] = set()
    for group in CITE.findall(latex):
        cited.update(key.strip() for key in group.split(",") if key.strip())
    bibitems = BIBITEM.findall(latex)
    bibitem_set = set(bibitems)

    unknown_citations = sorted(cited - parsed.allowed_citation_keys)
    if unknown_citations:
        issues.append("허용되지 않은 citation_key: " + ", ".join(unknown_citations))
    if len(bibitems) != len(bibitem_set):
        issues.append("중복 bibitem이 있습니다.")
    if cited != bibitem_set:
        cited_only = ", ".join(sorted(cited - bibitem_set)) or "없음"
        bibitem_only = ", ".join(sorted(bibitem_set - cited)) or "없음"
        issues.append(
            "본문 인용과 REFERENCE bibitem 집합이 일치하지 않습니다. "
            f"본문에만 있음: {cited_only}; REFERENCE에만 있음: {bibitem_only}"
        )

    for reference_id in (parsed.metadata["sw_technology_id"], parsed.metadata["hw_technology_id"]):
        expected_key = parsed.reference_to_citation.get(reference_id)
        if expected_key and expected_key not in cited:
            issues.append(f"{reference_id}의 필수 인용 {expected_key}가 없습니다.")

    if parsed.metadata.get("demo") is True:
        if "모의" not in latex or "성능 재현" not in latex:
            issues.append("demo 입력에 필요한 모의 Agent·성능 재현 한계 문구가 없습니다.")
    if parsed.metadata.get("report_generation") == "allowed_with_gaps":
        if "미확인" not in latex and "TBD" not in latex:
            issues.append("allowed_with_gaps 입력의 미확인 사항이 보고서에서 사라졌습니다.")

    return ValidationResult(valid=not issues, issues=tuple(issues))
