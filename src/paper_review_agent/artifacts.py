"""Small, durable file helpers used by the technical-research pipeline."""

from __future__ import annotations

import uuid
from pathlib import Path


def atomic_write(path: Path, data: bytes) -> None:
    """Write bytes through a sibling temporary file and publish atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
