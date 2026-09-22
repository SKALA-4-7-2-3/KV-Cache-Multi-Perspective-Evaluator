"""Render supplied bibliographic facts without shortening titles or inventing fields."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def _value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(part for item in value if (part := _value(item)))
    text = " ".join(str(value or "").split())
    return "" if text.casefold() in {"unknown", "none", "null", "n/a", "미확인", "없음"} else text


def _url_key(value: Any) -> str:
    raw = _value(value)
    parts = urlsplit(raw)
    if parts.netloc.lower() in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        match = re.fullmatch(r"/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?/?", parts.path)
        if match:
            return "https://arxiv.org/abs/" + match.group(1)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def normalize_reference(record: dict[str, Any], overrides: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Apply caller-supplied URL metadata; preserve absent fields and citation identity."""
    result = dict(record)
    overridden = set(result.get("_reference_override_fields", []))
    if overrides:
        key = _url_key(record.get("url"))
        for url, metadata in overrides.items():
            if key and _url_key(url) == key and isinstance(metadata, dict):
                supplied = {name: value for name, value in metadata.items()
                            if name not in {"citation_key", "reference_id", "url"}}
                result.update(supplied)
                overridden.update(supplied)
                result["_reference_override_fields"] = sorted(overridden)
                break
    aliases = {
        "authors_or_organization": ("applicant", "assignee", "authors", "author", "organization", "publisher"),
        "publication_date": ("published_at", "date"),
        "venue_or_site": ("journal", "conference", "site", "publisher"),
        "publication_number": ("patent_number", "application_number"),
        "pages": ("page_range",),
        "issue": ("number",),
    }
    for target, candidates in aliases.items():
        if target not in overridden and not _value(result.get(target)):
            for candidate in candidates:
                if _value(result.get(candidate)):
                    result[target] = result[candidate]
                    break
    url = _value(result.get("url"))
    arxiv = re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5}(?:v\d+)?)", url)
    if arxiv and not _value(result.get("arxiv_id")):
        result["arxiv_id"] = arxiv.group(1)
    kind = _value(result.get("kind") or result.get("source_type")).lower()
    if _value(result.get("publication_number")) or kind in {"patent", "특허"} or "patents.google.com" in url:
        result["kind"] = "patent"
    elif arxiv or _value(result.get("arxiv_id")) or kind in {"paper", "journal", "conference", "article", "논문"}:
        result["kind"] = "paper"
    else:
        result["kind"] = "web"
    return result


def _latex_text(value: Any) -> str:
    substitutions = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
                     "%": r"\%", "&": r"\&", "#": r"\#", "$": r"\$",
                     "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
                     "<": r"\textless{}", ">": r"\textgreater{}"}
    return "".join(substitutions.get(char, char) for char in _value(value))


def _source_url(url: str) -> str:
    visible = "".join(_latex_text(char) + (r"\allowbreak{}" if char in "/?&=-_." else "") for char in url)
    label = r"\texttt{" + visible + "}"
    return r"\href{" + _latex_text(url) + "}{" + label + "}" if url.startswith(("https://", "http://")) else label


def _date(record: dict[str, Any], precision: int) -> str:
    raw = _value(record.get("publication_date")) or _value(record.get("year"))
    match = re.match(r"(\d{4})(?:[-/.](\d{1,2})(?:[-/.](\d{1,2}))?)?", raw)
    if not match:
        return ""
    parts = [part.zfill(2) for part in match.groups() if part]
    return "-".join(parts[:precision])


def format_reference(record: dict[str, Any]) -> str:
    """Return one LaTeX entry body; the caller supplies its bibitem and citation key."""
    record = normalize_reference(record)
    kind = record["kind"]
    author = _latex_text(record.get("authors_or_organization")) or "작성자 미상"
    date = _date(record, {"paper": 1, "patent": 2, "web": 3}[kind])
    lead = author + "(" + (date or ("연도 미상" if kind == "paper" else "발행일 미상")) + ")"
    title = _latex_text(record.get("title")) or "제목 미확인"
    venue = _latex_text(record.get("venue_or_site"))
    url = _value(record.get("url"))
    if kind == "paper":
        arxiv = _value(record.get("arxiv_id"))
        venue = "arXiv" if arxiv else venue
        details = [r"\textit{" + venue + "}" ] if venue else []
        if arxiv:
            details.append(_latex_text(re.sub(r"^arxiv:\s*", "", arxiv, flags=re.I)))
        else:
            volume, issue = _latex_text(record.get("volume")), _latex_text(record.get("issue"))
            if volume or issue:
                details.append(volume + ("(" + issue + ")" if issue else ""))
            if _value(record.get("pages")):
                details.append(_latex_text(record["pages"]))
        parts = [lead, title, ", ".join(details)]
        if not url and _value(record.get("doi")):
            doi = _value(record["doi"])
            url = doi if doi.startswith("https://") else "https://doi.org/" + doi.removeprefix("doi:").strip()
    elif kind == "patent":
        details = [r"\textit{" + title + "}"]
        if _value(record.get("publication_number")):
            details.append(_latex_text(record["publication_number"]))
        parts = [lead, ", ".join(details)]
    else:
        parts = [lead, r"\textit{" + title + "}", venue]
    entry = " ".join(
        part if re.search(r"[.!?]\}*$", part) else part + "."
        for part in parts if part
    )
    if url:
        if kind == "patent" or (kind == "web" and venue):
            entry = entry[:-1] + ", " + _source_url(url) + "."
        else:
            entry += " " + _source_url(url) + "."
    return entry
