from __future__ import annotations

import re
from dataclasses import dataclass

from .parser import MARKET_CRITERIA, ParsedReportInput
from .prompt import REQUIRED_OUTLINE, REQUIRED_SUBSECTIONS
from .layout import normalize_numeric_ranges


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


def _visible_text(latex: str) -> str:
    """Read visible contract fields, excluding comments and citation commands."""
    value = re.sub(r"(?<!\\)%[^\n]*", "", latex)
    value = CITE.sub("", value)
    value = re.sub(r"\\([%&_#$])", r"\1", value)
    value = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", "", value)
    return re.sub(r"[{}~]", " ", value)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _reason_preserved(expected: str, plain: str) -> bool:
    """Permit one added standalone '명확히'; retain every source word."""
    compact_expected = _compact(expected)
    if compact_expected in _compact(plain):
        return True
    for modifier in re.finditer(r"(?<!\S)명확히(?=\s)", plain):
        without_modifier = plain[:modifier.start()] + plain[modifier.end():]
        if compact_expected in _compact(without_modifier):
            return True
    return False


def _trl_issues(latex: str, parsed: ParsedReportInput) -> list[str]:
    if not parsed.trl_assessments:
        return []
    heading = re.search(r"\\subsection\{기술 성숙도\}", latex)
    if not heading:
        return ["TRL: 기술 성숙도 subsection에 최종 Review 판정을 작성해야 합니다."]
    following = latex[heading.end():]
    end = re.search(r"\\(?:subsection|section)\{", following)
    maturity = following[:end.start()] if end else following
    visible_maturity = _visible_text(maturity)
    issues = []
    if not (re.search(r"공개\s*정보", visible_maturity)
            and re.search(r"팀\s*추정", visible_maturity)
            and re.search(r"공식\s*인증.{0,12}(?:아니|아님)", visible_maturity)):
        issues.append("TRL: 기술 성숙도 본문에 공개 정보 기반 팀 추정이며 공식 인증이 아님을 명시해야 합니다.")
    names = {parsed.metadata["sw_technology_id"]: "RDKV",
             parsed.metadata["hw_technology_id"]: "Photonic-CXL"}
    for tech, record in parsed.trl_assessments.items():
        expression = (r"(?m)^% BEGIN_TRL_ASSESSMENT " + re.escape(tech)
                      + r"\s*\n([\s\S]*?)^% END_TRL_ASSESSMENT " + re.escape(tech) + r"\s*$")
        blocks = re.findall(expression, maturity)
        if len(blocks) != 1:
            issues.append(f"TRL {tech}: 기술 성숙도 안에 BEGIN_TRL_ASSESSMENT/END_TRL_ASSESSMENT 경계와 본문을 정확히 한 번 작성해야 합니다.")
            continue
        block = blocks[0]
        plain = _visible_text(block)
        expected = "미확인" if record["level"] is None else str(record["level"])
        levels = re.findall(
            r"추정\s*TRL\s*[:：]\s*(미확인|[1-9])"
            r"(?!\d|\s*[-–—～]?\s*\d|\.\d|\s*(?:에서|부터)\s*[1-9])"
            r"(?=$|[\s.,;:()。])",
            plain,
        )
        if names[tech] not in plain or levels != [expected]:
            issues.append(f"TRL {tech}: {names[tech]}의 추정 TRL: {expected}를 보이는 본문에 유지해야 합니다. Review level={record['level']}이며 임의 숫자 변경은 허용하지 않습니다.")
        other_grades = re.findall(
            r"(?:실제|최종|확정|현재|공식|인증된|달성한)\s*TRL\s*[:：]?\s*([1-9])(?!\d)"
            r"|TRL\s*[:：]?\s*([1-9])(?!\d)\s*(?:단계)?\s*(?:수준|이다|임|에\s*해당|로\s*평가|를\s*달성)",
            plain,
        )
        if any((left or right) != expected for left, right in other_grades):
            issues.append(f"TRL {tech}: Review 추정 TRL: {expected}와 다른 실제·최종 단계 단정이 있습니다.")
        block_citations = {key.strip() for group in CITE.findall(re.sub(r"(?<!\\)%[^\n]*", "", block))
                           for key in group.split(",")}
        missing = set(record["citation_keys"]) - block_citations
        if missing:
            issues.append(f"TRL {tech}: 단계 근거 인용을 해당 TRL 본문에 넣어야 합니다: " + ", ".join(sorted(missing)))
        if "다음미확인조건:" not in _compact(plain).replace("：", ":"):
            issues.append(f"TRL {tech}: 다음 미확인 조건: 표시가 필요합니다.")
        for field in ("next_condition", "next_reason"):
            expected_text = record[field]
            preserved = (_reason_preserved(expected_text, plain) if field == "next_reason"
                         else _compact(expected_text) in _compact(plain))
            if expected_text and not preserved:
                issues.append(f"TRL {tech}: 다음 미확인 조건/이유를 보존해야 합니다: {expected_text}")
    return issues


def _market_issues(latex: str, parsed: ParsedReportInput) -> list[str]:
    if not parsed.market_cells:
        return []
    heading = re.search(r"\\subsection\{시장성\}", latex)
    if not heading:
        return ["시장성: 12개 기술·항목 분석을 시장성 subsection에 작성해야 합니다."]
    following = latex[heading.end():]
    end = re.search(r"\\(?:subsection|section)\{", following)
    market = following[:end.start()] if end else following
    names = {parsed.metadata["sw_technology_id"]: "RDKV", parsed.metadata["hw_technology_id"]: "Photonic-CXL"}
    issues = []
    for tech, criterion in parsed.market_cells:
        identity = re.escape(f"{tech} {criterion}")
        pattern = rf"(?m)^% BEGIN_MARKET_CELL {identity}[ \t]*\n([\s\S]*?)^% END_MARKET_CELL {identity}[ \t]*$"
        blocks = re.findall(pattern, market)
        if len(blocks) != 1:
            issues.append(f"시장성 {tech}/{criterion}: 시장성 안에 정확한 경계와 분석 본문을 한 번 작성해야 합니다.")
            continue
        plain = _visible_text(blocks[0])
        label = MARKET_CRITERIA[criterion]
        content = plain.replace(names[tech], "", 1).replace(label, "", 1)
        if names[tech] not in plain or _compact(label) not in _compact(plain) or len(_compact(content)) < 20:
            issues.append(f"시장성 {tech}/{criterion}: 보이는 기술·항목 제목과 실질 분석 본문이 필요합니다.")
        if not CITE.search(re.sub(r"(?<!\\)%[^\n]*", "", blocks[0])) and not all(
                field in _compact(plain).replace("：", ":") for field in ("미확인", "판단영향:", "다음확인:")):
            issues.append(f"시장성 {tech}/{criterion}: 근거 인용 또는 미확인 범위·판단 영향·다음 확인을 작성해야 합니다.")
    return issues


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
    issues.extend(_trl_issues(latex, parsed))
    issues.extend(_market_issues(latex, parsed))
    if normalize_numeric_ranges(latex) != latex:
        issues.append("숫자 범위의 ~는 PDF에서 공백으로 표시됩니다. 숫자·단위를 보존하고 -- 또는 '부터 …까지'로 범위를 명시하세요.")

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
