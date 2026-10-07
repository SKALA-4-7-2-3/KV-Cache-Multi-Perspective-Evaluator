"""Atomic, hash-checked references and completion caches for one run directory."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from threading import RLock


# Runtime/test caches are generated data, even when their files use source-like
# extensions. Use the same exclusions for run and accepted-worker fingerprints.
_FINGERPRINT_EXCLUDED_PARTS = {
    ".venv", "__pycache__", "output", "outputs", "tests", "examples",
    ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git",
}


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def fingerprint(root):
    paths = [p for base in ("pipeline", "agent", "report/src") for p in (root/base).rglob("*")
             if p.is_file() and p.suffix in {".py", ".md", ".json"} and not any(
                 part in _FINGERPRINT_EXCLUDED_PARTS for part in p.parts)]
    paths += [p for p in (root/"uv.lock", root/"pyproject.toml") if p.exists()]
    return digest({str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in sorted(paths)})


def role_fingerprints(root):
    """Only result-producing worker sources invalidate an accepted role result.

    Input identity and artifact hashes are checked separately. Report/Judge edits
    cannot invalidate an unchanged successful research worker.
    """
    common = [root / p for p in ("pipeline/__init__.py", "pipeline/runtime.py",
        "pipeline/worker_adapters.py", "pipeline/contracts.py", "pipeline/research_input.py",
        "pipeline/inputs.py", "pipeline/governance.py", "pyproject.toml", "uv.lock")]
    if (root / "pipeline/codex_provider.py").is_file():
        common.append(root / "pipeline/codex_provider.py")
    result = {}
    for role in ("domain", "market", "stakeholders"):
        directory = root / "agent" / ("stakeholder" if role == "stakeholders" else role)
        paths = common + [p for p in directory.rglob("*") if p.is_file()
            and p.suffix in {".py", ".md", ".json"} and not any(
                part in _FINGERPRINT_EXCLUDED_PARTS for part in p.parts)]
        result[role] = digest({str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in sorted(paths)})
    return result


def stage_fingerprint(root, name):
    """Hash only source dependencies that can change one persisted stage result."""
    stage = name.split("-", 1)[0]
    common = [root / relative for relative in (
        "pipeline/__init__.py", "pipeline/artifacts.py", "pipeline/governance.py", "pipeline/contracts.py",
        "pipeline/codex_provider.py",
        "pipeline/research_input.py", "pipeline/inputs.py", "pyproject.toml", "uv.lock",
    )]

    def sources(directory):
        return [path for path in directory.rglob("*") if path.is_file()
                and path.suffix in {".py", ".md", ".json"}
                and not any(part in _FINGERPRINT_EXCLUDED_PARTS for part in path.parts)]

    review_sources = sources(root / "agent/review/team_review")
    report_sources = sources(root / "report/src")
    relevant = {
        "trl": [root / "pipeline/trl.py"] + [root / f"agent/review/team_review/{file}"
            for file in ("__init__.py", "rubric.py", "schema.py", "contract.py", "review.py")],
        "review": [root / "pipeline/review_bridge.py"] + review_sources,
        "report": [root / "pipeline/reporting.py", root / "pipeline/reference_metadata.json"] + report_sources,
        "quality": [root / "pipeline/report_quality.py"] + report_sources,
    }
    if stage not in relevant:
        return fingerprint(root)
    paths = {path for path in common + relevant[stage] if path.exists() and path.is_file()}
    return digest({str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
                   for path in sorted(paths)})


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
