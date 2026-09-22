from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from .references import normalize_reference

class InputContractError(ValueError):
    """Raised when report input is unsafe or violates the handoff contract."""


@dataclass(frozen=True)
class ParsedReportInput:
    raw_markdown: str
    metadata: dict[str, Any]
    body: str
    reference_to_citation: dict[str, str]
    warnings: tuple[str, ...]
    collected_sources: tuple[dict[str, Any], ...] = ()
    retained_synthesis: dict[str, Any] = field(default_factory=dict)
    reference_records: dict[str, dict[str, Any]] = field(default_factory=dict)
    url_to_citation: dict[str, str] = field(default_factory=dict)
    source_analysis: tuple[dict[str, Any], ...] = ()

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


def _normalized_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        if parts.netloc.lower() in {"arxiv.org", "www.arxiv.org"}:
            paper = re.fullmatch(r"/(?:abs|html|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)(?:\.pdf)?/?", parts.path)
            if paper:
                return "https://arxiv.org/abs/" + paper.group(1)
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))
    except ValueError:
        return raw


def _reference_records(body: str, mapping: dict[str, str]) -> dict[str, dict[str, Any]]:
    section = body.split("## 10. REFERENCE CANDIDATES", 1)[1].split("## 11.", 1)[0]
    records = {}
    for match in re.finditer(r"(?m)^### \[([^]]+)\]\s*\n([\s\S]*?)(?=^### \[|\Z)", section):
        reference_id, block = match.groups()
        key = mapping.get(reference_id)
        if key:
            fields = dict(re.findall(r"(?m)^- ([A-Za-z_]+): (.*)$", block))
            records[key] = {field: value.replace(r"\|", "|").replace(r"\\", "\\").replace("&lt;", "<").replace("&gt;", ">")
                            for field, value in fields.items()}
            records[key]["reference_id"] = reference_id
    return records


def _include_collected_references(mapping: dict[str, str], records: dict[str, dict[str, Any]],
                                  collected_sources: list[dict[str, Any]]) -> tuple[dict, dict, dict]:
    """Keep paper keys and merge the source inventory by URL, not by citation use."""
    canonical, urls, aliases = {}, {}, {}
    ordered = sorted(records.items(), key=lambda item: item[1].get("reference_id") not in {"SW-01", "HW-01"})
    for key, record in ordered:
        url = _normalized_url(record.get("url"))
        canonical_key = urls.get(url) if url else None
        if canonical_key is None:
            canonical_key = key
            canonical[key] = record
            if url:
                urls[url] = key
        aliases[key] = canonical_key
    mapping = {reference_id: aliases[key] for reference_id, key in mapping.items()}
    for original_key, canonical_key in aliases.items():
        mapping.setdefault(original_key, canonical_key)
    for source in collected_sources:
        url = _normalized_url(source.get("url"))
        if not url:
            continue
        key = urls.get(url)
        if key is None:
            supplied_key = source.get("citation_key")
            key = supplied_key if isinstance(supplied_key, str) and CITATION_KEY.fullmatch(supplied_key) else None
            if not key or key in canonical:
                key = "WEB_" + hashlib.sha256(url.encode()).hexdigest()[:12]
            while key in canonical:
                key += "_WEB"
            urls[url] = key
            canonical[key] = {
                "citation_key": key, "title": source.get("title") or "제목 미확인",
                "authors_or_organization": source.get("author") or source.get("publisher") or "unknown",
                "publication_date": source.get("published_at") or "unknown",
                "accessed_at": source.get("retrieved_at") or "unknown",
                "url": source["url"], "source_type": source.get("source_type") or "web",
            }
        for field in ("kind", "authors_or_organization", "publication_date", "year", "venue_or_site",
                      "arxiv_id", "doi", "volume", "issue", "pages", "publication_number",
                      "patent_number", "applicant", "assignee"):
            if source.get(field) is not None and str(canonical[key].get(field) or "").lower() in {"", "unknown", "none", "null"}:
                canonical[key][field] = source[field]
        for identifier in (source.get("reference_id"), source.get("citation_key"),
                           source.get("source_id"), source.get("evidence_id"), source.get("url")):
            if identifier:
                mapping.setdefault(str(identifier), key)
        mapping.setdefault(key, key)
    return mapping, canonical, urls


def _data_block(body: str, name: str, default: Any) -> Any:
    match = re.search(r"<!-- " + name + r"_JSON\n([\s\S]*?)\nEND_" + name + r"_JSON -->", body)
    if not match:
        return default
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise InputContractError(f"{name} 자료 기록을 읽을 수 없습니다.") from exc


def parse_report_input(markdown: str, *, allow_unreviewed: bool = False,
                       allow_attributed_draft: bool = False,
                       reference_metadata: dict[str, dict[str, Any]] | None = None) -> ParsedReportInput:
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
    if allow_attributed_draft and metadata.get("attribution_first") is not True:
        raise InputContractError("출처 중심 초안은 attribution_first=true 입력에서만 허용됩니다.")
    draft_mode = allow_unreviewed or allow_attributed_draft
    if draft_mode and (metadata.get("demo") is not False
                            or metadata.get("valid_perspective_cells") != "8/8"
                            or metadata.get("failed_count") != 0):
        raise InputContractError("검증 전 초안도 실제 8개 관점 결과와 실패 없는 입력이 필요합니다.")
    if allow_attributed_draft and metadata.get("report_generation") == "blocked":
        raise InputContractError("출처 중심 초안도 입력 구조 오류로 차단된 결과는 사용할 수 없습니다.")
    if metadata.get("report_generation") == "blocked" and not draft_mode:
        raise InputContractError("report_generation=blocked 입력은 보고서를 생성할 수 없습니다.")
    if metadata.get("schema_version") != "report-input-v1":
        raise InputContractError("지원하지 않는 schema_version입니다.")
    if metadata.get("content_language") != "ko":
        raise InputContractError("content_language=ko 입력만 지원합니다.")
    if metadata.get("human_review_required") is not True:
        raise InputContractError("human_review_required는 boolean true여야 합니다.")
    if metadata.get("human_review_scope") != "final_submission_only":
        raise InputContractError("human_review_scope가 최신 계약과 다릅니다.")
    if metadata.get("semantic_validation_status") != "passed" and not draft_mode:
        raise InputContractError("종합 의견의 자동 의미 검사 통과 기록이 없습니다.")
    if type(metadata.get("demo")) is not bool:
        raise InputContractError("demo는 문자열이 아닌 boolean이어야 합니다.")
    if metadata.get("next") != "render":
        raise InputContractError("next=render인 최신 결과만 보고서를 생성할 수 있습니다.")
    if metadata.get("synthesis_status") not in {"completed", "partial"} and not draft_mode:
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

    reference_records = _reference_records(body, reference_to_citation)
    collected_sources = _data_block(body, "COLLECTED_SOURCES", [])
    retained_synthesis = _data_block(body, "RETAINED_SYNTHESIS", {})
    source_analysis = _data_block(body, "REPORT_SOURCE_ANALYSIS", [])
    if not isinstance(source_analysis, list) or any(not isinstance(item, dict) for item in source_analysis):
        raise InputContractError("출처별 분석 목록 형식이 잘못되었습니다.")
    if not isinstance(collected_sources, list) or any(not isinstance(s, dict) for s in collected_sources):
        raise InputContractError("수집 자료 목록 형식이 잘못되었습니다.")
    if not isinstance(retained_synthesis, dict):
        raise InputContractError("보존된 종합 의견 형식이 잘못되었습니다.")
    url_to_citation = {_normalized_url(record.get("url")): key for key, record in reference_records.items()
                       if record.get("url")}
    if allow_attributed_draft:
        reference_to_citation, reference_records, url_to_citation = _include_collected_references(
            reference_to_citation, reference_records, collected_sources)
    embedded_metadata = _data_block(body, "REFERENCE_METADATA", {})
    if not isinstance(embedded_metadata, dict) or any(not isinstance(value, dict) for value in embedded_metadata.values()):
        raise InputContractError("참고문헌 서지 정보 형식이 잘못되었습니다.")
    overrides = {**embedded_metadata, **(reference_metadata or {})}
    reference_records = {key: normalize_reference(record, overrides) for key, record in reference_records.items()}
    warnings: list[str] = []
    if allow_attributed_draft:
        metadata["render_mode"] = "annotated_draft"
        warnings.append("출처 기반 분석 초안입니다. 수집 자료와 종합 의견을 검토 사항과 함께 보존하며, 자동 의미 검사 미통과를 통과로 표시하지 않습니다. 출처 내용과 평가자의 해석을 구분해야 합니다.")
    elif allow_unreviewed:
        metadata["render_mode"] = "unreviewed_draft"
        warnings.append("검증 전 통합 실행 초안입니다. 종합 검토 통과를 의미하지 않습니다. 반려된 종합 의견은 사용하지 않고 실제 관점별 평가와 미확인 사항만 보고합니다.")
    else:
        metadata["render_mode"] = "reviewed_report"
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
        collected_sources=tuple(collected_sources),
        retained_synthesis=retained_synthesis,
        reference_records=reference_records,
        url_to_citation=url_to_citation,
        source_analysis=tuple(source_analysis),
    )
