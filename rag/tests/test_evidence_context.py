from __future__ import annotations

import hashlib

from paper_review_agent.evidence_context import expand_caption_linked_context
from paper_review_agent.schemas import BoundingBox, Chunk


def _chunk(
    chunk_id: str,
    text: str,
    *,
    kind: str = "text",
    y0: float,
    y1: float,
    object_label: str | None = None,
    element_id: str | None = None,
    parent_element_id: str | None = None,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_kind="paper",
        document_id="paper-a",
        document_version="a" * 64,
        page=3,
        section="Results",
        content_kind=kind,
        text=text,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        object_label=object_label,
        element_id=element_id or chunk_id,
        parent_element_id=parent_element_id,
        bbox=BoundingBox(
            x0=40,
            y0=y0,
            x1=300,
            y1=y1,
            page_width=612,
            page_height=792,
        ),
    )


def test_selected_table_adds_split_caption_conditions_above_and_below():
    before = _chunk(
        "before",
        "TABLE I summarizes results. All configurations use batch sizes "
        "{1, 2, 8, 16, 32}.",
        y0=100,
        y1=220,
    )
    caption = _chunk(
        "caption",
        "TABLE I. TESTING MATRIX ... BATCH SIZES {1,",
        kind="caption",
        y0=236,
        y1=253,
        object_label="Table I",
        element_id="caption-1",
    )
    continuation = _chunk(
        "continuation",
        "2, 8, 16, 32}. Standard contexts: 1K-100K; Maverick 1M; Scout 4M.",
        y0=253.2,
        y1=270,
    )
    table = _chunk(
        "table",
        "| Model | Platform | Host Memory | Disk Storage |",
        kind="table",
        y0=275,
        y1=430,
        object_label="Table I",
        parent_element_id="caption-1",
    )
    unrelated = _chunk("unrelated", "unrelated footer", y0=700, y1=720)

    expanded = expand_caption_linked_context(
        [table, caption], [before, caption, continuation, table, unrelated]
    )

    ids = {item.chunk_id for item in expanded}
    assert {"table", "caption", "before", "continuation"}.issubset(ids)
    assert "unrelated" not in ids
    assert len(ids) == 4


def test_context_expansion_is_bounded_and_deduplicated():
    caption = _chunk(
        "caption",
        "Table 1. Results",
        kind="caption",
        y0=200,
        y1=220,
        object_label="Table 1",
    )
    neighbors = [
        _chunk(f"n{index}", f"neighbor {index}", y0=221 + index, y1=222 + index)
        for index in range(5)
    ]

    expanded = expand_caption_linked_context(
        [caption, caption], [caption, *neighbors], max_neighbors_per_anchor=2
    )

    assert len(expanded) == 3
    assert len({item.chunk_id for item in expanded}) == 3
