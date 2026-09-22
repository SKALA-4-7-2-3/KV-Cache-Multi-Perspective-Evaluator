"""Source resolution, PDF/TXT parsing, and section-aware chunking."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Sequence
from typing import Any, Protocol
from urllib.request import Request, urlopen

from paper_review_agent.config import AppConfig
from paper_review_agent.exceptions import DependencyError, IngestionError
from paper_review_agent.schemas import (
    BoundingBox,
    Chunk,
    PageElement,
    PaperMetadata,
    ParsedDocument,
    TableCellRef,
    TextSpan,
)

ARXIV_RE = re.compile(r"^(?P<id>\d{4}\.\d{4,5}(?:v\d+)?)$")
KNOWN_HEADING_RE = re.compile(
    r"^(?:(?:\d+(?:\.\d+)*)\s+)?(?:Abstract|Introduction|"
    r"Background|Related Work|Method(?:ology)?|Approach|Experiments?|Results?|"
    r"Discussion|Limitations?|Conclusion|Future Work|Appendix)\s*$",
    re.IGNORECASE,
)
ALL_CAPS_HEADING_RE = re.compile(r"^(?:(?:\d+(?:\.\d+)*)\s+)?[A-Z][A-Z\s&:/-]{3,}$")
NUMBERED_HEADING_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+[A-Za-z].+$")
CAPTION_RE = re.compile(
    r"^(?P<kind>Figure|Fig\.|Table)\s*"
    r"(?P<number>(?:[A-Z]\.)?(?:\d+(?:[A-Za-z])?|[IVXLCDM]+))\s*[.:]\s*(?P<body>.*)$",
    re.IGNORECASE | re.DOTALL,
)
FALLBACK_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)

Tokenizer = Callable[[str], Sequence[object]]


class DocumentService(Protocol):
    def resolve_source(self, source: str) -> tuple[Path, str | None]: ...

    def parse(
        self,
        path: Path,
        *,
        document_id: str | None,
        source_kind: str,
        arxiv_id: str | None = None,
        enforce_quality: bool = True,
    ) -> ParsedDocument: ...


@dataclass(slots=True)
class LocalDocumentService:
    config: AppConfig
    tokenizer: Tokenizer | None = None

    def resolve_source(self, source: str) -> tuple[Path, str | None]:
        match = ARXIV_RE.fullmatch(source.strip())
        if match:
            arxiv_id = match.group("id")
            target = self.config.input_dir / f"{arxiv_id}.pdf"
            if target.exists():
                if target.stat().st_size == 0 or not _looks_like_pdf(target):
                    raise IngestionError(f"기존 arXiv 입력이 올바른 PDF가 아닙니다: {target}")
                return target.resolve(), arxiv_id
            self.config.input_dir.mkdir(parents=True, exist_ok=True)
            self._download_arxiv(arxiv_id, target)
            return target.resolve(), arxiv_id

        path = Path(source).expanduser()
        if not path.is_file():
            raise IngestionError(f"입력 파일을 찾을 수 없습니다: {path}")
        if path.suffix.lower() not in {".pdf", ".txt", ".md"}:
            raise IngestionError("지원 입력은 PDF, TXT, Markdown 또는 arXiv ID입니다.")
        return path.resolve(), None

    def _download_arxiv(self, arxiv_id: str, target: Path) -> None:
        request = Request(
            f"https://arxiv.org/pdf/{arxiv_id}",
            headers={"User-Agent": "paper-review-agent/0.1"},
        )
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{arxiv_id}.", suffix=".pdf.part", dir=target.parent
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle, urlopen(request, timeout=180) as response:
                while block := response.read(1024 * 1024):
                    handle.write(block)
                handle.flush()
                os.fsync(handle.fileno())
            if not _looks_like_pdf(temp_path):
                raise IngestionError(f"arXiv 응답이 PDF가 아닙니다: {arxiv_id}")
            os.replace(temp_path, target)
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError(f"arXiv 다운로드에 실패했습니다: {arxiv_id}: {exc}") from exc
        finally:
            temp_path.unlink(missing_ok=True)

    def parse(
        self,
        path: Path,
        *,
        document_id: str | None,
        source_kind: str,
        arxiv_id: str | None = None,
        enforce_quality: bool = True,
    ) -> ParsedDocument:
        source_hash = _sha256_file(path)
        resolved_id = document_id or source_hash
        if path.suffix.lower() == ".pdf":
            elements, page_count = self._parse_pdf(path, document_id=resolved_id)
        else:
            text = _normalize_text(path.read_text(encoding="utf-8"))
            elements = _text_elements(text, page=1, document_id=resolved_id)
            page_count = 1

        character_count = sum(
            len(element.text) for element in elements if element.content_kind == "text"
        )
        if enforce_quality and character_count < self.config.min_text_chars:
            raise IngestionError(
                f"유효 텍스트가 {character_count}자로 최소 {self.config.min_text_chars}자보다 "
                "짧습니다. 스캔 PDF라면 OCR이 필요합니다."
            )

        all_text = "\n".join(element.text for element in elements if element.content_kind == "text")
        title, abstract = _infer_metadata(all_text, elements)
        metadata = PaperMetadata(
            paper_id=resolved_id,
            title=title,
            abstract=abstract,
            arxiv_id=arxiv_id,
            source_path=str(path),
            source_hash=source_hash,
            page_count=page_count,
        )
        elements = _coalesce_text_elements(
            elements,
            document_id=resolved_id,
            max_tokens=getattr(self.config, "bge_chunk_tokens", 800),
            tokenizer=self.tokenizer,
        )
        chunks = chunk_elements(
            elements,
            source_kind=source_kind,
            document_id=resolved_id,
            document_version=source_hash,
            chunk_chars=self.config.chunk_chars,
            overlap_chars=self.config.chunk_overlap_chars,
            tokenizer=self.tokenizer,
            chunk_tokens=getattr(self.config, "bge_chunk_tokens", None),
            overlap_tokens=getattr(self.config, "bge_chunk_overlap_tokens", None),
            hard_limit_tokens=getattr(self.config, "bge_chunk_hard_limit", None),
        )
        return ParsedDocument(
            metadata=metadata,
            elements=elements,
            chunks=chunks,
            character_count=character_count,
        )

    def _parse_pdf(self, path: Path, *, document_id: str) -> tuple[list[PageElement], int]:
        try:
            import pymupdf
        except ImportError as exc:
            raise DependencyError("PDF 처리에는 pymupdf가 필요합니다.") from exc

        elements: list[PageElement] = []
        try:
            document = pymupdf.open(path)
        except Exception as exc:
            raise IngestionError(f"PDF를 열 수 없습니다: {path}: {exc}") from exc

        current_section: str | None = None
        try:
            page_count = len(document)
            for page_number, page in enumerate(document, start=1):
                page_elements, current_section = _pdf_page_elements(
                    page,
                    page_number=page_number,
                    document_id=document_id,
                    current_section=current_section,
                )
                elements.extend(page_elements)
        finally:
            document.close()

        captions = [item for item in elements if item.content_kind == "caption"]
        elements.extend(self._extract_tables(path, captions=captions, document_id=document_id))
        elements.sort(key=_element_sort_key)
        return elements, page_count

    def _extract_tables(
        self,
        path: Path,
        *,
        captions: list[PageElement],
        document_id: str,
    ) -> list[PageElement]:
        try:
            import pdfplumber
        except ImportError as exc:
            raise DependencyError("표 추출에는 pdfplumber가 필요합니다.") from exc

        tables: list[PageElement] = []
        try:
            caption_by_page: dict[int, list[PageElement]] = {}
            for caption in captions:
                caption_by_page.setdefault(caption.page, []).append(caption)
            with pdfplumber.open(path) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    detected = list(page.find_tables() or [])
                    for table_index, table in enumerate(detected):
                        rows = table.extract() or []
                        bbox_values = tuple(float(value) for value in table.bbox)
                        bbox = _make_bbox(
                            bbox_values,
                            page_width=float(page.width),
                            page_height=float(page.height),
                        )
                        caption = _nearest_caption(
                            caption_by_page.get(page_number, []),
                            bbox=bbox,
                            expected_kind="table",
                        )
                        if not _is_useful_table(rows, has_table_caption=caption is not None):
                            continue
                        markdown = _table_to_markdown(rows)
                        if markdown:
                            element_id = _stable_element_id(
                                document_id,
                                page_number,
                                "table",
                                table_index,
                                markdown,
                                bbox,
                            )
                            tables.append(
                                PageElement(
                                    page=page_number,
                                    section=caption.section if caption else "Table",
                                    content_kind="table",
                                    text=markdown,
                                    element_id=element_id,
                                    parent_element_id=caption.element_id if caption else None,
                                    object_label=caption.object_label if caption else None,
                                    printed_page=caption.printed_page if caption else str(page_number),
                                    bbox=bbox,
                                    text_span=TextSpan(start=0, end=len(markdown)),
                                    table_cells=_table_cell_refs(rows),
                                    extraction_method="pdfplumber",
                                )
                            )
        except Exception as exc:
            raise IngestionError(f"PDF 표 추출에 실패했습니다: {path}: {exc}") from exc
        return tables


def chunk_elements(
    elements: list[PageElement],
    *,
    source_kind: str,
    document_id: str,
    document_version: str | None = None,
    chunk_chars: int,
    overlap_chars: int,
    tokenizer: Tokenizer | None = None,
    chunk_tokens: int | None = None,
    overlap_tokens: int | None = None,
    hard_limit_tokens: int | None = None,
) -> list[Chunk]:
    """Chunk text on token budgets while preserving exact source character spans.

    ``chunk_chars`` and ``overlap_chars`` remain public for compatibility.  When
    explicit token budgets are omitted they are converted using the conservative
    four-characters-per-token rule.  An injected tokenizer only needs to return a
    sized sequence; decoding is deliberately unnecessary so chunks remain exact
    substrings of the source.
    """

    resolved_chunk_tokens = chunk_tokens or max(1, chunk_chars // 4)
    resolved_overlap_tokens = (
        overlap_tokens if overlap_tokens is not None else max(0, overlap_chars // 4)
    )
    if resolved_overlap_tokens >= resolved_chunk_tokens:
        raise ValueError("overlap_tokens는 chunk_tokens보다 작아야 합니다.")
    resolved_hard_limit = hard_limit_tokens or resolved_chunk_tokens
    if resolved_hard_limit < resolved_chunk_tokens:
        raise ValueError("hard_limit_tokens는 chunk_tokens 이상이어야 합니다.")
    chunks: list[Chunk] = []
    seen: set[tuple[str, str]] = set()
    for element in elements:
        if element.content_kind == "text":
            parts = [
                (*part, element.table_cells)
                for part in _token_sliding_chunks(
                    element.text,
                    max_tokens=resolved_chunk_tokens,
                    overlap_tokens=resolved_overlap_tokens,
                    tokenizer=tokenizer,
                )
            ]
        elif element.content_kind == "table":
            parts = _table_row_group_chunks(
                element,
                max_tokens=resolved_chunk_tokens,
                hard_limit_tokens=resolved_hard_limit,
                tokenizer=tokenizer,
            )
        else:
            parts = [(element.text, 0, len(element.text), element.table_cells)]
        for index, (part, span_start, span_end, part_cells) in enumerate(parts):
            normalized = _normalize_text(part)
            if not normalized:
                continue
            content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            dedupe_key = (element.content_kind, content_hash)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            identity = (
                f"{source_kind}|{document_id}|{element.page}|{element.section}|"
                f"{element.content_kind}|{index}|{content_hash}"
            )
            chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    source_kind=source_kind,
                    document_id=document_id,
                    document_version=document_version,
                    page=element.page,
                    section=element.section,
                    content_kind=element.content_kind,
                    text=normalized,
                    content_hash=content_hash,
                    element_id=element.element_id,
                    parent_element_id=element.parent_element_id,
                    object_label=element.object_label,
                    printed_page=element.printed_page,
                    bbox=element.bbox,
                    text_span=TextSpan(start=span_start, end=span_end),
                    table_cells=part_cells,
                    crop_hash=element.crop_hash,
                    extraction_method=element.extraction_method,
                )
            )
    return chunks


def _coalesce_text_elements(
    elements: list[PageElement],
    *,
    document_id: str,
    max_tokens: int,
    tokenizer: Tokenizer | None,
) -> list[PageElement]:
    """Merge adjacent layout text blocks without crossing page/section boundaries."""

    result: list[PageElement] = []
    buffer: list[PageElement] = []
    ordinal = 0

    def flush() -> None:
        nonlocal ordinal
        if not buffer:
            return
        if len(buffer) == 1:
            result.append(buffer[0])
            buffer.clear()
            return
        text = _normalize_text("\n\n".join(item.text for item in buffer))
        boxes = [item.bbox for item in buffer if item.bbox is not None]
        bbox = None
        if len(boxes) == len(buffer) and boxes:
            page_width = max(float(item.page_width or item.x1) for item in boxes)
            page_height = max(float(item.page_height or item.y1) for item in boxes)
            bbox = _make_bbox(
                _union_bbox((item.x0, item.y0, item.x1, item.y1) for item in boxes),
                page_width=page_width,
                page_height=page_height,
            )
        first = buffer[0]
        element_id = _stable_element_id(
            document_id,
            first.page,
            "text-group",
            ordinal,
            text,
            bbox,
        )
        result.append(
            PageElement(
                page=first.page,
                section=first.section,
                content_kind="text",
                text=text,
                element_id=element_id,
                parent_element_id=first.element_id,
                printed_page=first.printed_page,
                bbox=bbox,
                text_span=TextSpan(start=0, end=len(text)),
                extraction_method="native_text",
            )
        )
        ordinal += 1
        buffer.clear()

    for element in elements:
        if element.content_kind != "text":
            flush()
            result.append(element)
            continue
        same_partition = bool(
            buffer
            and buffer[-1].page == element.page
            and buffer[-1].section == element.section
            and buffer[-1].printed_page == element.printed_page
        )
        candidate = _normalize_text(
            "\n\n".join([*(item.text for item in buffer), element.text])
        )
        if buffer and (not same_partition or _token_count(candidate, tokenizer) > max_tokens):
            flush()
        buffer.append(element)
    flush()
    return result


def _table_row_group_chunks(
    element: PageElement,
    *,
    max_tokens: int,
    hard_limit_tokens: int,
    tokenizer: Tokenizer | None,
) -> list[tuple[str, int, int, list[TableCellRef]]]:
    """Split Markdown tables by rows while repeating their header in every group."""

    if _token_count(element.text, tokenizer) <= max_tokens:
        return [(element.text, 0, len(element.text), element.table_cells)]
    lines = element.text.splitlines()
    if len(lines) < 3 or not re.match(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+", lines[1]):
        # A non-Markdown visual transcription is kept as one independent element;
        # the BGE runtime applies the hard truncation guard.
        return [(element.text, 0, len(element.text), element.table_cells)]
    header = "\n".join(lines[:2])
    header_tokens = _token_count(header, tokenizer)
    if header_tokens >= hard_limit_tokens:
        return [(element.text, 0, len(element.text), element.table_cells)]

    groups: list[tuple[str, int, int, list[TableCellRef]]] = []
    rows: list[tuple[int, str]] = []

    def flush() -> None:
        if not rows:
            return
        selected_rows = {0, *(row_index for row_index, _ in rows)}
        value = header + "\n" + "\n".join(line for _, line in rows)
        groups.append(
            (
                value,
                0,
                len(element.text),
                [cell for cell in element.table_cells if cell.row_index in selected_rows],
            )
        )
        rows.clear()

    for line_index, line in enumerate(lines[2:], start=2):
        row_index = line_index - 1
        candidate = header + "\n" + "\n".join(
            [*(value for _, value in rows), line]
        )
        if rows and _token_count(candidate, tokenizer) > max_tokens:
            flush()
            candidate = header + "\n" + line
        if _token_count(candidate, tokenizer) > hard_limit_tokens:
            # Very wide single rows are preserved as their own group so no cell
            # value is silently truncated; the later index guard fails closed.
            flush()
            rows.append((row_index, line))
            flush()
            continue
        rows.append((row_index, line))
    flush()
    return groups or [(element.text, 0, len(element.text), element.table_cells)]


def _pdf_page_elements(
    page: Any,
    *,
    page_number: int,
    document_id: str,
    current_section: str | None,
) -> tuple[list[PageElement], str | None]:
    """Extract ordered layout blocks without discarding source coordinates."""

    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    try:
        printed_page = str(page.get_label() or page_number)
    except Exception:  # pragma: no cover - older PyMuPDF builds
        printed_page = str(page_number)
    payload = page.get_text("dict", sort=True)
    elements: list[PageElement] = []
    ordinal = 0

    for block in payload.get("blocks", []):
        if int(block.get("type", 0)) != 0:
            continue
        line_records: list[tuple[str, tuple[float, float, float, float]]] = []
        for line in block.get("lines", []):
            text = "".join(str(span.get("text", "")) for span in line.get("spans", []))
            text = _normalize_text(text)
            if not text:
                continue
            raw_bbox = line.get("bbox") or block.get("bbox")
            if not raw_bbox or len(raw_bbox) != 4:
                continue
            line_records.append((text, tuple(float(value) for value in raw_bbox)))
        if not line_records:
            continue

        segment_lines: list[tuple[str, tuple[float, float, float, float]]] = []

        def flush_segment(kind: str = "text") -> None:
            nonlocal ordinal
            if not segment_lines:
                return
            value = _normalize_text("\n".join(item[0] for item in segment_lines))
            bbox = _make_bbox(
                _union_bbox(item[1] for item in segment_lines),
                page_width=page_width,
                page_height=page_height,
            )
            match = CAPTION_RE.match(value) if kind == "caption" else None
            element_id = _stable_element_id(
                document_id, page_number, kind, ordinal, value, bbox
            )
            elements.append(
                PageElement(
                    page=page_number,
                    section=current_section,
                    content_kind=kind,
                    text=value,
                    element_id=element_id,
                    object_label=_caption_label(match) if match else None,
                    printed_page=printed_page,
                    bbox=bbox,
                    text_span=TextSpan(start=0, end=len(value)),
                    extraction_method="native_text",
                )
            )
            ordinal += 1
            segment_lines.clear()

        for line_index, (line_text, line_bbox) in enumerate(line_records):
            caption_match = CAPTION_RE.match(line_text)
            if caption_match:
                flush_segment()
                segment_lines.extend(line_records[line_index:])
                flush_segment("caption")
                break
            if _is_heading(line_text):
                flush_segment()
                current_section = line_text
                continue
            segment_lines.append((line_text, line_bbox))
        else:
            flush_segment()

    return elements, current_section


def _make_bbox(
    values: tuple[float, float, float, float],
    *,
    page_width: float,
    page_height: float,
) -> BoundingBox:
    x0, y0, x1, y1 = values
    x0 = min(max(0.0, x0), max(0.0, page_width - 0.01))
    y0 = min(max(0.0, y0), max(0.0, page_height - 0.01))
    x1 = min(max(x0 + 0.01, x1), page_width)
    y1 = min(max(y0 + 0.01, y1), page_height)
    return BoundingBox(
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        page_width=page_width,
        page_height=page_height,
    )


def _union_bbox(
    values: Sequence[tuple[float, float, float, float]] | Any,
) -> tuple[float, float, float, float]:
    boxes = list(values)
    return (
        min(item[0] for item in boxes),
        min(item[1] for item in boxes),
        max(item[2] for item in boxes),
        max(item[3] for item in boxes),
    )


def _caption_label(match: re.Match[str] | None) -> str | None:
    if match is None:
        return None
    kind = match.group("kind")
    normalized_kind = "Figure" if kind.lower().startswith("fig") else "Table"
    return f"{normalized_kind} {match.group('number')}"


def _stable_element_id(
    document_id: str,
    page: int,
    kind: str,
    ordinal: int,
    text: str,
    bbox: BoundingBox | None,
) -> str:
    bbox_value = (
        f"{bbox.x0:.2f},{bbox.y0:.2f},{bbox.x1:.2f},{bbox.y1:.2f}" if bbox else "none"
    )
    payload = f"{document_id}|{page}|{kind}|{ordinal}|{bbox_value}|{text}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    safe_document = re.sub(r"[^A-Za-z0-9._-]+", "-", document_id)[:32] or "document"
    return f"elem-{safe_document}-p{page:04d}-{kind}-{ordinal:03d}-{digest}"


def _nearest_caption(
    captions: list[PageElement],
    *,
    bbox: BoundingBox,
    expected_kind: str,
) -> PageElement | None:
    compatible = [
        item
        for item in captions
        if item.bbox is not None
        and item.object_label is not None
        and item.object_label.lower().startswith(expected_kind.lower())
    ]
    if not compatible:
        return None

    def distance(item: PageElement) -> float:
        assert item.bbox is not None
        vertical = min(abs(item.bbox.y0 - bbox.y1), abs(bbox.y0 - item.bbox.y1))
        overlap = max(0.0, min(item.bbox.x1, bbox.x1) - max(item.bbox.x0, bbox.x0))
        width = max(1.0, min(item.bbox.x1 - item.bbox.x0, bbox.x1 - bbox.x0))
        return vertical + (0.0 if overlap / width >= 0.25 else 144.0)

    winner = min(compatible, key=distance)
    return winner if distance(winner) <= 180.0 else None


def _is_useful_table(rows: list[list[object | None]], *, has_table_caption: bool) -> bool:
    cleaned = [row for row in rows if row]
    if len(cleaned) < 2:
        return False
    width = max((len(row) for row in cleaned), default=0)
    if width < 2:
        return False
    cells = [str(cell).strip() for row in cleaned for cell in row if cell is not None]
    non_empty = [cell for cell in cells if cell]
    total_slots = len(cleaned) * width
    if total_slots == 0 or len(non_empty) / total_slots < 0.35:
        return False
    first_row = cleaned[0]
    header_non_empty = sum(bool(str(cell).strip()) for cell in first_row if cell is not None)
    if header_non_empty == 0:
        return False
    # Uncaptioned candidates need stronger evidence because plots and diagrams often
    # contain enough ruling lines to look like a table to pdfplumber.
    if not has_table_caption and len(non_empty) / total_slots < 0.60:
        return False
    return True


def _table_cell_refs(rows: list[list[object | None]]) -> list[TableCellRef]:
    header = [str(cell).replace("\n", " ").strip() if cell is not None else "" for cell in rows[0]]
    refs: list[TableCellRef] = []
    for row_index, row in enumerate(rows):
        cleaned = [str(cell).replace("\n", " ").strip() if cell is not None else "" for cell in row]
        row_header = cleaned[0] if cleaned else None
        for column_index, raw_text in enumerate(cleaned):
            if not raw_text:
                continue
            refs.append(
                TableCellRef(
                    row_index=row_index,
                    column_index=column_index,
                    raw_text=raw_text,
                    row_header=row_header if row_index > 0 else None,
                    column_header=header[column_index] if column_index < len(header) else None,
                )
            )
    return refs


def _text_elements(
    text: str,
    page: int,
    *,
    document_id: str = "document",
    printed_page: str | None = None,
) -> list[PageElement]:
    elements: list[PageElement] = []
    current_section: str | None = None
    buffer: list[str] = []
    ordinal = 0

    def flush() -> None:
        nonlocal ordinal
        if buffer:
            value = _normalize_text("\n".join(buffer))
            if value:
                element_id = _stable_element_id(
                    document_id, page, "text", ordinal, value, None
                )
                elements.append(
                    PageElement(
                        page=page,
                        section=current_section,
                        content_kind="text",
                        text=value,
                        element_id=element_id,
                        printed_page=printed_page or str(page),
                        text_span=TextSpan(start=0, end=len(value)),
                        extraction_method="native_text",
                    )
                )
                ordinal += 1
            buffer.clear()

    for line in text.splitlines():
        stripped = re.sub(r"^#{1,6}\s+", "", line.strip())
        if not stripped:
            buffer.append("")
            continue
        if CAPTION_RE.match(stripped):
            flush()
            match = CAPTION_RE.match(stripped)
            object_label = _caption_label(match) if match else None
            element_id = _stable_element_id(
                document_id, page, "caption", ordinal, stripped, None
            )
            elements.append(
                PageElement(
                    page=page,
                    section=current_section,
                    content_kind="caption",
                    text=stripped,
                    element_id=element_id,
                    object_label=object_label,
                    printed_page=printed_page or str(page),
                    text_span=TextSpan(start=0, end=len(stripped)),
                    extraction_method="native_text",
                )
            )
            ordinal += 1
        elif _is_heading(stripped):
            flush()
            current_section = stripped
        else:
            buffer.append(stripped)
    flush()
    return elements


def _is_heading(text: str) -> bool:
    if len(text) > 100:
        return False
    return bool(
        KNOWN_HEADING_RE.fullmatch(text)
        or ALL_CAPS_HEADING_RE.fullmatch(text)
        or NUMBERED_HEADING_RE.fullmatch(text)
    )


def _token_sliding_chunks(
    text: str,
    *,
    max_tokens: int,
    overlap_tokens: int,
    tokenizer: Tokenizer | None,
) -> list[tuple[str, int, int]]:
    if _token_count(text, tokenizer) <= max_tokens:
        return [(text, 0, len(text))]
    chunks: list[tuple[str, int, int]] = []
    start = 0
    while start < len(text):
        end = _max_token_end(text, start, max_tokens, tokenizer)
        if end < len(text):
            boundary = _preferred_boundary(text, start, end)
            if boundary > start and _token_count(text[start:boundary], tokenizer) >= max_tokens // 2:
                end = boundary
        raw = text[start:end]
        left_trim = len(raw) - len(raw.lstrip())
        right_trimmed = raw.rstrip()
        normalized_start = start + left_trim
        normalized_end = start + len(right_trimmed)
        if normalized_end > normalized_start:
            chunks.append((text[normalized_start:normalized_end], normalized_start, normalized_end))
        if end >= len(text):
            break
        next_start = _overlap_start(text, start, end, overlap_tokens, tokenizer)
        start = next_start if next_start > start else end
    return chunks


def _token_count(text: str, tokenizer: Tokenizer | None) -> int:
    if not text:
        return 0
    if tokenizer is None:
        return sum(1 for _ in FALLBACK_TOKEN_RE.finditer(text))
    return len(tokenizer(text))


def _max_token_end(
    text: str,
    start: int,
    max_tokens: int,
    tokenizer: Tokenizer | None,
) -> int:
    low, high = start + 1, len(text)
    best = low
    while low <= high:
        middle = (low + high) // 2
        if _token_count(text[start:middle], tokenizer) <= max_tokens:
            best = middle
            low = middle + 1
        else:
            high = middle - 1
    return best


def _preferred_boundary(text: str, start: int, end: int) -> int:
    lower = start + max(1, (end - start) // 2)
    candidates = [
        text.rfind("\n\n", lower, end),
        text.rfind("\n", lower, end),
        text.rfind(". ", lower, end),
        text.rfind("; ", lower, end),
        text.rfind(" ", lower, end),
    ]
    boundary = max(candidates)
    if boundary < 0:
        return end
    return boundary + (2 if text[boundary : boundary + 2] in {"\n\n", ". ", "; "} else 1)


def _overlap_start(
    text: str,
    chunk_start: int,
    chunk_end: int,
    overlap_tokens: int,
    tokenizer: Tokenizer | None,
) -> int:
    if overlap_tokens <= 0:
        return chunk_end
    low, high = chunk_start, chunk_end
    best = chunk_end
    while low <= high:
        middle = (low + high) // 2
        count = _token_count(text[middle:chunk_end], tokenizer)
        if count > overlap_tokens:
            low = middle + 1
        else:
            best = middle
            high = middle - 1
    return best


def _table_to_markdown(rows: list[list[object | None]]) -> str:
    cleaned = [
        [str(cell).replace("\n", " ").strip() if cell is not None else "" for cell in row]
        for row in rows
        if row
    ]
    if not cleaned:
        return ""
    width = max(len(row) for row in cleaned)
    normalized = [row + [""] * (width - len(row)) for row in cleaned]
    header = normalized[0]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in normalized[1:])
    return "\n".join(lines)


def _infer_metadata(
    text: str, elements: list[PageElement]
) -> tuple[str | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = next((line for line in lines[:12] if 8 <= len(line) <= 300), None)
    abstract_parts = [
        element.text
        for element in elements
        if element.content_kind == "text"
        and element.section
        and element.section.lower().startswith("abstract")
    ]
    abstract = _normalize_text("\n".join(abstract_parts))[:8000] if abstract_parts else None
    match = re.search(
        r"\bAbstract\b\s*[:—-]?\s*(.+?)(?=\n\s*(?:1\.?\s+)?Introduction\b)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match and not abstract:
        abstract = _normalize_text(match.group(1))[:8000]
    return title, abstract


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _looks_like_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(5) == b"%PDF-"
    except OSError:
        return False


def _kind_order(kind: str) -> int:
    return {
        "text": 0,
        "caption": 1,
        "table": 2,
        "figure": 3,
        "chart": 3,
        "diagram": 3,
    }.get(kind, 9)


def _element_sort_key(item: PageElement) -> tuple[int, float, float, int, str]:
    if item.bbox is None:
        return (item.page, float("inf"), float("inf"), _kind_order(item.content_kind), item.element_id or "")
    return (
        item.page,
        item.bbox.y0,
        item.bbox.x0,
        _kind_order(item.content_kind),
        item.element_id or "",
    )
