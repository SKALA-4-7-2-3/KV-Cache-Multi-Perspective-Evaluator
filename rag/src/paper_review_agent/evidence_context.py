"""Deterministic context expansion for caption-linked tables and figures."""

from __future__ import annotations

from collections.abc import Iterable

from paper_review_agent.schemas import Chunk


_VISUAL_KINDS = {"table", "caption", "figure", "chart", "diagram"}
_CONTEXT_KINDS = {"text", "table", "caption"}


def expand_caption_linked_context(
    selected: Iterable[Chunk],
    document_chunks: Iterable[Chunk],
    *,
    max_neighbors_per_anchor: int = 2,
) -> list[Chunk]:
    """Add the closest native context surrounding each selected visual.

    PDF captions are frequently split across layout blocks.  A selected table
    may therefore contain exact cells while its caption ends mid-condition, or
    the paragraph immediately above it may hold the batch/context matrix.  This
    expansion is local, deterministic and bounded: it adds at most two nearest
    same-page text/caption/table chunks per selected visual anchor.
    """

    base = _unique_chunks(selected)
    if max_neighbors_per_anchor <= 0:
        return base
    all_chunks = list(document_chunks)
    known = {item.chunk_id for item in base}
    added: list[Chunk] = []
    anchors = [item for item in base if item.content_kind != "caption" and item.content_kind in _VISUAL_KINDS]
    if not anchors:
        anchors = [item for item in base if item.content_kind == "caption"]
    for anchor in anchors:
        candidates: list[tuple[tuple[int, float, str], Chunk]] = []
        for candidate in all_chunks:
            if (
                candidate.chunk_id in known
                or candidate.document_id != anchor.document_id
                or candidate.document_version != anchor.document_version
                or candidate.page != anchor.page
                or candidate.content_kind not in _CONTEXT_KINDS
            ):
                continue
            relation = _relation_rank(anchor, candidate)
            distance = _vertical_distance(anchor, candidate)
            # Without a structural link or usable geometry there is no safe
            # reason to pull an arbitrary same-page paragraph into the prompt.
            if relation >= 3 and distance == float("inf"):
                continue
            candidates.append(((relation, distance, candidate.chunk_id), candidate))
        candidates.sort(key=lambda item: item[0])
        for _, candidate in candidates[:max_neighbors_per_anchor]:
            if candidate.chunk_id in known:
                continue
            known.add(candidate.chunk_id)
            added.append(candidate)
    return [*base, *added]


def _relation_rank(anchor: Chunk, candidate: Chunk) -> int:
    if anchor.element_id and candidate.parent_element_id == anchor.element_id:
        return 0
    if candidate.element_id and anchor.parent_element_id == candidate.element_id:
        return 0
    if (
        anchor.parent_element_id
        and candidate.parent_element_id
        and anchor.parent_element_id == candidate.parent_element_id
    ):
        return 0
    if (
        anchor.object_label
        and candidate.object_label
        and anchor.object_label.casefold() == candidate.object_label.casefold()
    ):
        return 1
    if anchor.object_label and anchor.object_label.casefold() in candidate.text.casefold():
        return 2
    return 3


def _vertical_distance(left: Chunk, right: Chunk) -> float:
    if left.bbox is None or right.bbox is None:
        return float("inf")
    if right.bbox.y1 < left.bbox.y0:
        return left.bbox.y0 - right.bbox.y1
    if left.bbox.y1 < right.bbox.y0:
        return right.bbox.y0 - left.bbox.y1
    return 0.0


def _unique_chunks(values: Iterable[Chunk]) -> list[Chunk]:
    unique: list[Chunk] = []
    seen: set[str] = set()
    for item in values:
        if item.chunk_id in seen:
            continue
        seen.add(item.chunk_id)
        unique.append(item)
    return unique
