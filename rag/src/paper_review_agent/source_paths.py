"""Deterministic local document path extraction for natural-language requests."""

from __future__ import annotations

import re
from pathlib import Path


_PATH_PATTERN = re.compile(
    r"(?P<quote>['\"])?(?P<path>(?:~|/|\.{1,2}/)?[^\n,'\"]+?\.(?:pdf|txt|md))(?P=quote)?",
    re.IGNORECASE,
)


def extract_source_paths(instruction: str, cwd: Path) -> list[Path]:
    """Extract document paths without treating surrounding text as commands."""

    results: list[Path] = []
    for match in _PATH_PATTERN.finditer(instruction):
        raw = match.group("path").strip().replace("\\_", "_").replace("\\ ", " ")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = cwd / path
        results.append(path.resolve())
    return list(dict.fromkeys(results))
