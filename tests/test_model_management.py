from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import pytest

from paper_review_agent.exceptions import ConfigurationError, ProviderError
from paper_review_agent.model_management import (
    BGEModelRuntimeConfig,
    LocalBgeM3Embedder,
    load_local_snapshot,
    pull_pinned_snapshot,
)


def test_pinned_snapshot_is_explicit_and_cached(tmp_path: Path):
    revision = "a" * 40
    calls: list[dict[str, object]] = []

    def downloader(**kwargs):
        calls.append(kwargs)
        path = Path(str(kwargs["local_dir"]))
        (path / "config.json").write_text("{}", encoding="utf-8")
        return str(path)

    first = pull_pinned_snapshot(tmp_path, revision=revision, downloader=downloader)
    second = pull_pinned_snapshot(
        tmp_path,
        revision=revision,
        downloader=lambda **_: (_ for _ in ()).throw(AssertionError("network called")),
    )

    assert len(calls) == 1
    assert calls[0]["repo_id"] == "BAAI/bge-m3"
    assert calls[0]["revision"] == revision
    assert first == second
    assert len(first.files_sha256) == 64
    assert first.file_hashes == {"config.json": hashlib.sha256(b"{}").hexdigest()}
    assert load_local_snapshot(first.path, expected_revision=revision) == first


def test_local_snapshot_detects_file_tampering(tmp_path: Path):
    revision = "1" * 40

    def downloader(**kwargs):
        path = Path(str(kwargs["local_dir"]))
        (path / "config.json").write_text("original", encoding="utf-8")
        return str(path)

    snapshot = pull_pinned_snapshot(tmp_path, revision=revision, downloader=downloader)
    (snapshot.path / "config.json").write_text("changed", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="파일 해시 불일치"):
        load_local_snapshot(snapshot.path, expected_revision=revision)


@pytest.mark.parametrize("revision", ["", "main", "latest", "a" * 39])
def test_snapshot_rejects_moving_or_invalid_revisions(tmp_path: Path, revision: str):
    with pytest.raises(ConfigurationError, match="commit SHA"):
        pull_pinned_snapshot(tmp_path, revision=revision, downloader=lambda **_: "unused")


def test_snapshot_rejects_unexpected_downloader_path(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ProviderError, match="local_dir 밖"):
        pull_pinned_snapshot(
            tmp_path / "models",
            revision="b" * 40,
            downloader=lambda **_: str(outside),
        )


class _FakeBgeModel:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def encode(self, texts, **kwargs):
        self.calls.append({"texts": list(texts), **kwargs})
        count = len(texts)
        return {
            "dense_vecs": np.tile(np.eye(1, 1024, dtype=np.float32), (count, 1)),
            "lexical_weights": [{"11": 0.75, "3": 0.25} for _ in texts],
            "colbert_vecs": [np.eye(2, 1024, dtype=np.float32) for _ in texts],
        }


def test_local_runtime_uses_cpu_batch_one_and_all_three_outputs(tmp_path: Path):
    model_path = tmp_path / "model"
    model_path.mkdir()
    fake = _FakeBgeModel()
    factory_calls: list[dict[str, object]] = []

    def factory(path, **kwargs):
        factory_calls.append({"path": path, **kwargs})
        return fake

    embedder = LocalBgeM3Embedder(
        BGEModelRuntimeConfig(
            model_path=model_path,
            model_revision="c" * 40,
            device="auto",
        ),
        model_factory=factory,
        cuda_available=lambda: False,
    )
    output = embedder.embed_documents(["first", "second"])

    assert factory_calls == [
        {"path": str(model_path.resolve()), "devices": "cpu", "use_fp16": False}
    ]
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert len(fake.calls) == 2
    assert all(call["batch_size"] == 1 for call in fake.calls)
    assert output[0].dense.shape == (1024,)
    assert output[0].sparse_indices.tolist() == [3, 11]
    assert output[0].sparse_values.tolist() == pytest.approx([0.25, 0.75])
    assert output[0].colbert.shape == (2, 1024)
    assert output[0].dense.flags.writeable is False
    assert output[0].colbert.flags.writeable is False


def test_query_cache_deduplicates_and_cuda_is_opt_in(tmp_path: Path):
    model_path = tmp_path / "model"
    model_path.mkdir()
    fake = _FakeBgeModel()
    embedder = LocalBgeM3Embedder(
        BGEModelRuntimeConfig(
            model_path=model_path,
            model_revision="d" * 40,
            device="cuda",
            cuda_batch_size=4,
        ),
        model_factory=lambda *_, **__: fake,
        cuda_available=lambda: True,
    )

    first = embedder.embed_queries(["same", "same"])
    second = embedder.embed_queries(["same"])

    assert len(first) == 2 and len(second) == 1
    assert len(fake.calls) == 1
    assert fake.calls[0]["texts"] == ["same"]
    assert fake.calls[0]["batch_size"] == 4
    assert embedder.use_fp16 is True


def test_runtime_rejects_remote_identifier_and_openai(tmp_path: Path):
    with pytest.raises(ConfigurationError, match="로컬 디렉터리"):
        LocalBgeM3Embedder(
            BGEModelRuntimeConfig(
                model_path=tmp_path / "BAAI-bge-m3",
                model_revision="e" * 40,
            ),
            model_factory=lambda *_, **__: object(),
            cuda_available=lambda: False,
        )
    with pytest.raises(ConfigurationError, match="OpenAI"):
        BGEModelRuntimeConfig(
            model_path=tmp_path,
            model_revision="f" * 40,
            model_id="text-embedding-3-large",
        )
