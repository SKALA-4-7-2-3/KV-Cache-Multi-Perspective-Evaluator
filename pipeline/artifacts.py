"""Atomic, hash-checked references and completion caches for one run directory."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from threading import RLock


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def fingerprint(root):
    paths = [p for base in ("pipeline", "agent", "report/src") for p in (root/base).rglob("*")
             if p.is_file() and p.suffix in {".py", ".md", ".json"} and not any(
                 part in {".venv", "__pycache__", "output", "outputs", "tests", "examples"} for part in p.parts)]
    paths += [p for p in (root/"uv.lock", root/"pyproject.toml") if p.exists()]
    return digest({str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in sorted(paths)})


class ArtifactStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def _path(self, relative):
        path = (self.root/relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Artifact path escapes the run directory")
        return path

    def put(self, relative, value):
        path = self._path(relative)
        body = (json.dumps(value, ensure_ascii=False, indent=2, default=str)+"\n").encode()
        with self.lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix+".tmp")
            temporary.write_bytes(body)
            temporary.replace(path)
        return {"relative_path": str(path.relative_to(self.root)), "sha256": sha256(body).hexdigest(),
                "media_type": "application/json", "schema_version": "1.0"}

    def get(self, ref):
        body = self._path(ref["relative_path"]).read_bytes()
        if sha256(body).hexdigest() != ref["sha256"]:
            raise ValueError(f"Artifact changed: {ref['relative_path']}")
        return json.loads(body)

    def cached(self, name, stamp, operation, *, validate=None):
        path = self._path(f"cache/{name}.json")
        with self.lock:
            if path.exists():
                cached = json.loads(path.read_text())
                if cached["stamp"] == stamp:
                    try:
                        value = self.get(cached["ref"])
                        if validate is None or validate(value):
                            return value, cached["ref"], True
                    except (ValueError, FileNotFoundError):
                        pass
        result = operation()
        ref = self.put(f"artifacts/{name}-{stamp[:16]}.json", result)
        self.put(f"cache/{name}.json", {"stamp": stamp, "ref": ref})
        return result, ref, False

    def event(self, event, **fields):
        from datetime import datetime, timezone
        with self.lock:
            with self._path("events.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"event":event, "timestamp":datetime.now(timezone.utc).isoformat(), **fields},
                                   ensure_ascii=False, default=str)+"\n")

    def invalidate(self, stages):
        for path in (self.root/"cache").glob("*.json"):
            if any(path.stem == stage or path.stem.startswith(stage+"-") for stage in stages):
                path.unlink()
