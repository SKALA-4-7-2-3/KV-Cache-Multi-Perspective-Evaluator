from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any

class InputContractError(ValueError):
    """Raised when report input is unsafe or violates the handoff contract."""


@dataclass(frozen=True)
class ParsedReportInput:
    raw_markdown: str
    metadata: dict[str, Any]
    body: str
    reference_to_citation: dict[str, str]
    warnings: tuple[str, ...]

    @property
    def allowed_citation_keys(self) -> set[str]:
        return set(self.reference_to_citation.values())


FRONT_MATTER = re.compile(r"\A---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)\Z", re.DOTALL)
CITATION_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]*$")
STATUS_PAIRS = {
    ("complete", "allowed"),
    ("partial", "allowed_with_gaps"),
    ("failed", "blocked"),
}
REQUIRED_METADATA = {
    "schema_version",
    "rubric_version",
    "reference_schema_version",
    "content_language",
    "run_id",
    "generated_at",
    "evaluation_as_of",
    "review_status",
    "report_generation",
    "human_review_required",
    "human_review_scope",
    "semantic_validation_status",
    "sw_technology_id",
    "hw_technology_id",
    "valid_perspective_cells",
    "valid_criterion_blocks",
    "unknown_count",
    "failed_count",
    "evidence_count",
    "reference_candidate_count",
    "demo",
    "next",
    "synthesis_status",
}


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value[0:1] in {"'", '"'} and value[-1:] == value[0]:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            raise InputContractError(f"잘못된 quoted YAML scalar: {value}") from None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _parse_flat_frontmatter(text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)", line)
        if not match:
            raise InputContractError(
                f"지원하지 않는 YAML frontmatter 형식({line_number}행): {line}"
            )
        key, value = match.groups()
        if key in metadata:
            raise InputContractError(f"중복 metadata key: {key}")
        metadata[key] = _parse_scalar(value)
    return metadata


def _parse_references(body: str) -> dict[str, str]:
    start = re.search(r"(?m)^## 10\. REFERENCE CANDIDATES\s*$", body)
    end = re.search(r"(?m)^## 11\.", body)
    if not start or not end or end.start() <= start.end():
        raise InputContractError("REFERENCE CANDIDATES 섹션을 찾을 수 없습니다.")

    section = body[start.end() : end.start()]
    mapping: dict[str, str] = {}
    current_reference: str | None = None

    for line in section.splitlines():
        heading = re.fullmatch(r"### \[([^]]+)]", line.strip())
        if heading:
            current_reference = heading.group(1).strip()
            if current_reference in mapping:
                raise InputContractError(f"중복 Reference ID: {current_reference}")
            continue

        key_match = re.fullmatch(r"- citation_key:\s*(\S+)", line.strip())
        if key_match and current_reference:
            key = key_match.group(1)
            if not CITATION_KEY.fullmatch(key):
                raise InputContractError(f"잘못된 citation_key: {key}")
            if key in mapping.values():
                raise InputContractError(f"중복 citation_key: {key}")
            mapping[current_reference] = key

    if not mapping:
        raise InputContractError("구조화된 Reference/citation_key가 없습니다.")
    return mapping


def parse_report_input(markdown: str) -> ParsedReportInput:
    if not markdown.strip():
        raise InputContractError("입력 Markdown이 비어 있습니다.")

    match = FRONT_MATTER.match(markdown.replace("\r\n", "\n"))
    if not match:
        raise InputContractError("YAML frontmatter를 읽을 수 없습니다.")

    metadata = _parse_flat_frontmatter(match.group("meta"))

    missing = sorted(REQUIRED_METADATA - metadata.keys())
    if missing:
        raise InputContractError(f"필수 metadata 누락: {', '.join(missing)}")

    status_pair = (metadata.get("review_status"), metadata.get("report_generation"))
    if status_pair not in STATUS_PAIRS:
        raise InputContractError(f"허용되지 않은 상태 조합: {status_pair}")
    if metadata.get("report_generation") == "blocked":
        raise InputContractError("report_generation=blocked 입력은 보고서를 생성할 수 없습니다.")
    if metadata.get("schema_version") != "report-input-v1":
        raise InputContractError("지원하지 않는 schema_version입니다.")
    if metadata.get("content_language") != "ko":
        raise InputContractError("content_language=ko 입력만 지원합니다.")
    if metadata.get("human_review_required") is not True:
        raise InputContractError("human_review_required는 boolean true여야 합니다.")
    if metadata.get("human_review_scope") != "final_submission_only":
        raise InputContractError("human_review_scope가 최신 계약과 다릅니다.")
    if metadata.get("semantic_validation_status") != "passed":
        raise InputContractError("종합 의견의 자동 의미 검사 통과 기록이 없습니다.")
    if type(metadata.get("demo")) is not bool:
        raise InputContractError("demo는 문자열이 아닌 boolean이어야 합니다.")
    if metadata.get("next") != "render":
        raise InputContractError("next=render인 최신 결과만 보고서를 생성할 수 있습니다.")
    if metadata.get("synthesis_status") not in {"completed", "partial"}:
        raise InputContractError("종합 의견이 완료되지 않아 보고서를 생성할 수 없습니다.")

    for key in ("unknown_count", "failed_count", "evidence_count", "reference_candidate_count"):
        if type(metadata.get(key)) is not int or metadata[key] < 0:
            raise InputContractError(f"{key}는 0 이상의 정수여야 합니다.")
    for key in ("valid_perspective_cells", "valid_criterion_blocks"):
        if not isinstance(metadata.get(key), str) or not re.fullmatch(r"\d+/\d+", metadata[key]):
            raise InputContractError(f"{key}는 N/M 형식이어야 합니다.")

    body = match.group("body")
    required_sections = [f"## {number}." for number in range(1, 13)]
    absent_sections = [prefix for prefix in required_sections if prefix not in body]
    if absent_sections:
        raise InputContractError(f"필수 입력 섹션 누락: {', '.join(absent_sections)}")

    reference_to_citation = _parse_references(body)
    expected_references = metadata.get("reference_candidate_count")
    if type(expected_references) is int and expected_references != len(reference_to_citation):
        raise InputContractError(
            "reference_candidate_count와 실제 Reference 수가 다릅니다: "
            f"{expected_references} != {len(reference_to_citation)}"
        )

    warnings: list[str] = []
    if metadata.get("report_generation") == "allowed_with_gaps":
        warnings.append("입력이 partial이므로 미확인 사항과 한계를 최종 보고서에 포함해야 합니다.")
    if metadata.get("human_review_required") is True:
        warnings.append("생성 결과는 사람의 최종 검토가 필요합니다.")
    if metadata.get("demo") is True:
        warnings.append("모의 Agent 입력임을 최종 보고서에 명시해야 합니다.")
    if metadata.get("synthesis_status") == "partial":
        warnings.append("종합 관계 분석 일부가 미완료이므로 보류 사유를 최종 보고서에 포함해야 합니다.")

    return ParsedReportInput(
        raw_markdown=markdown,
        metadata=metadata,
        body=body,
        reference_to_citation=reference_to_citation,
        warnings=tuple(warnings),
    )
