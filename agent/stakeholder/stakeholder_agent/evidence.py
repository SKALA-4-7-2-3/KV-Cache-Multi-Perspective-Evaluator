"""Deterministic, source-local quotation choices without rewriting source text."""

import re

from markdown_it import MarkdownIt

from .models import Assessment, Evidence

_MAX_OPTIONS = 80
_MAX_CHARS = 220
_MAX_WORDS = 25
_MIN_CHARS = 12
_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+|\n+")
# Counting numbers and hyphen-separated parts too is deliberately conservative.
_WORD = re.compile(r"[A-Za-z0-9]+")
_KEY = re.compile(r"Q[0-9]{3}\Z")
_URL = re.compile(r"https?://[^\s<>)\]]+")


def visible_quote(text: str) -> str:
    """Visible Markdown words only; a link's destination is not source evidence."""
    visible = []
    for token in MarkdownIt("commonmark").parseInline(text):
        for child in token.children or []:
            if child.type in {"text", "code_inline"}:
                visible.append(child.content)
            elif child.type in {"softbreak", "hardbreak"}:
                visible.append(" ")
    return " ".join(re.sub(r"https?://\S+", "", "".join(visible)).split())


def substantive_quote(text: str) -> bool:
    visible = visible_quote(text)
    if not any(char.isspace() for char in visible) and re.search(r"[/=?]", visible):
        return False
    return sum(char.isalnum() for char in visible) >= _MIN_CHARS


def source_quote_has_text(source_text: str, quote: str) -> bool:
    """Do not treat a chunk from the middle of a long URL as document prose."""
    if not quote or not substantive_quote(quote):
        return False
    urls = [match.span() for match in _URL.finditer(source_text)]
    start = source_text.find(quote)
    while start >= 0:
        end = start + len(quote)
        visible = list(quote)
        for left, right in urls:
            for position in range(max(start, left), min(end, right)):
                visible[position - start] = " "
        if substantive_quote("".join(visible)):
            return True
        start = source_text.find(quote, start + 1)
    return False


def _chunks(segment: str):
    remaining = segment.strip()
    while len(remaining) >= _MIN_CHARS:
        limit = min(len(remaining), _MAX_CHARS)
        for index, word in enumerate(_WORD.finditer(remaining)):
            if index == _MAX_WORDS:
                limit = min(limit, word.start())
                break
        if limit < len(remaining):
            # Prefer a complete word when a long sentence must be split. A
            # long unbroken token is still a literal, bounded source span.
            spaces = list(re.finditer(r"\s+", remaining[:limit + 1]))
            if spaces and spaces[-1].start() >= _MIN_CHARS:
                limit = spaces[-1].start()
        chunk = remaining[:limit].strip()
        if len(chunk) >= _MIN_CHARS:
            yield chunk
        remaining = remaining[limit:].lstrip()


def quote_options(evidence: Evidence) -> dict[str, str]:
    """Return up to 80 exact source spans keyed Q001, Q002, ... for this source.

    Sentence/newline boundaries take priority, followed by word boundaries for
    long segments. Whitespace inside a choice is preserved. The catalog depends
    only on the supplied excerpt; no model, network, or normalization is used.
    """
    options: dict[str, str] = {}
    seen: set[str] = set()
    for segment in _BOUNDARY.split(evidence.excerpt):
        for quote in _chunks(segment):
            if evidence.source_type == "web" and not source_quote_has_text(evidence.excerpt, quote):
                continue
            if quote in seen:
                continue
            seen.add(quote)
            options[f"Q{len(options) + 1:03d}"] = quote
            if len(options) == _MAX_OPTIONS:
                return options
    return options


def resolve_support_quotes(draft: Assessment, evidence: dict[str, Evidence]) -> None:
    """Replace only exact, known Q### choices belonging to the cited source.

    Literal quotations, unknown sources/keys, and malformed keys stay unchanged
    so the existing citation validator can reject unsupported material.
    """
    catalogs: dict[str, dict[str, str]] = {}
    for claim in draft.claims:
        for support in claim.supports:
            if not _KEY.fullmatch(support.quote) or support.evidence_id not in evidence:
                continue
            if support.evidence_id not in catalogs:
                catalogs[support.evidence_id] = quote_options(evidence[support.evidence_id])
            resolved = catalogs[support.evidence_id].get(support.quote)
            if resolved is not None:
                support.quote = resolved
