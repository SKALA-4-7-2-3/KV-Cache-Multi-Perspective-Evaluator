from __future__ import annotations

import pytest

from paper_review_agent.config import AppConfig
from paper_review_agent.documents import (
    LocalDocumentService,
    _is_useful_table,
    _coalesce_text_elements,
    _text_elements,
    chunk_elements,
)
from paper_review_agent.exceptions import IngestionError
from paper_review_agent.schemas import PageElement, TableCellRef


def test_caption_and_text_are_separate_chunks():
    elements = [
        PageElement(page=1, section="Method", content_kind="text", text="A" * 200),
        PageElement(
            page=1,
            section="Method",
            content_kind="caption",
            text="Figure 1: System overview",
        ),
    ]
    chunks = chunk_elements(
        elements,
        source_kind="paper",
        document_id="paper-1",
        chunk_chars=100,
        overlap_chars=20,
    )
    assert {chunk.content_kind for chunk in chunks} == {"text", "caption"}
    assert all(chunk.page == 1 for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_tokenizer_injection_preserves_source_spans():
    text = "alpha beta gamma delta epsilon zeta eta theta"
    elements = [
        PageElement(page=1, section="Method", content_kind="text", text=text)
    ]

    chunks = chunk_elements(
        elements,
        source_kind="paper",
        document_id="paper-token",
        chunk_chars=100,
        overlap_chars=20,
        tokenizer=lambda value: value.split(),
        chunk_tokens=3,
        overlap_tokens=1,
    )

    assert len(chunks) >= 3
    assert all(len(chunk.text.split()) <= 3 for chunk in chunks)
    for chunk in chunks:
        assert chunk.text_span is not None
        assert text[chunk.text_span.start : chunk.text_span.end] == chunk.text


def test_table_quality_filter_rejects_empty_graph_grid():
    assert not _is_useful_table(
        [[None, None, None], ["", "", ""]],
        has_table_caption=False,
    )
    assert _is_useful_table(
        [["Method", "Score"], ["RDKV", "91.2"]],
        has_table_caption=True,
    )


def test_long_table_is_split_by_rows_with_repeated_header():
    text = "| Method | Score |\n| --- | --- |\n" + "\n".join(
        f"| method-{index} | {index}.0 |" for index in range(1, 8)
    )
    cells = [
        TableCellRef(row_index=0, column_index=0, raw_text="Method"),
        TableCellRef(row_index=0, column_index=1, raw_text="Score"),
        *[
            TableCellRef(row_index=index, column_index=1, raw_text=f"{index}.0")
            for index in range(1, 8)
        ],
    ]
    chunks = chunk_elements(
        [
            PageElement(
                page=1,
                section="Results",
                content_kind="table",
                text=text,
                table_cells=cells,
            )
        ],
        source_kind="paper",
        document_id="paper-table",
        chunk_chars=100,
        overlap_chars=20,
        tokenizer=lambda value: value.split(),
        chunk_tokens=14,
        overlap_tokens=2,
        hard_limit_tokens=18,
    )

    assert len(chunks) > 1
    assert all(chunk.text.startswith("| Method | Score |\n| --- | --- |") for chunk in chunks)
    assert all(any(cell.row_index == 0 for cell in chunk.table_cells) for chunk in chunks)


def test_adjacent_text_blocks_coalesce_without_crossing_page_or_section():
    elements = [
        PageElement(page=1, section="Method", content_kind="text", text="alpha beta"),
        PageElement(page=1, section="Method", content_kind="text", text="gamma delta"),
        PageElement(page=1, section="Results", content_kind="text", text="epsilon"),
        PageElement(page=2, section="Results", content_kind="text", text="zeta"),
    ]

    grouped = _coalesce_text_elements(
        elements,
        document_id="paper-group",
        max_tokens=8,
        tokenizer=lambda value: value.split(),
    )

    assert len(grouped) == 3
    assert grouped[0].text == "alpha beta\n\ngamma delta"
    assert grouped[0].element_id and "text-group" in grouped[0].element_id
    assert grouped[1].section == "Results"
    assert grouped[2].page == 2


def test_mixed_case_title_and_sentences_are_not_misclassified_as_headings():
    elements = _text_elements(
        "Denoising Diffusion Probabilistic Models\n"
        "Jonathan Ho\n"
        "Abstract\n"
        "We present high quality image synthesis results using diffusion models.\n"
        "1 Introduction\n"
        "Deep generative models have recently exhibited high quality samples.",
        page=1,
    )

    assert elements[0].text.startswith("Denoising Diffusion Probabilistic Models")
    assert elements[1].section == "Abstract"
    assert elements[2].section == "1 Introduction"


def test_too_short_text_is_rejected(tmp_path):
    source = tmp_path / "scan.txt"
    source.write_text("too short", encoding="utf-8")
    config = AppConfig(root_dir=tmp_path, min_text_chars=100, checkpoint_enabled=False)
    service = LocalDocumentService(config)
    with pytest.raises(IngestionError, match="OCR"):
        service.parse(
            source,
            document_id=None,
            source_kind="paper",
            enforce_quality=True,
        )


def test_pdf_page_text_and_caption_are_extracted(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    source = tmp_path / "paper.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Method\n" + "technical evidence " * 40)
    page.insert_text((72, 180), "Figure 1: System overview")
    document.save(source)
    document.close()

    config = AppConfig(root_dir=tmp_path, min_text_chars=50, checkpoint_enabled=False)
    parsed = LocalDocumentService(config).parse(
        source,
        document_id="pdf-paper",
        source_kind="paper",
        enforce_quality=True,
    )
    assert parsed.metadata.page_count == 1
    caption = next(item for item in parsed.elements if item.content_kind == "caption")
    assert caption.object_label == "Figure 1"
    assert caption.element_id
    assert caption.bbox is not None
    assert caption.printed_page == "1"
    assert caption.extraction_method == "native_text"
    assert any(item.page == 1 for item in parsed.chunks)
