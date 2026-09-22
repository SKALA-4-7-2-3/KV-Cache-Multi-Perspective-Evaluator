"""Human-readable Markdown export for technical-research JSON artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from paper_review_agent.artifacts import atomic_write
from paper_review_agent.technical_schemas import (
    TechnicalComparison,
    TechnicalDossier,
    TechnicalEvidence,
    TechnicalResearchEnvelope,
)


_OVERVIEW_LABELS = {
    "problem_definition": "문제 정의",
    "core_approach": "핵심 접근법",
    "novelty": "신규성",
    "mechanisms": "메커니즘·알고리즘·수식",
    "training_process": "학습 과정",
    "inference_process": "추론 과정",
    "requirements": "입력·출력·데이터·연산 요구사항",
    "experimental_results": "주요 실험 결과",
    "not_reported": "논문에서 확인되지 않은 항목",
}

_SCOPE_LABELS = {
    "target_tasks": "대상 태스크",
    "domains": "대상 도메인",
    "operating_conditions": "사용 조건",
    "evaluated_settings": "평가된 데이터셋·설정",
    "modalities": "모달리티",
    "author_claimed_scope": "저자가 주장한 적용 범위",
    "inferred_scope": "분석자가 추론한 범위",
    "out_of_scope": "범위 밖 조건",
    "not_reported": "논문에서 확인되지 않은 항목",
}

_LIMITATION_LABELS = {
    "author_stated": "저자가 명시한 한계",
    "inferred": "실험·가정으로부터 추론한 한계",
    "compute_constraints": "계산 제약",
    "data_constraints": "데이터 제약",
    "generalization_constraints": "일반화 제약",
    "reproducibility_constraints": "재현성 제약",
    "not_reported": "논문에서 확인되지 않은 항목",
}


def export_technical_markdown(
    run_path: Path, output_dir: Path | None = None
) -> list[Path]:
    """Render one successful technical run into a navigable Markdown bundle.

    The exporter reads the immutable JSON artifacts and writes Markdown beside
    them by default. It deliberately does not mutate ``run.json`` or its artifact
    hashes because Markdown is a review view, not part of the machine contract.
    """

    run_path = run_path.expanduser().resolve()
    try:
        envelope = TechnicalResearchEnvelope.model_validate_json(
            run_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise ValueError(f"기술조사 run.json을 읽을 수 없습니다: {exc}") from exc
    if envelope.status != "succeeded":
        raise ValueError(
            f"성공한 기술조사 결과만 Markdown으로 변환할 수 있습니다: {envelope.status}"
        )

    evidence_path = _resolve_evidence_path(run_path, envelope)
    try:
        raw_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence = [TechnicalEvidence.model_validate(item) for item in raw_evidence]
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"evidence registry를 읽을 수 없습니다: {exc}") from exc

    destination = (output_dir or run_path.parent / "markdown").expanduser().resolve()
    dossier_dir = destination / "dossiers"
    evidence_labels = {
        item.evidence_id: f"ev-{index:03d}"
        for index, item in enumerate(evidence, start=1)
    }
    dossier_names = {
        dossier.paper.paper_id: f"{_safe_name(dossier.paper.paper_id)}.md"
        for dossier in envelope.dossiers
    }

    written: list[Path] = []
    written.append(
        _write_markdown(
            destination / "README.md",
            _render_run(envelope, dossier_names),
        )
    )
    for dossier in envelope.dossiers:
        written.append(
            _write_markdown(
                dossier_dir / dossier_names[dossier.paper.paper_id],
                _render_dossier(dossier, evidence_labels),
            )
        )
    written.append(
        _write_markdown(
            destination / "comparison.md",
            _render_comparison(envelope.comparison, evidence_labels),
        )
    )
    written.append(
        _write_markdown(
            destination / "evidence_registry.md",
            _render_evidence_registry(evidence, evidence_labels),
        )
    )
    return written


def _resolve_evidence_path(
    run_path: Path, envelope: TechnicalResearchEnvelope
) -> Path:
    configured = Path(envelope.evidence_registry_path or "")
    candidates = [
        configured if configured.is_absolute() else run_path.parent / configured,
        run_path.parent / "evidence_registry.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError("run.json과 같은 디렉터리에서 evidence_registry.json을 찾을 수 없습니다.")


def _render_run(
    envelope: TechnicalResearchEnvelope, dossier_names: dict[str, str]
) -> str:
    run = envelope.run
    quality = envelope.quality
    lines = [
        "# 기술조사 결과 검토본",
        "",
        "> 이 문서는 `run.json`과 관련 기술조사 JSON을 사람이 검토하기 쉽게 변환한 보기입니다.",
        "> 기계 간 전달과 무결성 검증에는 원본 JSON을 사용하세요.",
        "",
        "## 실행 요약",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 상태 | {_cell(envelope.status)} |",
        f"| schema version | {_cell(envelope.schema_version)} |",
        f"| job ID | `{_inline(run.job_id)}` |",
        f"| OpenAI 모델 | `{_inline(run.openai_model)}` |",
        f"| 임베딩 | `{_inline(run.embedding_model)}` |",
        f"| 임베딩 revision | `{_inline(run.embedding_revision or '-')}` |",
        f"| index profile | `{_inline(run.index_profile or '-')}` |",
        f"| 시작 | {_cell(str(run.started_at))} |",
        f"| 종료 | {_cell(str(run.finished_at or '-'))} |",
        f"| 입력 토큰 | {run.token_usage.input_tokens:,} |",
        f"| 출력 토큰 | {run.token_usage.output_tokens:,} |",
        f"| 총 토큰 | {run.token_usage.total_tokens:,} |",
        f"| peak RSS | {_format_bytes(run.peak_rss_bytes)} |",
        "",
        "## 품질 지표",
        "",
        "| 지표 | 값 |",
        "|---|---:|",
        f"| Evidence 해석률 | {quality.evidence_resolution_rate:.3f} |",
        f"| Locator 해석률 | {quality.locator_resolution_rate:.3f} |",
        f"| Critical inventory 계약 충족률 | {quality.critical_inventory_coverage:.3f} |",
        f"| Unsupported numeric claim | {quality.unsupported_numeric_claims} |",
        "",
        "## 검토 파일",
        "",
    ]
    for dossier in envelope.dossiers:
        title = dossier.paper.title or dossier.paper.paper_id
        lines.append(
            f"- [{_escape_text(title)}](dossiers/{dossier_names[dossier.paper.paper_id]})"
        )
    lines.extend(
        [
            "- [교차 논문 비교](comparison.md)",
            "- [근거 레지스트리](evidence_registry.md)",
            "",
            "## 주의 사항",
            "",
        ]
    )
    warnings = [
        *quality.warnings,
        *[
            f"{dossier.paper.paper_id}: {item.topic} — {item.reason}"
            for dossier in envelope.dossiers
            for item in dossier.unverified_items
        ],
    ]
    if warnings:
        lines.extend(f"- {_escape_text(item)}" for item in warnings)
    else:
        lines.append("- 별도 경고 없음")
    if envelope.diagnostics:
        lines.extend(["", "## 진단", ""])
        lines.extend(
            f"- `{_inline(item.code)}` ({_escape_text(item.node)}): {_escape_text(item.message)}"
            for item in envelope.diagnostics
        )
    return _finish(lines)


def _render_dossier(
    dossier: TechnicalDossier, evidence_labels: dict[str, str]
) -> str:
    paper = dossier.paper
    lines = [
        f"# {_escape_text(paper.title or paper.paper_id)}",
        "",
        "[전체 요약](../README.md) · [교차 비교](../comparison.md) · "
        "[근거 레지스트리](../evidence_registry.md)",
        "",
        "## 논문 정보",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| Paper ID | `{_inline(paper.paper_id)}` |",
        f"| arXiv ID | `{_inline(paper.arxiv_id or '-')}` |",
        f"| 저자 | {_cell(', '.join(paper.authors) or '-')} |",
        f"| 페이지 | {paper.page_count} |",
        f"| 원문 SHA-256 | `{_inline(paper.source_hash)}` |",
        "",
    ]
    if paper.abstract:
        lines.extend(["### 초록", "", _escape_text(paper.abstract), ""])

    lines.extend(["## 기술 개요", ""])
    _append_analysis_section(
        lines,
        dossier.analysis.technical_overview.model_dump(mode="python"),
        _OVERVIEW_LABELS,
        evidence_labels,
    )
    lines.extend(["## 적용 범위", ""])
    _append_analysis_section(
        lines,
        dossier.analysis.scope.model_dump(mode="python"),
        _SCOPE_LABELS,
        evidence_labels,
    )
    lines.extend(["## 한계", ""])
    _append_analysis_section(
        lines,
        dossier.analysis.limitations.model_dump(mode="python"),
        _LIMITATION_LABELS,
        evidence_labels,
    )

    lines.extend(["## 핵심 항목 Inventory", ""])
    lines.extend(
        [
            "| 상태 | 분류 | 요약 | 연결 주장 | 근거 | 이유 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in dossier.critical_inventory:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(item.disposition),
                    _cell(item.category),
                    _cell(item.summary),
                    _cell(", ".join(item.claim_ids) or "-"),
                    _cell(_evidence_links(item.evidence_ids, evidence_labels, "../")),
                    _cell(item.reason or "-"),
                ]
            )
            + " |"
        )

    lines.extend(["", "## 원자적 기술 주장", ""])
    for index, claim in enumerate(dossier.claims, start=1):
        lines.extend(
            [
                f"### {index}. `{_inline(claim.claim_id)}`",
                "",
                _escape_text(claim.text),
                "",
                f"- 유형: `{claim.claim_type}`",
                f"- Critical: `{str(claim.critical).lower()}`",
                f"- Confidence: `{claim.confidence:.3f}`",
                f"- 논문 근거: {_evidence_links(claim.evidence_ids, evidence_labels, '../')}",
            ]
        )
        if claim.context_evidence_ids:
            lines.append(
                "- 공통 문맥: "
                + _evidence_links(claim.context_evidence_ids, evidence_labels, "../")
            )
        lines.append("")

    lines.extend(["## 실험 관측", ""])
    if dossier.experiment_observations:
        lines.extend(
            [
                "| ID | Metric | 값 | Baseline | 모델·하드웨어 | Context·Workload | 평가 방식 | 근거 |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for item in dossier.experiment_observations:
            value = item.value or _range_value(item.value_min, item.value_max, item.unit)
            environment = "<br>".join(
                _cell(value)
                for value in (item.model, item.hardware)
                if value
            ) or "-"
            workload = "<br>".join(
                _cell(value)
                for value in (
                    item.context_length,
                    item.concurrency,
                    item.dataset,
                    item.workload,
                )
                if value
            ) or "-"
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{_inline(item.observation_id)}`",
                        _cell(item.metric),
                        _cell(value or "-"),
                        _cell(item.baseline or "-"),
                        environment,
                        workload,
                        _cell(item.evaluation_mode),
                        _cell(_evidence_links(item.evidence_ids, evidence_labels, "../")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- 추출된 실험 관측 없음")

    lines.extend(["", "## 미확인 항목", ""])
    if dossier.unverified_items:
        for item in dossier.unverified_items:
            lines.extend(
                [
                    f"### `{_inline(item.item_id)}` — {_escape_text(item.topic)}",
                    "",
                    f"- 이유: {_escape_text(item.reason)}",
                    f"- 시도 횟수: {item.attempts}",
                    "- 검색 질의:",
                    *[f"  - `{_inline(query)}`" for query in item.searched_queries],
                    "",
                ]
            )
    else:
        lines.append("- 없음")
    return _finish(lines)


def _append_analysis_section(
    lines: list[str],
    values: dict[str, object],
    labels: dict[str, str],
    evidence_labels: dict[str, str],
) -> None:
    for field, label in labels.items():
        items = values.get(field) or []
        lines.extend([f"### {label}", ""])
        if field == "not_reported":
            lines.extend(f"- {_escape_text(str(item))}" for item in items)
        else:
            for raw in items:
                evidence = _evidence_links(
                    raw.get("evidence_ids", []), evidence_labels, "../"
                )
                context = _evidence_links(
                    raw.get("context_evidence_ids", []), evidence_labels, "../"
                )
                metadata = (
                    f"`{raw.get('claim_type', '-')}` · confidence "
                    f"`{float(raw.get('confidence', 0.0)):.3f}` · {evidence}"
                )
                if context != "-":
                    metadata += f" · context {context}"
                lines.extend(
                    [
                        f"- {_escape_text(str(raw.get('text', '')))}",
                        f"  - {metadata}",
                    ]
                )
        if not items:
            lines.append("- 없음")
        lines.append("")


def _render_comparison(
    comparison: TechnicalComparison | None, evidence_labels: dict[str, str]
) -> str:
    if comparison is None:
        return "# 교차 논문 비교\n\n비교 결과가 없습니다.\n"
    lines = [
        "# 교차 논문 기술 비교",
        "",
        "[전체 요약](README.md) · [근거 레지스트리](evidence_registry.md)",
        "",
        "## 기술 관계",
        "",
    ]
    for item in comparison.relationships:
        lines.extend(
            [
                f"### `{item.left_paper_id}` ↔ `{item.right_paper_id}`",
                "",
                f"- 관계: **{item.relationship}**",
                f"- 함께 검증됨: `{str(item.tested_together).lower()}`",
                f"- 판단 유형: `{item.claim_type}`",
                f"- 근거: {_evidence_links(item.evidence_ids, evidence_labels)}",
                f"- 설명: {_escape_text(item.rationale)}",
                "",
            ]
        )

    lines.extend(["## 공통 가정", ""])
    if comparison.common_assumptions:
        for item in comparison.common_assumptions:
            lines.extend(
                [
                    f"- **{_escape_text(item.summary)}**",
                    f"  - 논문: {', '.join(f'`{_inline(value)}`' for value in item.paper_ids)}",
                    f"  - 근거: {_evidence_links(item.evidence_ids, evidence_labels)}",
                ]
            )
    else:
        lines.append("- 없음")

    lines.extend(["", "## 상이한 가정", ""])
    for item in comparison.differing_assumptions:
        lines.extend([f"### {_escape_text(item.dimension)}", ""])
        for assumption in item.paper_assumptions:
            lines.append(
                f"- `{_inline(assumption.paper_id)}`: {_escape_text(assumption.statement)} "
                f"({_evidence_links(assumption.evidence_ids, evidence_labels)})"
            )
        lines.extend([f"- 영향: {_escape_text(item.implication)}", ""])
    if not comparison.differing_assumptions:
        lines.append("- 없음")

    lines.extend(["## 비교 매트릭스", ""])
    if comparison.matrix:
        lines.extend(
            [
                "| 비교 차원 | 논문 | 내용 | 근거 |",
                "|---|---|---|---|",
            ]
        )
        for item in comparison.matrix:
            lines.append(
                f"| {_cell(item.dimension)} | `{_inline(item.paper_id)}` | "
                f"{_cell(item.summary)} | {_cell(_evidence_links(item.evidence_ids, evidence_labels))} |"
            )
    else:
        lines.append("- 없음")

    lines.extend(["", "## 수치 비교 가능성", ""])
    for item in comparison.metric_comparisons:
        lines.extend(
            [
                f"### {_escape_text(item.metric)}",
                "",
                f"- 판정: **{item.comparability}**",
                f"- Observation: {', '.join(f'`{_inline(value)}`' for value in item.observation_ids)}",
                f"- 이유: {_escape_text(item.reason)}",
                "",
            ]
        )
    if not comparison.metric_comparisons:
        lines.append("- 없음")

    lines.extend(["## 결합 가설", ""])
    for item in comparison.integration_hypotheses:
        lines.extend(
            [
                f"### `{_inline(item.hypothesis_id)}`",
                "",
                _escape_text(item.text),
                "",
                f"- 판단 유형: `{item.claim_type}`",
                f"- 근거: {_evidence_links(item.evidence_ids, evidence_labels)}",
                "- 가정:",
                *[f"  - {_escape_text(value)}" for value in item.assumptions],
                "- 추가 검증:",
                *[f"  - {_escape_text(value)}" for value in item.validation_needed],
                "",
            ]
        )
    if not comparison.integration_hypotheses:
        lines.append("- 없음")

    lines.extend(["## 충돌 및 미확인 항목", ""])
    lines.append("### 충돌")
    lines.append("")
    lines.extend(
        [f"- {_escape_text(item)}" for item in comparison.contradictions]
        or ["- 없음"]
    )
    lines.extend(["", "### 미확인", ""])
    if comparison.unverified_items:
        for item in comparison.unverified_items:
            lines.extend(
                [
                    f"- **{_escape_text(item.topic)}**: {_escape_text(item.reason)}",
                    f"  - 시도 횟수: {item.attempts}",
                    "  - 질의: "
                    + ", ".join(f"`{_inline(value)}`" for value in item.searched_queries),
                ]
            )
    else:
        lines.append("- 없음")
    return _finish(lines)


def _render_evidence_registry(
    evidence: list[TechnicalEvidence], labels: dict[str, str]
) -> str:
    counts: dict[str, int] = {}
    for item in evidence:
        counts[item.document_id] = counts.get(item.document_id, 0) + 1
    lines = [
        "# 근거 레지스트리",
        "",
        "[전체 요약](README.md) · [교차 비교](comparison.md)",
        "",
        "> 각 근거는 논문 페이지·절·요소·표 셀 또는 Vision crop으로 역추적할 수 있습니다.",
        "",
        "## 문서별 근거 수",
        "",
        "| 문서 | 근거 수 |",
        "|---|---:|",
        *[f"| `{_inline(key)}` | {value} |" for key, value in sorted(counts.items())],
        "",
        "## 근거 목록",
        "",
    ]
    for item in evidence:
        label = labels[item.evidence_id]
        locator = item.locator
        page = locator.physical_page or "-"
        printed = locator.printed_page_label or "-"
        section = " › ".join(locator.section_path) or "-"
        cells = "; ".join(
            f"r{cell.row_index}c{cell.column_index}={cell.raw_text}"
            for cell in locator.table_cells
        ) or "-"
        lines.extend(
            [
                f'<a id="{label}"></a>',
                f"### {label} — `{_inline(item.document_id)}` p.{page}",
                "",
                "| 항목 | 값 |",
                "|---|---|",
                f"| Evidence ID | `{_inline(item.evidence_id)}` |",
                f"| 출처 종류 | `{item.source_kind}` |",
                f"| 콘텐츠 | `{item.content_kind}` / `{item.extraction_method}` |",
                f"| 물리·인쇄 페이지 | `{page}` / `{_inline(str(printed))}` |",
                f"| 절 | {_cell(section)} |",
                f"| Object | `{_inline(locator.object_label or locator.element_id)}` |",
                f"| 원본 element | `{_inline(locator.source_element_id or '-')}` |",
                f"| Text span | `{_inline(_span(locator.text_span))}` |",
                f"| Table cell | {_cell(cells)} |",
                f"| BBox | `{_inline(_bbox(locator.bbox_pt))}` |",
                f"| Content SHA-256 | `{item.content_hash}` |",
                "",
                "<details>",
                "<summary>원문 스니펫 보기</summary>",
                "",
                *_blockquote(item.snippet),
                "",
                "</details>",
                "",
            ]
        )
    return _finish(lines)


def _evidence_links(
    evidence_ids: Iterable[str], labels: dict[str, str], prefix: str = ""
) -> str:
    links = []
    for evidence_id in evidence_ids:
        label = labels.get(evidence_id)
        if label is None:
            links.append(f"`{_inline(evidence_id)}`")
        else:
            links.append(
                f"[{label}]({prefix}evidence_registry.md#{label})"
            )
    return ", ".join(links) or "-"


def _write_markdown(path: Path, value: str) -> Path:
    atomic_write(path, value.encode("utf-8"))
    return path


def _cell(value: object) -> str:
    return _escape_text(str(value)).replace("\n", "<br>").replace("|", "\\|")


def _escape_text(value: str) -> str:
    return value.replace("<", "&lt;").replace(">", "&gt;")


def _inline(value: str) -> str:
    return value.replace("`", "\u02cb").replace("\n", " ")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "paper"


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    gib = value / (1024**3)
    return f"{value:,} bytes ({gib:.2f} GiB)"


def _range_value(low: float | None, high: float | None, unit: str | None) -> str:
    suffix = f" {unit}" if unit else ""
    if low is not None and high is not None:
        return f"{low:g}–{high:g}{suffix}"
    if low is not None:
        return f"≥ {low:g}{suffix}"
    if high is not None:
        return f"≤ {high:g}{suffix}"
    return "-"


def _span(value: object) -> str:
    if value is None:
        return "-"
    return f"{value.start}:{value.end}"


def _bbox(value: tuple[float, float, float, float] | None) -> str:
    if value is None:
        return "-"
    return ", ".join(f"{item:.2f}" for item in value)


def _blockquote(value: str) -> list[str]:
    return [f"> {line}" if line else ">" for line in value.splitlines()]


def _finish(lines: list[str]) -> str:
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["export_technical_markdown"]
