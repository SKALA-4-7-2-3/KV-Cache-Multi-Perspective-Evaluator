"""Pinned local model snapshots and the BGE-M3 runtime adapter.

The analysis runtime never accepts a Hugging Face model identifier.  A model is
downloaded explicitly during setup, recorded in a small manifest, and loaded by
local path afterwards.  Heavy ML dependencies are intentionally imported only
inside the setup/runtime entry points so the rest of the package remains usable
without PyTorch or FlagEmbedding installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from paper_review_agent.artifacts import atomic_write
from paper_review_agent.exceptions import ConfigurationError, DependencyError, ProviderError

BGE_M3_MODEL_ID = "BAAI/bge-m3"
BGE_M3_DENSE_DIMENSION = 1024
BGE_M3_COLBERT_DIMENSION = 1024
MODEL_MANIFEST_NAME = ".paper-review-model.json"
MODEL_MANIFEST_SCHEMA_VERSION = "1.0.0"
_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True, slots=True)
class ModelSnapshot:
    """A verified, pinned model snapshot available on the local filesystem."""

    model_id: str
    revision: str
    path: Path
    manifest_sha256: str
    files_sha256: str
    file_hashes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BGEModelRuntimeConfig:
    """Settings for local-only BGE-M3 inference."""

    model_path: Path
    model_revision: str
    model_id: str = BGE_M3_MODEL_ID
    model_files_sha256: str | None = None
    device: Literal["auto", "cpu", "cuda"] = "auto"
    max_query_tokens: int = 128
    max_passage_tokens: int = 896
    cuda_batch_size: int = 8
    query_cache_size: int = 256

    def __post_init__(self) -> None:
        _reject_openai_embedding(self.model_id)
        if not _COMMIT_RE.fullmatch(self.model_revision):
            raise ConfigurationError("BGE-M3 model_revision은 40자리 고정 commit SHA여야 합니다.")
        if self.model_files_sha256 is not None and not re.fullmatch(
            r"[0-9a-fA-F]{64}", self.model_files_sha256
        ):
            raise ConfigurationError("model_files_sha256는 64자리 SHA-256이어야 합니다.")
        if not 1 <= self.max_query_tokens <= self.max_passage_tokens:
            raise ConfigurationError("max_query_tokens는 1 이상 max_passage_tokens 이하여야 합니다.")
        if not 1 <= self.max_passage_tokens <= 896:
            raise ConfigurationError(
                "BGE-M3 ColBERT 저장을 위해 max_passage_tokens는 896 이하여야 합니다."
            )
        if self.cuda_batch_size < 1:
            raise ConfigurationError("cuda_batch_size는 1 이상이어야 합니다.")
        if self.query_cache_size < 0:
            raise ConfigurationError("query_cache_size는 0 이상이어야 합니다.")

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ModelSnapshot,
        **overrides: object,
    ) -> BGEModelRuntimeConfig:
        """Build a runtime config from a previously verified local snapshot."""

        values: dict[str, object] = {
            "model_path": snapshot.path,
            "model_revision": snapshot.revision,
            "model_id": snapshot.model_id,
            "model_files_sha256": snapshot.files_sha256,
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class MultiRepresentation:
    """Dense, learned-sparse and ColBERT representations for one text."""

    dense: Any
    sparse_indices: Any
    sparse_values: Any
    colbert: Any


SnapshotDownloader = Callable[..., str]


def pull_pinned_snapshot(
    destination: Path,
    *,
    revision: str,
    model_id: str = BGE_M3_MODEL_ID,
    downloader: SnapshotDownloader | None = None,
) -> ModelSnapshot:
    """Download one immutable Hugging Face commit and write a local manifest.

    ``revision`` deliberately accepts only a 40-character commit hash.  Tags and
    branch names can move and therefore cannot participate in a reproducible
    retrieval profile.
    """

    _reject_openai_embedding(model_id)
    if not _COMMIT_RE.fullmatch(revision):
        raise ConfigurationError(
            "model revision은 이동 가능한 branch/tag가 아닌 40자리 commit SHA여야 합니다."
        )
    root = destination.expanduser().resolve()
    snapshot_dir = root / f"bge-m3-{revision[:12].lower()}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = snapshot_dir / MODEL_MANIFEST_NAME
    if manifest_path.is_file():
        return load_local_snapshot(
            snapshot_dir,
            expected_model_id=model_id,
            expected_revision=revision,
        )

    if downloader is None:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise DependencyError(
                "모델 설치에는 huggingface-hub가 필요합니다. 런타임은 다운로드를 수행하지 않습니다."
            ) from exc
        downloader = snapshot_download

    try:
        downloaded = downloader(
            repo_id=model_id,
            revision=revision,
            local_dir=str(snapshot_dir),
        )
    except Exception as exc:  # noqa: BLE001 - downloader implementations vary
        raise ProviderError(f"고정 BGE-M3 snapshot 다운로드 실패: {exc}") from exc

    resolved = Path(downloaded).expanduser().resolve()
    if not resolved.is_dir():
        raise ProviderError(f"다운로드된 model snapshot 경로가 디렉터리가 아닙니다: {resolved}")
    # ``local_dir`` should be honored. Refuse an unexpected path so runtime data
    # is never silently read from an ambient, mutable cache.
    if resolved != snapshot_dir:
        raise ProviderError(
            f"snapshot downloader가 지정한 local_dir 밖의 경로를 반환했습니다: {resolved}"
        )

    file_hashes = _snapshot_file_hashes(resolved)
    if not file_hashes:
        raise ProviderError("다운로드된 model snapshot에 검증할 파일이 없습니다.")
    files_sha256 = _file_hashes_fingerprint(file_hashes)
    payload = {
        "schema_version": MODEL_MANIFEST_SCHEMA_VERSION,
        "model_id": model_id,
        "revision": revision.lower(),
        "files_sha256": files_sha256,
        "file_hashes": file_hashes,
        "created_at": datetime.now(UTC).isoformat(),
    }
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    manifest_path = resolved / MODEL_MANIFEST_NAME
    atomic_write(manifest_path, raw)
    return ModelSnapshot(
        model_id=model_id,
        revision=revision.lower(),
        path=resolved,
        manifest_sha256=hashlib.sha256(raw).hexdigest(),
        files_sha256=files_sha256,
        file_hashes=file_hashes,
    )


def load_local_snapshot(
    model_path: Path,
    *,
    expected_model_id: str = BGE_M3_MODEL_ID,
    expected_revision: str | None = None,
    verify_files: bool = True,
) -> ModelSnapshot:
    """Validate a setup manifest without performing any network operation."""

    _reject_openai_embedding(expected_model_id)
    path = model_path.expanduser().resolve()
    if not path.is_dir():
        raise ConfigurationError(f"로컬 BGE-M3 model 경로가 없습니다: {path}")
    manifest_path = path / MODEL_MANIFEST_NAME
    if not manifest_path.is_file():
        raise ConfigurationError(
            f"로컬 model manifest가 없습니다. pull_pinned_snapshot을 먼저 실행하세요: {manifest_path}"
        )
    raw = manifest_path.read_bytes()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"model manifest JSON이 손상되었습니다: {exc}") from exc
    if payload.get("schema_version") != MODEL_MANIFEST_SCHEMA_VERSION:
        raise ConfigurationError("지원하지 않는 model manifest schema_version입니다.")
    if payload.get("model_id") != expected_model_id:
        raise ConfigurationError(
            f"model_id 불일치: expected={expected_model_id}, actual={payload.get('model_id')}"
        )
    revision = str(payload.get("revision", "")).lower()
    if not _COMMIT_RE.fullmatch(revision):
        raise ConfigurationError("model manifest revision이 고정 commit SHA가 아닙니다.")
    if expected_revision is not None and revision != expected_revision.lower():
        raise ConfigurationError(
            f"model revision 불일치: expected={expected_revision}, actual={revision}"
        )
    stored_hashes = payload.get("file_hashes")
    stored_fingerprint = str(payload.get("files_sha256", ""))
    if not isinstance(stored_hashes, dict) or not stored_hashes:
        raise ConfigurationError("model manifest에 file_hashes가 없습니다.")
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in stored_hashes.items()):
        raise ConfigurationError("model manifest file_hashes 형식이 잘못되었습니다.")
    canonical_fingerprint = _file_hashes_fingerprint(stored_hashes)
    if stored_fingerprint != canonical_fingerprint:
        raise ConfigurationError("model manifest files_sha256가 file_hashes와 일치하지 않습니다.")
    if verify_files:
        actual_hashes = _snapshot_file_hashes(path)
        if actual_hashes != stored_hashes:
            missing = sorted(set(stored_hashes) - set(actual_hashes))
            added = sorted(set(actual_hashes) - set(stored_hashes))
            changed = sorted(
                key
                for key in set(stored_hashes) & set(actual_hashes)
                if stored_hashes[key] != actual_hashes[key]
            )
            raise ConfigurationError(
                "로컬 model snapshot 파일 해시 불일치: "
                f"missing={missing[:3]}, added={added[:3]}, changed={changed[:3]}"
            )
    return ModelSnapshot(
        model_id=expected_model_id,
        revision=revision,
        path=path,
        manifest_sha256=hashlib.sha256(raw).hexdigest(),
        files_sha256=stored_fingerprint,
        file_hashes=dict(sorted(stored_hashes.items())),
    )


class LocalBgeM3Embedder:
    """Thread-safe local BGE-M3 tri-modal inference adapter.

    The constructor checks that ``model_path`` is an existing directory before
    importing FlagEmbedding. Consequently a remote model id can never be passed
    through to the underlying library by mistake.
    """

    model_id = BGE_M3_MODEL_ID
    dense_dimension = BGE_M3_DENSE_DIMENSION
    colbert_dimension = BGE_M3_COLBERT_DIMENSION

    def __init__(
        self,
        config: BGEModelRuntimeConfig,
        *,
        model_factory: Callable[..., object] | None = None,
        cuda_available: Callable[[], bool] | None = None,
    ) -> None:
        self.config = config
        self.model_id = config.model_id
        self.revision = config.model_revision.lower()
        self.files_sha256 = (
            config.model_files_sha256.lower() if config.model_files_sha256 else None
        )
        self.model_path = config.model_path.expanduser().resolve()
        if not self.model_path.is_dir():
            raise ConfigurationError(
                "BGE-M3 runtime은 remote model id를 허용하지 않습니다. "
                f"존재하는 로컬 디렉터리를 지정하세요: {self.model_path}"
            )

        self.device = _resolve_device(config.device, cuda_available)
        self.batch_size = 1 if self.device == "cpu" else config.cuda_batch_size
        self.use_fp16 = self.device == "cuda"
        # Runtime inference must never turn a missing local file into an ambient
        # network request. These variables are set before importing either
        # Transformers or FlagEmbedding.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        if model_factory is None:
            try:
                from FlagEmbedding import BGEM3FlagModel
            except ImportError as exc:
                raise DependencyError(
                    "로컬 BGE-M3 실행에는 FlagEmbedding과 PyTorch가 필요합니다."
                ) from exc
            model_factory = BGEM3FlagModel
        try:
            self._model = model_factory(
                str(self.model_path),
                devices=self.device,
                use_fp16=self.use_fp16,
            )
        except Exception as exc:  # noqa: BLE001 - backend exception types vary
            raise ProviderError(f"로컬 BGE-M3 model 로드 실패: {exc}") from exc
        self._lock = threading.RLock()
        self._query_cache: OrderedDict[str, MultiRepresentation] = OrderedDict()

    def embed_documents(self, texts: Sequence[str]) -> list[MultiRepresentation]:
        return self._encode(texts, max_length=self.config.max_passage_tokens)

    def embed_queries(self, texts: Sequence[str]) -> list[MultiRepresentation]:
        values: list[MultiRepresentation | None] = [None] * len(texts)
        missing_texts: list[str] = []
        missing_positions: dict[str, list[int]] = {}
        with self._lock:
            for index, text in enumerate(texts):
                cached = self._query_cache.get(text)
                if cached is not None:
                    self._query_cache.move_to_end(text)
                    values[index] = cached
                else:
                    missing_positions.setdefault(text, []).append(index)
                    if len(missing_positions[text]) == 1:
                        missing_texts.append(text)
            if missing_texts:
                encoded = self._encode_locked(
                    missing_texts,
                    max_length=self.config.max_query_tokens,
                )
                for text, representation in zip(missing_texts, encoded, strict=True):
                    for position in missing_positions[text]:
                        values[position] = representation
                    if self.config.query_cache_size:
                        self._query_cache[text] = representation
                        self._query_cache.move_to_end(text)
                        while len(self._query_cache) > self.config.query_cache_size:
                            self._query_cache.popitem(last=False)
        return [value for value in values if value is not None]

    def _encode(self, texts: Sequence[str], *, max_length: int) -> list[MultiRepresentation]:
        with self._lock:
            return self._encode_locked(texts, max_length=max_length)

    def _encode_locked(
        self, texts: Sequence[str], *, max_length: int
    ) -> list[MultiRepresentation]:
        if not texts:
            return []
        normalized = [str(text) for text in texts]
        if any(not text.strip() for text in normalized):
            raise ValueError("BGE-M3에 전달할 텍스트는 비어 있을 수 없습니다.")
        representations: list[MultiRepresentation] = []
        for offset in range(0, len(normalized), self.batch_size):
            batch = normalized[offset : offset + self.batch_size]
            try:
                output = self._model.encode(
                    batch,
                    batch_size=self.batch_size,
                    max_length=max_length,
                    return_dense=True,
                    return_sparse=True,
                    return_colbert_vecs=True,
                )
            except Exception as exc:  # noqa: BLE001 - backend exception types vary
                raise ProviderError(f"로컬 BGE-M3 embedding 실패: {exc}") from exc
            representations.extend(_coerce_bge_output(output, expected=len(batch)))
        return representations


def _coerce_bge_output(output: object, *, expected: int) -> list[MultiRepresentation]:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("BGE-M3 출력 처리에는 numpy가 필요합니다.") from exc
    if not isinstance(output, dict):
        raise ProviderError("BGE-M3 출력이 dict 형식이 아닙니다.")
    try:
        dense_values = output["dense_vecs"]
        sparse_values = output["lexical_weights"]
        colbert_values = output["colbert_vecs"]
    except KeyError as exc:
        raise ProviderError(f"BGE-M3 출력 필드가 누락되었습니다: {exc}") from exc
    if not (len(dense_values) == len(sparse_values) == len(colbert_values) == expected):
        raise ProviderError("BGE-M3 출력 개수가 입력 batch와 다릅니다.")

    result: list[MultiRepresentation] = []
    for dense_raw, sparse_raw, colbert_raw in zip(
        dense_values, sparse_values, colbert_values, strict=True
    ):
        dense = np.asarray(dense_raw, dtype=np.float32)
        colbert = np.asarray(colbert_raw, dtype=np.float32)
        if dense.shape != (BGE_M3_DENSE_DIMENSION,):
            raise ProviderError(f"BGE-M3 dense dimension 불일치: {dense.shape}")
        if colbert.ndim != 2 or colbert.shape[1] != BGE_M3_COLBERT_DIMENSION:
            raise ProviderError(f"BGE-M3 ColBERT dimension 불일치: {colbert.shape}")
        if not np.isfinite(dense).all() or not np.isfinite(colbert).all():
            raise ProviderError("BGE-M3 출력에 NaN 또는 infinity가 포함되어 있습니다.")
        if not isinstance(sparse_raw, dict):
            raise ProviderError("BGE-M3 lexical_weights가 dict 형식이 아닙니다.")
        pairs = sorted((int(token_id), float(weight)) for token_id, weight in sparse_raw.items())
        indices = np.asarray([token_id for token_id, _ in pairs], dtype=np.int32)
        weights = np.asarray([weight for _, weight in pairs], dtype=np.float32)
        if not np.isfinite(weights).all() or (weights < 0).any():
            raise ProviderError("BGE-M3 sparse weight가 유효하지 않습니다.")
        for array in (dense, indices, weights, colbert):
            array.setflags(write=False)
        result.append(
            MultiRepresentation(
                dense=dense,
                sparse_indices=indices,
                sparse_values=weights,
                colbert=colbert,
            )
        )
    return result


def _resolve_device(
    requested: Literal["auto", "cpu", "cuda"],
    cuda_available: Callable[[], bool] | None,
) -> Literal["cpu", "cuda"]:
    if requested == "cpu":
        return "cpu"
    if cuda_available is None:
        try:
            import torch
        except ImportError as exc:
            raise DependencyError("BGE-M3 device 확인에는 PyTorch가 필요합니다.") from exc
        cuda_available = torch.cuda.is_available
    available = bool(cuda_available())
    if requested == "cuda" and not available:
        raise ConfigurationError("CUDA device를 요청했지만 사용 가능한 CUDA GPU가 없습니다.")
    return "cuda" if available else "cpu"


def _reject_openai_embedding(value: str) -> None:
    normalized = value.strip().lower()
    if "openai" in normalized or normalized.startswith("text-embedding-"):
        raise ConfigurationError("OpenAI embedding model은 허용되지 않습니다.")
    if not normalized:
        raise ConfigurationError("embedding model id는 비어 있을 수 없습니다.")


def _snapshot_file_hashes(path: Path) -> dict[str, str]:
    """Hash immutable snapshot contents, excluding our manifest and HF cache metadata."""

    hashes: dict[str, str] = {}
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = file_path.relative_to(path)
        if (
            relative.name == MODEL_MANIFEST_NAME
            or relative.name.startswith(MODEL_MANIFEST_NAME + ".")
            or relative.parts[:1] == (".cache",)
        ):
            continue
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            while block := handle.read(8 * 1024 * 1024):
                digest.update(block)
        hashes[relative.as_posix()] = digest.hexdigest()
    return hashes


def _file_hashes_fingerprint(file_hashes: dict[str, str]) -> str:
    canonical = json.dumps(file_hashes, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
