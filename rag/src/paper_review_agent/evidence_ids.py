"""Stable, human-readable evidence locator identifiers.

The parser intentionally uses content-derived ``elem-*`` identifiers internally.
Those are useful for joins, but they are poor citation labels.  This module keeps
the two concerns separate: source element IDs remain available on the locator,
while tables and figures receive a normalized object key such as ``table-01``.
"""

from __future__ import annotations

import hashlib
import re


EVIDENCE_ID_VERSION = "2.0.0"

_OBJECT_LABEL_RE = re.compile(
    r"^\s*(?P<kind>table|figure|fig\.?|chart|diagram)\s*"
    r"(?:no\.?\s*)?(?P<number>(?:[A-Za-z]\.)?\d+(?:\.\d+)*(?:[A-Za-z])?|"
    r"[A-Za-z]\d+|[IVXLCDM]+)\b",
    re.IGNORECASE,
)
_ROMAN_RE = re.compile(r"^[IVXLCDM]+$", re.IGNORECASE)
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def normalized_object_locator(
    object_label: str | None,
    *,
    content_kind: str,
    source_element_id: str,
) -> tuple[str, str | None]:
    """Return ``(object_key, normalized_label)`` for a visual object.

    Roman numerals are converted to Arabic numbers (``Table IV`` ->
    ``table-04``/``Table 4``).  Appendix-style labels remain unambiguous
    (``Table A.1`` -> ``table-a-01``).  An unlabeled visual uses a short digest
    of its stable parser element ID rather than a row-group chunk hash, so every
    chunk from the same object keeps the same key.
    """

    match = _OBJECT_LABEL_RE.match(object_label or "")
    if match is not None:
        kind = _normalized_kind(match.group("kind"))
        number_key, display_number = _normalized_number(match.group("number"))
        return f"{kind}-{number_key}", f"{_display_kind(kind)} {display_number}"

    kind = _normalized_kind(content_kind)
    digest = hashlib.sha256(source_element_id.encode("utf-8")).hexdigest()[:10]
    return f"{kind}-unlabeled-{digest}", None


def evidence_element_id(
    *,
    object_label: str | None,
    content_kind: str,
    source_element_id: str,
) -> tuple[str, str | None]:
    """Map visual/caption elements to citation IDs; retain text element IDs."""

    visual_kind = content_kind in {"table", "caption", "figure", "chart", "diagram"}
    if visual_kind and (object_label or content_kind != "caption"):
        return normalized_object_locator(
            object_label,
            content_kind=content_kind,
            source_element_id=source_element_id,
        )
    return source_element_id, None


def format_table_cell_suffix(row_index: int, column_index: int) -> str:
    """Format an exact, zero-based table-cell coordinate with two-digit minimums."""

    return f"cell-r{row_index:02d}-c{column_index:02d}"


def table_aggregate_suffix(
    *,
    chunk_text: str | None = None,
    chunk_text_length: int | None = None,
    span_end: int | None,
    row_indices: list[int],
    chunk_id: str,
) -> str:
    """Create a collision-free aggregate suffix for a whole table or row group.

    Row-group chunks repeat row zero (the header), so only data rows define the
    group range.  A digest fallback covers malformed/header-only groups.  Exact
    cell IDs intentionally omit the row-group suffix because original row/column
    coordinates are already unique within the page/object.
    """

    resolved_length = (
        chunk_text_length
        if chunk_text_length is not None
        else len(chunk_text or "")
    )
    if span_end is not None and span_end == resolved_length:
        return "whole"
    data_rows = sorted({value for value in row_indices if value > 0})
    if data_rows:
        return f"rows-r{data_rows[0]:02d}-r{data_rows[-1]:02d}"
    return f"rows-{chunk_id[:12]}"


def _normalized_kind(value: str) -> str:
    lowered = value.casefold().rstrip(".")
    if lowered == "fig" or lowered == "caption":
        return "figure"
    if lowered not in {"table", "figure", "chart", "diagram"}:
        return "figure"
    return lowered


def _display_kind(value: str) -> str:
    return {
        "table": "Table",
        "figure": "Figure",
        "chart": "Chart",
        "diagram": "Diagram",
    }[value]


def _normalized_number(value: str) -> tuple[str, str]:
    raw = value.strip().strip(".")
    if _ROMAN_RE.fullmatch(raw):
        try:
            number = _roman_to_int(raw)
        except ValueError:
            # Keep a deterministic label even for a publisher's non-canonical
            # Roman-like token instead of making ingestion fail.
            return raw.casefold(), raw.upper()
        return f"{number:02d}", str(number)

    numeric_suffix = re.fullmatch(r"(?P<number>\d+)(?P<suffix>[A-Za-z])", raw)
    if numeric_suffix:
        number = int(numeric_suffix.group("number"))
        suffix = numeric_suffix.group("suffix").casefold()
        return f"{number:02d}{suffix}", f"{number}{suffix}"

    alpha_prefix = re.fullmatch(r"(?P<prefix>[A-Za-z])(?P<number>\d+)", raw)
    if alpha_prefix:
        prefix = alpha_prefix.group("prefix")
        number = int(alpha_prefix.group("number"))
        return f"{prefix.casefold()}-{number:02d}", f"{prefix.upper()}{number}"

    pieces = re.findall(r"[A-Za-z]+|\d+", raw)
    if not pieces:
        safe = re.sub(r"[^a-z0-9]+", "-", raw.casefold()).strip("-") or "unknown"
        return safe, raw
    key_parts: list[str] = []
    display_parts: list[str] = []
    for piece in pieces:
        if piece.isdigit():
            number = int(piece)
            key_parts.append(f"{number:02d}")
            display_parts.append(str(number))
        else:
            key_parts.append(piece.casefold())
            display_parts.append(piece.upper())
    return "-".join(key_parts), ".".join(display_parts)


def _roman_to_int(value: str) -> int:
    total = 0
    previous = 0
    for character in reversed(value.upper()):
        current = _ROMAN_VALUES[character]
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    # Reject non-canonical subtractive spellings by round-tripping.  Falling
    # back to a sanitized token is less useful than accepting ambiguous labels,
    # so object labels parsed as Roman numerals are required to be canonical.
    if total <= 0 or _int_to_roman(total) != value.upper():
        raise ValueError(f"invalid Roman object label: {value}")
    return total


def _int_to_roman(value: int) -> str:
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    parts: list[str] = []
    remaining = value
    for amount, symbol in numerals:
        while remaining >= amount:
            parts.append(symbol)
            remaining -= amount
    return "".join(parts)
