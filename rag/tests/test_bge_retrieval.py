from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from paper_review_agent.bge_retrieval import (
    BGERetrievalConfig,
    BgeM3HybridRetrievalService,
    DenseCandidate,
    InMemoryCosineDenseStore,
    IndexIntegrityError,
    RetrievalFilters,
    maximal_marginal_relevance_ids,
    maxsim_score,
    reciprocal_rank_fusion_ids,
)
from paper_review_agent.model_management import MultiRepresentation
from paper_review_agent.schemas import Chunk


class _FakeEmbedder:
    model_id = "BAAI/bge-m3"
    revision = "a" * 40
    dense_dimension = 1024
    colbert_dimension = 1024

    def __init__(self):
        self.document_calls = 0
        self.query_calls = 0
        self.document_texts = []

    def embed_documents(self, texts):
        self.document_calls += 1
        self.document_texts.extend(texts)
        return [self._representation(text) for text in texts]

    def embed_queries(self, texts):
        self.query_calls += 1
        return [self._representation(text) for text in texts]

    @staticmethod
    def _representation(text: str) -> MultiRepresentation:
        dense = np.zeros(1024, dtype=np.float32)
        if "beta" in text:
            dense[1] = 1.0
            sparse = {2: 1.0}
            colbert_index = 1
        else:
            dense[0] = 1.0
            sparse = {1: 1.0}
            colbert_index = 0
        colbert = np.zeros((1, 1024), dtype=np.float32)
        colbert[0, colbert_index] = 1.0
        return MultiRepresentation(
            dense=dense,
            sparse_indices=np.asarray(sorted(sparse), dtype=np.int32),
            sparse_values=np.asarray(
                [sparse[key] for key in sorted(sparse)], dtype=np.float32
            ),
            colbert=colbert,
        )


def _config(
    tmp_path: Path,
    *,
    revision: str = "a" * 40,
    files_sha256: str = "f" * 64,
) -> BGERetrievalConfig:
    model_path = tmp_path / "model"
    model_path.mkdir(exist_ok=True)
    return BGERetrievalConfig(
        index_root=tmp_path / "index",
        model_path=model_path,
        model_revision=revision,
        model_files_sha256=files_sha256,
    )


def _chunk(
    chunk_id: str, document_id: str, text: str, source_kind: str = "paper"
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_kind=source_kind,
        document_id=document_id,
        page=1,
        section="Method",
        content_kind="text",
        text=text,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )


def _service(tmp_path: Path):
    embedder = _FakeEmbedder()
    dense = InMemoryCosineDenseStore()
    service = BgeM3HybridRetrievalService(
        _config(tmp_path), embedder, dense_store=dense
    )
    return service, embedder, dense


def test_profile_fingerprint_is_stable_and_revision_isolated(tmp_path: Path):
    first = _config(tmp_path, revision="a" * 40)
    same = _config(tmp_path, revision="a" * 40)
    other = _config(tmp_path, revision="b" * 40)
    changed_files = _config(tmp_path, revision="a" * 40, files_sha256="e" * 64)

    assert first.profile_fingerprint == same.profile_fingerprint
    assert len(first.profile_fingerprint) == 64
    assert first.profile_fingerprint != other.profile_fingerprint
    assert first.profile_fingerprint != changed_files.profile_fingerprint
    assert "gemini" not in first.profile_fingerprint


def test_index_is_idempotent_and_colbert_is_float16_mmap(tmp_path: Path):
    service, embedder, _ = _service(tmp_path)
    chunks = [_chunk("alpha", "paper-a", "alpha method")]

    assert service.index_chunks(chunks) is True
    assert service.index_chunks(chunks) is False
    assert embedder.document_calls == 1
    assert embedder.document_texts == ["Section: Method\nalpha method"]

    files = list(service.colbert_dir.rglob("*.npy"))
    assert len(files) == 1
    value = np.load(files[0], mmap_mode="r", allow_pickle=False)
    assert isinstance(value, np.memmap)
    assert value.dtype == np.float16
    assert value.shape == (1, 1024)


def test_chunk_locator_fields_survive_sqlite_round_trip(tmp_path: Path):
    service, _, _ = _service(tmp_path)
    chunk = _chunk("table", "paper-a", "alpha table")
    payload = chunk.model_dump(mode="json")
    payload.update(
        {
            "element_id": "tbl-1",
            "object_label": "Table 1",
            "printed_page": "7",
            "bbox": {
                "x0": 10.0,
                "y0": 20.0,
                "x1": 100.0,
                "y1": 200.0,
                "page_width": 612.0,
                "page_height": 792.0,
            },
            "extraction_method": "pdfplumber",
        }
    )
    chunk = Chunk.model_validate(payload)
    service.index_chunks([chunk])

    restored = service.retrieve("paper", "paper-a", ["alpha"], 1)[0]

    assert restored.element_id == "tbl-1"
    assert restored.object_label == "Table 1"
    assert restored.printed_page == "7"
    assert restored.bbox is not None and restored.bbox.x1 == 100.0
    assert restored.extraction_method == "pdfplumber"


def test_existing_sparse_database_adds_chunk_json_column(tmp_path: Path):
    config = _config(tmp_path)
    profile_dir = config.index_root / "bge-m3" / config.profile_fingerprint[:16]
    profile_dir.mkdir(parents=True)
    database = profile_dir / "sparse.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE chunks (
                point_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL,
                document_id TEXT NOT NULL, generation TEXT NOT NULL,
                chunk_id TEXT NOT NULL, page INTEGER, section TEXT,
                content_kind TEXT NOT NULL, text TEXT NOT NULL,
                content_hash TEXT NOT NULL, colbert_path TEXT NOT NULL
            )"""
        )

    BgeM3HybridRetrievalService(
        config,
        _FakeEmbedder(),
        dense_store=InMemoryCosineDenseStore(),
    )

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(chunks)")}
    assert "chunk_json" in columns


def test_dense_sparse_rrf_colbert_and_trace_are_deterministic(tmp_path: Path):
    service, _, _ = _service(tmp_path)
    service.index_chunks(
        [
            _chunk("a", "paper-a", "alpha mechanism"),
            _chunk("b", "paper-a", "beta mechanism"),
        ]
    )

    result = service.retrieve_with_trace("paper", "paper-a", ["alpha question"], 2)

    assert [hit.chunk.chunk_id for hit in result.hits] == ["a", "b"]
    query_trace = result.trace.queries[0]
    assert len(query_trace.dense_ids) == 2
    assert len(query_trace.sparse_ids) == 1
    assert query_trace.rrf_candidate_ids[0] in query_trace.dense_ids
    assert len(query_trace.candidates) <= service.config.fusion_candidates
    assert query_trace.candidates[0].colbert_score is not None
    assert result.trace.to_dict()["selected_chunk_ids"] == ["a", "b"]


def test_colbert_maxsim_order_is_not_undone_by_candidate_retrieval(tmp_path: Path):
    class ConflictingEmbedder(_FakeEmbedder):
        def embed_documents(self, texts):
            return [self._document_representation(text) for text in texts]

        def embed_queries(self, texts):
            return [self._query_representation() for _ in texts]

        @staticmethod
        def _representation_for(
            *, dense_index: int, sparse_index: int, colbert_index: int
        ) -> MultiRepresentation:
            dense = np.zeros(1024, dtype=np.float32)
            dense[dense_index] = 1.0
            colbert = np.zeros((1, 1024), dtype=np.float32)
            colbert[0, colbert_index] = 1.0
            return MultiRepresentation(
                dense=dense,
                sparse_indices=np.asarray([sparse_index], dtype=np.int32),
                sparse_values=np.asarray([1.0], dtype=np.float32),
                colbert=colbert,
            )

        @classmethod
        def _document_representation(cls, text: str) -> MultiRepresentation:
            if "dense-favorite" in text:
                return cls._representation_for(
                    dense_index=0,
                    sparse_index=1,
                    colbert_index=0,
                )
            return cls._representation_for(
                dense_index=1,
                sparse_index=2,
                colbert_index=1,
            )

        @classmethod
        def _query_representation(cls) -> MultiRepresentation:
            # Dense and sparse retrieval favor the first document, while
            # MaxSim deliberately favors the second one.
            return cls._representation_for(
                dense_index=0,
                sparse_index=1,
                colbert_index=1,
            )

    service = BgeM3HybridRetrievalService(
        _config(tmp_path),
        ConflictingEmbedder(),
        dense_store=InMemoryCosineDenseStore(),
    )
    service.index_chunks(
        [
            _chunk("dense", "paper-a", "dense-favorite candidate"),
            _chunk("colbert", "paper-a", "colbert-favorite candidate"),
        ]
    )

    result = service.retrieve_with_trace("paper", "paper-a", ["query"], 2)
    query_trace = result.trace.queries[0]

    assert query_trace.candidates[0].chunk_id == "colbert"
    assert query_trace.candidates[0].colbert_rank == 1
    assert query_trace.candidates[0].fused_score > query_trace.candidates[1].fused_score
    assert [hit.chunk.chunk_id for hit in result.hits] == ["colbert", "dense"]


def test_reserved_visual_is_included_at_tail_without_rank_front_forcing():
    candidates = ["best", "runner-up", "visual"]
    relevance = {"best": 1.0, "runner-up": 0.9, "visual": 0.1}
    vectors = {
        "best": np.asarray([1.0, 0.0, 0.0], dtype=np.float32),
        "runner-up": np.asarray([0.0, 1.0, 0.0], dtype=np.float32),
        "visual": np.asarray([0.0, 0.0, 1.0], dtype=np.float32),
    }

    natural = maximal_marginal_relevance_ids(
        candidates,
        relevance,
        vectors,
        limit=2,
    )
    reserved = maximal_marginal_relevance_ids(
        candidates,
        relevance,
        vectors,
        limit=2,
        reserved=["visual"],
    )

    assert natural == ["best", "runner-up"]
    assert reserved == ["best", "visual"]


@pytest.mark.parametrize(
    ("content_kind", "object_label", "query"),
    [
        (
            "table",
            "Table I",
            "In Table I, what beta throughput value is reported?",
        ),
        (
            "figure",
            "Figure 5",
            "In Figure 5, what beta memory value is shown?",
        ),
    ],
)
def test_exact_numeric_visual_reference_is_reserved_after_mmr(
    tmp_path: Path,
    content_kind: str,
    object_label: str,
    query: str,
):
    service, _, _ = _service(tmp_path)
    visual = _chunk(
        "z-visual", "paper-a", "alpha throughput memory 12 GB/s"
    ).model_copy(
        update={
            "content_kind": content_kind,
            "object_label": object_label,
        }
    )
    service.index_chunks(
        [
            _chunk("a-text", "paper-a", "beta mechanism explanation"),
            visual,
        ]
    )

    result = service.retrieve_with_trace("paper", "paper-a", [query], 1)

    assert [hit.chunk.chunk_id for hit in result.hits] == ["z-visual"]
    assert result.trace.numeric_visual_reserved_chunk_ids == ["z-visual"]
    query_trace = result.trace.queries[0]
    assert len(query_trace.rrf_candidate_ids) <= service.config.fusion_candidates


def test_exact_visual_from_dense_sparse_union_is_retained_at_rrf_boundary(
    tmp_path: Path,
):
    service, _, dense = _service(tmp_path)
    dense_only = [
        _chunk(f"dense-{index:02d}", "paper-a", f"alpha mechanism {index}")
        for index in range(23)
    ]
    visual = _chunk("visual", "paper-a", "alpha throughput 12 GB/s").model_copy(
        update={"content_kind": "table", "object_label": "Table I"}
    )
    sparse_only = [
        _chunk(f"sparse-{index:02d}", "paper-a", f"beta retrieval {index}")
        for index in range(24)
    ]
    service.index_chunks([*dense_only, visual, *sparse_only])
    point_id_by_chunk = {
        str(record.metadata["chunk_id"]): point_id
        for point_id, record in dense.records.items()
    }
    forced_dense_ids = [
        *(point_id_by_chunk[chunk.chunk_id] for chunk in dense_only),
        point_id_by_chunk[visual.chunk_id],
    ]

    def forced_query(*_args, **_kwargs):
        return [
            DenseCandidate(point_id, 1.0 - rank / 100.0)
            for rank, point_id in enumerate(forced_dense_ids, start=1)
        ]

    dense.query = forced_query  # type: ignore[method-assign]

    result = service.retrieve_with_trace(
        "paper",
        "paper-a",
        ["In Table I, what beta throughput value is reported?"],
        1,
    )

    query_trace = result.trace.queries[0]
    visual_point_id = point_id_by_chunk["visual"]
    assert query_trace.dense_ids[-1] == visual_point_id
    assert visual_point_id not in query_trace.sparse_ids
    assert len(query_trace.rrf_candidate_ids) == service.config.fusion_candidates
    assert visual_point_id in query_trace.rrf_candidate_ids
    assert [hit.chunk.chunk_id for hit in result.hits] == ["visual"]


def test_numeric_query_does_not_reserve_irrelevant_visual(tmp_path: Path):
    service, _, _ = _service(tmp_path)
    irrelevant_table = _chunk(
        "z-table", "paper-a", "alpha latency measurements"
    ).model_copy(update={"content_kind": "table", "object_label": "Table II"})
    service.index_chunks(
        [
            _chunk("a-text", "paper-a", "beta throughput mechanism"),
            irrelevant_table,
        ]
    )

    result = service.retrieve_with_trace(
        "paper",
        "paper-a",
        ["What beta throughput percentage is reported?"],
        1,
    )

    assert [hit.chunk.chunk_id for hit in result.hits] == ["a-text"]
    assert result.trace.numeric_visual_reserved_chunk_ids == []


def test_non_numeric_query_keeps_normal_hybrid_mmr_behavior(tmp_path: Path):
    service, _, _ = _service(tmp_path)
    service.index_chunks(
        [
            _chunk("a-text", "paper-a", "beta mechanism explanation"),
            _chunk("z-table", "paper-a", "alpha LLaMA-8B mechanism table").model_copy(
                update={"content_kind": "table", "object_label": "Table I"}
            ),
        ]
    )

    result = service.retrieve_with_trace(
        "paper", "paper-a", ["Explain the beta mechanism"], 1
    )

    assert [hit.chunk.chunk_id for hit in result.hits] == ["a-text"]
    assert result.trace.numeric_visual_reserved_chunk_ids == []

    model_identifier_result = service.retrieve_with_trace(
        "paper", "paper-a", ["Explain beta behavior of LLaMA-8B"], 1
    )
    assert [hit.chunk.chunk_id for hit in model_identifier_result.hits] == ["a-text"]
    assert model_identifier_result.trace.numeric_visual_reserved_chunk_ids == []


def test_visual_reservation_cannot_bypass_metadata_filters(tmp_path: Path):
    service, _, _ = _service(tmp_path)
    service.index_chunks(
        [
            _chunk("a-text", "paper-a", "beta mechanism explanation"),
            _chunk("z-table", "paper-a", "alpha throughput 12 GB/s").model_copy(
                update={"content_kind": "table", "object_label": "Table I"}
            ),
        ]
    )

    result = service.retrieve_with_trace(
        "paper",
        "paper-a",
        ["In Table I, what beta throughput value is reported?"],
        1,
        filters=RetrievalFilters(content_kinds=("text",)),
    )

    assert [hit.chunk.chunk_id for hit in result.hits] == ["a-text"]
    assert result.trace.numeric_visual_reserved_chunk_ids == []


def test_document_and_corpus_filters_are_applied_before_topk(tmp_path: Path):
    service, _, _ = _service(tmp_path)
    service.index_chunks([_chunk("a", "paper-a", "alpha relevant")])
    service.index_chunks([_chunk("b", "paper-b", "alpha other")])
    service.index_chunks([_chunk("c", "glossary", "alpha context", "common")])

    paper = service.retrieve("paper", "paper-a", ["alpha"], 5)
    common = service.retrieve("common", None, ["alpha"], 5)

    assert [chunk.chunk_id for chunk in paper] == ["a"]
    assert [chunk.chunk_id for chunk in common] == ["c"]


def test_metadata_filters_apply_before_topk_and_support_source_version(tmp_path: Path):
    service, _, _ = _service(tmp_path)
    base = _chunk("method", "paper-a", "alpha method")
    table = _chunk("table", "paper-a", "alpha table").model_copy(
        update={
            "document_version": "source-sha-v2",
            "page": 7,
            "section": "Experiments",
            "content_kind": "table",
        }
    )
    service.index_chunks([base, table])

    result = service.retrieve(
        "paper",
        None,
        ["alpha"],
        1,
        filters=RetrievalFilters(
            document_ids=("paper-a",),
            versions=("source-sha-v2",),
            pages=(7,),
            sections=("Experiments",),
            content_kinds=("table",),
        ),
    )

    assert [chunk.chunk_id for chunk in result] == ["table"]


def test_invalid_retrieval_filter_fails_before_embedding(tmp_path: Path):
    service, embedder, _ = _service(tmp_path)

    with pytest.raises(ValueError, match="content_kind"):
        RetrievalFilters(content_kinds=("audio",))
    with pytest.raises(ValueError, match="page filter"):
        RetrievalFilters(pages=(0,))
    assert embedder.query_calls == 0


def test_failed_reindex_keeps_previous_generation_searchable(tmp_path: Path):
    service, _, dense = _service(tmp_path)
    service.index_chunks([_chunk("old", "paper-a", "alpha old")])
    original_upsert = dense.upsert

    def fail(_):
        raise RuntimeError("simulated dense failure")

    dense.upsert = fail  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="simulated"):
        service.index_chunks([_chunk("new", "paper-a", "beta new")])
    dense.upsert = original_upsert  # type: ignore[method-assign]

    assert [
        chunk.chunk_id for chunk in service.retrieve("paper", "paper-a", ["alpha"], 5)
    ] == ["old"]


def test_corrupt_colbert_sidecar_fails_closed(tmp_path: Path):
    service, _, _ = _service(tmp_path)
    service.index_chunks([_chunk("a", "paper-a", "alpha")])
    sidecar = next(service.colbert_dir.rglob("*.npy"))
    sidecar.write_bytes(b"not-numpy")

    with pytest.raises(IndexIntegrityError, match="읽을 수 없습니다"):
        service.retrieve("paper", "paper-a", ["alpha"], 1)


def test_rrf_candidate_budget_and_maxsim_math():
    dense = [f"d-{index:02d}" for index in range(24)]
    sparse = [f"s-{index:02d}" for index in range(24)]
    fused = reciprocal_rank_fusion_ids([dense, sparse])[:32]

    assert len(fused) == 32
    assert len({point_id for point_id, _ in fused}) == 32
    query = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    exact = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    partial = np.asarray([[1.0, 0.0]], dtype=np.float32)
    assert maxsim_score(query, exact) == pytest.approx(1.0)
    assert maxsim_score(query, partial) == pytest.approx(0.5)


def test_empty_requests_do_not_call_embedder(tmp_path: Path):
    service, embedder, _ = _service(tmp_path)
    result = service.retrieve_with_trace("paper", "missing", ["", "   "], 0)

    assert result.hits == []
    assert result.trace.queries == []
    assert embedder.query_calls == 0


def test_chroma_cosine_store_persists_across_service_restart(tmp_path: Path):
    pytest.importorskip("chromadb")
    config = _config(tmp_path)
    first_embedder = _FakeEmbedder()
    first = BgeM3HybridRetrievalService(config, first_embedder)
    first.index_chunks(
        [
            _chunk("a", "paper-a", "alpha persisted"),
            _chunk("b", "paper-a", "beta persisted"),
        ]
    )

    reopened = BgeM3HybridRetrievalService(config, _FakeEmbedder())
    result = reopened.retrieve("paper", "paper-a", ["alpha"], 2)

    assert [chunk.chunk_id for chunk in result] == ["a", "b"]
