"""Local BGE-M3 dense, learned-sparse and late-interaction retrieval.

The implementation deliberately keeps the three representations in storage
suited to their shapes:

* 1024-dimensional dense vectors in a cosine Chroma collection;
* learned sparse token weights in SQLite postings;
* variable-length 1024-dimensional ColBERT matrices as atomic float16 ``.npy``
  files, loaded with mmap only for the fused candidate set.

An SQLite document pointer publishes a new generation only after all three
representations have been written. Partially written generations are therefore
unreachable by normal searches and the previous generation remains active.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from paper_review_agent.artifacts import atomic_write
from paper_review_agent.exceptions import (
    ConfigurationError,
    DependencyError,
    PaperReviewError,
)
from paper_review_agent.model_management import (
    BGE_M3_COLBERT_DIMENSION,
    BGE_M3_DENSE_DIMENSION,
    BGE_M3_MODEL_ID,
    MultiRepresentation,
)
from paper_review_agent.schemas import Chunk

INDEX_SCHEMA_VERSION = "2.0.0"


class IndexIntegrityError(PaperReviewError):
    """Stored retrieval representations are missing, corrupt or incompatible."""


class MultiRepresentationEmbedder(Protocol):
    model_id: str
    revision: str
    dense_dimension: int
    colbert_dimension: int

    def embed_documents(self, texts: Sequence[str]) -> list[MultiRepresentation]: ...

    def embed_queries(self, texts: Sequence[str]) -> list[MultiRepresentation]: ...


@dataclass(frozen=True, slots=True)
class BGERetrievalConfig:
    """Independent retrieval settings; no application-global config required."""

    index_root: Path
    model_path: Path
    model_revision: str
    model_files_sha256: str
    model_id: str = BGE_M3_MODEL_ID
    parser_version: str = "paper-parser-1.0.0"
    chunker_version: str = "token-chunker-1.2.0"
    target_chunk_tokens: int = 800
    chunk_overlap_tokens: int = 120
    max_passage_tokens: int = 896
    max_query_tokens: int = 128
    dense_dimension: int = BGE_M3_DENSE_DIMENSION
    colbert_dimension: int = BGE_M3_COLBERT_DIMENSION
    dense_k: int = 24
    sparse_k: int = 24
    fusion_candidates: int = 32
    rrf_k: int = 60
    mmr_lambda: float = 0.7
    index_schema_version: str = INDEX_SCHEMA_VERSION

    def __post_init__(self) -> None:
        normalized = self.model_id.lower()
        if "openai" in normalized or normalized.startswith("text-embedding-"):
            raise ConfigurationError("OpenAI embedding model은 허용되지 않습니다.")
        if not self.model_revision.strip():
            raise ConfigurationError("BGE-M3 model_revision은 비어 있을 수 없습니다.")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", self.model_revision):
            raise ConfigurationError(
                "BGE-M3 model_revision은 40자리 고정 commit SHA여야 합니다."
            )
        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.model_files_sha256):
            raise ConfigurationError(
                "model_files_sha256는 64자리 SHA-256이어야 합니다."
            )
        if self.dense_dimension != BGE_M3_DENSE_DIMENSION:
            raise ConfigurationError("BGE-M3 dense dimension은 1024여야 합니다.")
        if self.colbert_dimension != BGE_M3_COLBERT_DIMENSION:
            raise ConfigurationError("BGE-M3 ColBERT dimension은 1024여야 합니다.")
        if not 1 <= self.max_query_tokens <= self.max_passage_tokens <= 896:
            raise ConfigurationError(
                "token 상한은 1 <= query <= passage <= 896이어야 합니다."
            )
        if not 0 <= self.chunk_overlap_tokens < self.target_chunk_tokens:
            raise ConfigurationError(
                "chunk overlap은 target chunk 크기보다 작아야 합니다."
            )
        if min(self.dense_k, self.sparse_k, self.fusion_candidates, self.rrf_k) < 1:
            raise ConfigurationError("검색 candidate 설정은 모두 1 이상이어야 합니다.")
        if not 0.0 <= self.mmr_lambda <= 1.0:
            raise ConfigurationError("mmr_lambda는 0과 1 사이여야 합니다.")

    def profile_payload(self) -> dict[str, object]:
        return {
            "index_schema_version": self.index_schema_version,
            "model_id": self.model_id,
            "model_revision": self.model_revision.lower(),
            "model_files_sha256": self.model_files_sha256.lower(),
            "dense_dimension": self.dense_dimension,
            "colbert_dimension": self.colbert_dimension,
            "dense_distance": "cosine",
            "late_vector_dtype": "float16",
            "max_passage_tokens": self.max_passage_tokens,
            "max_query_tokens": self.max_query_tokens,
            "parser_version": self.parser_version,
            "chunker_version": self.chunker_version,
            "target_chunk_tokens": self.target_chunk_tokens,
            "chunk_overlap_tokens": self.chunk_overlap_tokens,
            "representations": ["dense", "learned_sparse", "colbert"],
        }

    @property
    def profile_fingerprint(self) -> str:
        canonical = json.dumps(
            self.profile_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    @property
    def profile_id(self) -> str:
        """Stable full profile identifier (alias retained for graph integration)."""

        return self.profile_fingerprint


@dataclass(frozen=True, slots=True)
class ActiveTarget:
    source_kind: str
    document_id: str
    generation: str


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    """Metadata filters applied before dense/sparse top-k selection.

    ``versions`` accepts either the immutable ``Chunk.document_version`` (the
    source SHA-256 in the parser) or an explicit active index generation.  All
    populated fields are ANDed; values inside a field are ORed.
    """

    document_ids: tuple[str, ...] = ()
    versions: tuple[str, ...] = ()
    pages: tuple[int, ...] = ()
    sections: tuple[str, ...] = ()
    content_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        valid_kinds = {"text", "table", "caption", "figure", "chart", "diagram"}
        unknown = set(self.content_kinds) - valid_kinds
        if unknown:
            raise ValueError(f"지원하지 않는 content_kind filter: {sorted(unknown)}")
        if any(page < 1 for page in self.pages):
            raise ValueError("page filter는 1 이상의 물리 페이지여야 합니다.")

    def to_dict(self) -> dict[str, list[str | int]]:
        return {
            "document_ids": list(self.document_ids),
            "versions": list(self.versions),
            "pages": list(self.pages),
            "sections": list(self.sections),
            "content_kinds": list(self.content_kinds),
        }


@dataclass(frozen=True, slots=True)
class DenseRecord:
    point_id: str
    vector: Any
    text: str
    metadata: dict[str, str | int | bool]


@dataclass(frozen=True, slots=True)
class DenseCandidate:
    point_id: str
    score: float


class DenseStore(Protocol):
    def upsert(self, records: Sequence[DenseRecord]) -> None: ...

    def query(
        self,
        vector: Any,
        targets: Sequence[ActiveTarget],
        limit: int,
        *,
        allowed_point_ids: set[str] | None = None,
    ) -> list[DenseCandidate]: ...

    def get_vectors(self, point_ids: Sequence[str]) -> dict[str, Any]: ...

    def delete(self, point_ids: Sequence[str]) -> None: ...


@dataclass(frozen=True, slots=True)
class CandidateTrace:
    point_id: str
    chunk_id: str
    dense_rank: int | None = None
    dense_score: float | None = None
    sparse_rank: int | None = None
    sparse_score: float | None = None
    colbert_rank: int | None = None
    colbert_score: float | None = None
    fused_score: float = 0.0


@dataclass(frozen=True, slots=True)
class QueryRetrievalTrace:
    query: str
    dense_ids: list[str]
    sparse_ids: list[str]
    rrf_candidate_ids: list[str]
    candidates: list[CandidateTrace]


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    profile_fingerprint: str
    source_kind: str
    document_id: str | None
    targets: list[dict[str, str]]
    queries: list[QueryRetrievalTrace]
    selected_chunk_ids: list[str]
    numeric_visual_reserved_chunk_ids: list[str] = field(default_factory=list)
    filters: dict[str, list[str | int]] | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk: Chunk
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    hits: list[RetrievalHit]
    trace: RetrievalTrace

    @property
    def chunks(self) -> list[Chunk]:
        return [hit.chunk for hit in self.hits]


@dataclass(slots=True)
class _StoredChunk:
    point_id: str
    chunk: Chunk
    generation: str
    colbert_path: str


class ChromaCosineDenseStore:
    """Precomputed BGE dense vectors stored in an explicit cosine collection."""

    def __init__(self, root: Path, profile_fingerprint: str):
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as exc:
            raise DependencyError("BGE dense 검색에는 chromadb가 필요합니다.") from exc
        path = root / "chroma"
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=Settings(anonymized_telemetry=False),
        )
        name = f"bge_m3_{profile_fingerprint[:24]}"
        self._collection = self._client.get_or_create_collection(
            name=name,
            metadata={
                "hnsw:space": "cosine",
                "profile_fingerprint": profile_fingerprint,
            },
        )
        metadata = self._collection.metadata or {}
        if metadata.get("profile_fingerprint") != profile_fingerprint:
            raise IndexIntegrityError(
                "Chroma collection profile fingerprint가 일치하지 않습니다."
            )

    def upsert(self, records: Sequence[DenseRecord]) -> None:
        if not records:
            return
        self._collection.upsert(
            ids=[record.point_id for record in records],
            embeddings=[_float_list(record.vector) for record in records],
            documents=[record.text for record in records],
            metadatas=[record.metadata for record in records],
        )

    def query(
        self,
        vector: Any,
        targets: Sequence[ActiveTarget],
        limit: int,
        *,
        allowed_point_ids: set[str] | None = None,
    ) -> list[DenseCandidate]:
        if limit <= 0 or not targets or allowed_point_ids == set():
            return []
        count = self._collection.count()
        if count == 0:
            return []
        where = _chroma_target_filter(targets)
        if allowed_point_ids is not None:
            where = {
                "$and": [
                    where,
                    {"point_id": {"$in": sorted(allowed_point_ids)}},
                ]
            }
        result = self._collection.query(
            query_embeddings=[_float_list(vector)],
            n_results=min(limit, count),
            where=where,
            include=["distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            DenseCandidate(point_id=point_id, score=1.0 - float(distance))
            for point_id, distance in zip(ids, distances, strict=True)
        ]

    def get_vectors(self, point_ids: Sequence[str]) -> dict[str, Any]:
        if not point_ids:
            return {}
        result = self._collection.get(ids=list(point_ids), include=["embeddings"])
        ids = result.get("ids") or []
        embeddings = result.get("embeddings")
        if embeddings is None:
            return {}
        return {
            point_id: embedding
            for point_id, embedding in zip(ids, embeddings, strict=True)
        }

    def delete(self, point_ids: Sequence[str]) -> None:
        if point_ids:
            self._collection.delete(ids=list(point_ids))


class InMemoryCosineDenseStore:
    """Deterministic dense store for unit tests and dependency-light exercises."""

    def __init__(self):
        self.records: dict[str, DenseRecord] = {}

    def upsert(self, records: Sequence[DenseRecord]) -> None:
        self.records.update((record.point_id, record) for record in records)

    def query(
        self,
        vector: Any,
        targets: Sequence[ActiveTarget],
        limit: int,
        *,
        allowed_point_ids: set[str] | None = None,
    ) -> list[DenseCandidate]:
        allowed = {
            (item.source_kind, item.document_id, item.generation) for item in targets
        }
        ranked = []
        for point_id, record in self.records.items():
            if allowed_point_ids is not None and point_id not in allowed_point_ids:
                continue
            metadata = record.metadata
            key = (
                str(metadata["source_kind"]),
                str(metadata["document_id"]),
                str(metadata["generation"]),
            )
            if key in allowed:
                ranked.append(DenseCandidate(point_id, _cosine(vector, record.vector)))
        return sorted(ranked, key=lambda item: (-item.score, item.point_id))[:limit]

    def get_vectors(self, point_ids: Sequence[str]) -> dict[str, Any]:
        return {
            point_id: self.records[point_id].vector
            for point_id in point_ids
            if point_id in self.records
        }

    def delete(self, point_ids: Sequence[str]) -> None:
        for point_id in point_ids:
            self.records.pop(point_id, None)


class BgeM3HybridRetrievalService:
    """Persistent tri-modal retrieval with atomic active-generation publication."""

    def __init__(
        self,
        config: BGERetrievalConfig,
        embedder: MultiRepresentationEmbedder,
        *,
        dense_store: DenseStore | None = None,
    ) -> None:
        self.config = config
        self.embedder = embedder
        _validate_embedder(config, embedder)
        self.profile_fingerprint = config.profile_fingerprint
        self.profile_id = self.profile_fingerprint
        self.profile_dir = (
            config.index_root.expanduser().resolve()
            / "bge-m3"
            / self.profile_fingerprint[:16]
        )
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.colbert_dir = self.profile_dir / "colbert"
        self.colbert_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = self.profile_dir / "sparse.sqlite"
        self._lock = threading.RLock()
        self._write_profile_manifest()
        self._initialize_database()
        self.dense_store = dense_store or ChromaCosineDenseStore(
            self.profile_dir, self.profile_fingerprint
        )

    def index_chunks(self, chunks: list[Chunk], *, force: bool = False) -> bool:
        if not chunks:
            return False
        source_kind = chunks[0].source_kind
        document_id = chunks[0].document_id
        if any(
            chunk.source_kind != source_kind or chunk.document_id != document_id
            for chunk in chunks
        ):
            raise ValueError(
                "한 index_chunks 호출에는 같은 문서의 chunk만 전달해야 합니다."
            )
        document_fingerprint = _document_fingerprint(
            self.profile_fingerprint, source_kind, document_id, chunks
        )
        generation = document_fingerprint[:24]

        with self._lock:
            previous = self._document_row(source_kind, document_id)
            if (
                previous is not None
                and previous["document_fingerprint"] == document_fingerprint
            ):
                if not force:
                    return False
                # Force means a real staged generation. Reusing the active point
                # ids would let cleanup after a failed force-index delete the old
                # generation's dense vectors.
                generation = hashlib.sha256(
                    f"{document_fingerprint}|{uuid.uuid4().hex}".encode()
                ).hexdigest()[:24]
            stored: list[tuple[Chunk, Any, Any, str, str]] = []
            dense_records: list[DenseRecord] = []
            embedding_batch = max(1, int(getattr(self.embedder, "batch_size", 1)))
            for offset in range(0, len(chunks), embedding_batch):
                chunk_batch = chunks[offset : offset + embedding_batch]
                embedding_texts = [_embedding_text(chunk) for chunk in chunk_batch]
                representations = self.embedder.embed_documents(embedding_texts)
                if len(representations) != len(chunk_batch):
                    raise IndexIntegrityError(
                        "embedding 개수가 chunk batch와 일치하지 않습니다."
                    )
                for chunk, embedding_text, representation in zip(
                    chunk_batch, embedding_texts, representations, strict=True
                ):
                    _validate_representation(self.config, representation)
                    point_id = _point_id(
                        self.profile_fingerprint,
                        source_kind,
                        document_id,
                        generation,
                        chunk.chunk_id,
                    )
                    relative_colbert = self._write_colbert(
                        hashlib.sha256(embedding_text.encode("utf-8")).hexdigest(),
                        representation.colbert,
                    )
                    # Do not retain the large ColBERT matrix after its atomic
                    # sidecar write. Sparse arrays and dense vectors are small.
                    stored.append(
                        (
                            chunk,
                            representation.sparse_indices,
                            representation.sparse_values,
                            point_id,
                            relative_colbert,
                        )
                    )
                    metadata: dict[str, str | int | bool] = {
                        "point_id": point_id,
                        "chunk_id": chunk.chunk_id,
                        "source_kind": source_kind,
                        "document_id": document_id,
                        "generation": generation,
                        "content_kind": chunk.content_kind,
                        "content_hash": chunk.content_hash,
                    }
                    if chunk.page is not None:
                        metadata["page"] = chunk.page
                    if chunk.section is not None:
                        metadata["section"] = chunk.section
                    dense_records.append(
                        DenseRecord(
                            point_id, representation.dense, chunk.text, metadata
                        )
                    )

            # Dense and ColBERT writes happen before the SQLite pointer swap.
            # Any failure leaves the previous generation active.
            try:
                self.dense_store.upsert(dense_records)
            except Exception:
                try:
                    self.dense_store.delete(
                        [record.point_id for record in dense_records]
                    )
                except Exception:  # noqa: BLE001 - preserve the indexing error
                    pass
                raise
            old_ids = (
                json.loads(previous["point_ids_json"]) if previous is not None else []
            )
            try:
                with self._connect() as connection:
                    for (
                        chunk,
                        sparse_indices,
                        sparse_values,
                        point_id,
                        relative_colbert,
                    ) in stored:
                        connection.execute(
                            """INSERT OR REPLACE INTO chunks(
                                point_id,source_kind,document_id,generation,chunk_id,page,
                                section,content_kind,text,content_hash,colbert_path,chunk_json
                            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                point_id,
                                source_kind,
                                document_id,
                                generation,
                                chunk.chunk_id,
                                chunk.page,
                                chunk.section,
                                chunk.content_kind,
                                chunk.text,
                                chunk.content_hash,
                                relative_colbert,
                                json.dumps(
                                    chunk.model_dump(mode="json"), ensure_ascii=False
                                ),
                            ),
                        )
                        connection.execute(
                            "DELETE FROM sparse_postings WHERE point_id=?", (point_id,)
                        )
                        connection.executemany(
                            "INSERT INTO sparse_postings(point_id,token_id,weight) VALUES(?,?,?)",
                            [
                                (point_id, int(token_id), float(weight))
                                for token_id, weight in zip(
                                    sparse_indices,
                                    sparse_values,
                                    strict=True,
                                )
                            ],
                        )
                    point_ids = [point_id for _, _, _, point_id, _ in stored]
                    connection.execute(
                        """INSERT INTO documents(
                            source_kind,document_id,active_generation,document_fingerprint,
                            profile_fingerprint,point_ids_json
                        ) VALUES(?,?,?,?,?,?)
                        ON CONFLICT(source_kind,document_id) DO UPDATE SET
                            active_generation=excluded.active_generation,
                            document_fingerprint=excluded.document_fingerprint,
                            profile_fingerprint=excluded.profile_fingerprint,
                            point_ids_json=excluded.point_ids_json""",
                        (
                            source_kind,
                            document_id,
                            generation,
                            document_fingerprint,
                            self.profile_fingerprint,
                            json.dumps(point_ids, sort_keys=True),
                        ),
                    )
            except Exception:
                # New dense rows are orphaned because the active pointer was not
                # published. Best-effort cleanup keeps storage tidy.
                try:
                    self.dense_store.delete(
                        [record.point_id for record in dense_records]
                    )
                except Exception:  # noqa: BLE001 - preserve the indexing error
                    pass
                raise

            stale_ids = sorted(
                set(old_ids) - {record.point_id for record in dense_records}
            )
            if stale_ids:
                # Publication already succeeded. Cleanup must not turn that
                # committed operation into an apparent failure; stale rows are
                # unreachable because every query uses the active generation.
                try:
                    self._delete_stale_rows(stale_ids)
                except Exception:  # noqa: BLE001 - safe orphan, reclaimed later
                    pass
                try:
                    self.dense_store.delete(stale_ids)
                except Exception:  # noqa: BLE001 - safe orphan, reclaimed later
                    pass
            return True

    def retrieve(
        self,
        source_kind: str,
        document_id: str | None,
        queries: list[str],
        limit: int,
        *,
        filters: RetrievalFilters | None = None,
    ) -> list[Chunk]:
        return self.retrieve_with_trace(
            source_kind, document_id, queries, limit, filters=filters
        ).chunks

    def retrieve_with_trace(
        self,
        source_kind: str,
        document_id: str | None,
        queries: list[str],
        limit: int,
        *,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        clean_queries = list(
            dict.fromkeys(query.strip() for query in queries if query.strip())
        )
        filters = filters or RetrievalFilters()
        targets = self._active_targets(source_kind, document_id, filters=filters)
        empty_trace = RetrievalTrace(
            profile_fingerprint=self.profile_fingerprint,
            source_kind=source_kind,
            document_id=document_id,
            targets=[asdict(target) for target in targets],
            queries=[],
            selected_chunk_ids=[],
            numeric_visual_reserved_chunk_ids=[],
            filters=filters.to_dict(),
        )
        if limit <= 0 or not clean_queries or not targets:
            return RetrievalResult(hits=[], trace=empty_trace)

        active_chunks = {
            point_id: stored
            for point_id, stored in self._load_active_chunks(targets).items()
            if _matches_filters(stored, filters)
        }
        if not active_chunks:
            return RetrievalResult(hits=[], trace=empty_trace)
        query_vectors = self.embedder.embed_queries(clean_queries)
        if len(query_vectors) != len(clean_queries):
            raise IndexIntegrityError(
                "query embedding 개수가 query 개수와 일치하지 않습니다."
            )

        aggregate_rankings: list[list[str]] = []
        numeric_visual_rankings: list[list[str]] = []
        explicitly_referenced_visual_ids: list[str] = []
        query_traces: list[QueryRetrievalTrace] = []
        for query, representation in zip(clean_queries, query_vectors, strict=True):
            _validate_representation(self.config, representation)
            dense = self.dense_store.query(
                representation.dense,
                targets,
                self.config.dense_k,
                allowed_point_ids=set(active_chunks),
            )
            dense = [item for item in dense if item.point_id in active_chunks]
            sparse = self._sparse_search(
                representation.sparse_indices,
                representation.sparse_values,
                active_chunks,
                self.config.sparse_k,
            )
            dense_ids = [item.point_id for item in dense]
            sparse_ids = [item.point_id for item in sparse]
            first_fusion = reciprocal_rank_fusion_ids(
                [dense_ids, sparse_ids], k=self.config.rrf_k
            )
            fused_ids = [point_id for point_id, _ in first_fusion]
            candidate_ids = fused_ids[: self.config.fusion_candidates]
            pre_colbert_visuals = _rank_relevant_numeric_visuals(
                query,
                fused_ids,
                active_chunks,
                dict(first_fusion),
            )
            if (
                pre_colbert_visuals
                and pre_colbert_visuals[0] not in candidate_ids
                and candidate_ids
            ):
                # Keep the candidate budget at 32 while allowing one exact,
                # query-relevant visual from the dense/sparse top-k union to
                # reach ColBERT instead of being lost at the RRF boundary.
                candidate_ids[-1] = pre_colbert_visuals[0]
            colbert_scores = {
                point_id: maxsim_score(
                    representation.colbert,
                    self._load_colbert(active_chunks[point_id].colbert_path),
                )
                for point_id in candidate_ids
            }
            colbert_ids = sorted(
                candidate_ids,
                key=lambda point_id: (-colbert_scores[point_id], point_id),
            )
            # Dense and learned-sparse retrieval define the fixed candidate
            # gate above.  Within that gate ColBERT is the reranker: fusing the
            # dense/sparse ranks back in here can overturn MaxSim order and
            # therefore is not a rerank at all.  A one-list RRF gives us stable
            # reciprocal scores for downstream multi-query fusion while
            # preserving the ColBERT order exactly.
            final_fusion = reciprocal_rank_fusion_ids(
                [colbert_ids],
                k=self.config.rrf_k,
            )
            final_ids = [point_id for point_id, _ in final_fusion]
            aggregate_rankings.append(final_ids)
            relevant_visuals = _rank_relevant_numeric_visuals(
                query,
                final_ids,
                active_chunks,
                dict(final_fusion),
            )
            if relevant_visuals:
                # Reserve at most one best locator per query. Related table and
                # caption chunks stay available to normal MMR without consuming
                # the small cross-query reservation budget together.
                numeric_visual_rankings.append(relevant_visuals[:1])
                if _visual_references(query):
                    explicitly_referenced_visual_ids.append(relevant_visuals[0])

            dense_rank = {
                item.point_id: rank for rank, item in enumerate(dense, start=1)
            }
            sparse_rank = {
                item.point_id: rank for rank, item in enumerate(sparse, start=1)
            }
            colbert_rank = {
                point_id: rank for rank, point_id in enumerate(colbert_ids, start=1)
            }
            dense_score = {item.point_id: item.score for item in dense}
            sparse_score = {item.point_id: item.score for item in sparse}
            final_score = dict(final_fusion)
            query_traces.append(
                QueryRetrievalTrace(
                    query=query,
                    dense_ids=dense_ids,
                    sparse_ids=sparse_ids,
                    rrf_candidate_ids=candidate_ids,
                    candidates=[
                        CandidateTrace(
                            point_id=point_id,
                            chunk_id=active_chunks[point_id].chunk.chunk_id,
                            dense_rank=dense_rank.get(point_id),
                            dense_score=dense_score.get(point_id),
                            sparse_rank=sparse_rank.get(point_id),
                            sparse_score=sparse_score.get(point_id),
                            colbert_rank=colbert_rank.get(point_id),
                            colbert_score=colbert_scores.get(point_id),
                            fused_score=final_score.get(point_id, 0.0),
                        )
                        for point_id in final_ids
                    ],
                )
            )

        aggregate = reciprocal_rank_fusion_ids(aggregate_rankings, k=self.config.rrf_k)
        aggregate_ids = [
            point_id for point_id, _ in aggregate if point_id in active_chunks
        ]
        relevance = dict(aggregate)
        reserved_ids: list[str] = []
        if numeric_visual_rankings:
            reservation_budget = min(2, limit)
            fused_visual_ids = [
                point_id
                for point_id, _ in reciprocal_rank_fusion_ids(
                    numeric_visual_rankings,
                    k=self.config.rrf_k,
                )
                if point_id in aggregate_ids
            ]
            reserved_ids = [
                point_id
                for point_id in dict.fromkeys(
                    [*explicitly_referenced_visual_ids, *fused_visual_ids]
                )
                if point_id in aggregate_ids
            ][:reservation_budget]
        dense_vectors = self.dense_store.get_vectors(aggregate_ids)
        missing_vectors = set(aggregate_ids) - set(dense_vectors)
        if missing_vectors:
            raise IndexIntegrityError(
                f"MMR에 필요한 dense vector가 없습니다: {sorted(missing_vectors)[:3]}"
            )
        selected_ids = maximal_marginal_relevance_ids(
            aggregate_ids,
            relevance,
            dense_vectors,
            limit=limit,
            lambda_mult=self.config.mmr_lambda,
            reserved=reserved_ids,
        )
        hits = [
            RetrievalHit(chunk=active_chunks[point_id].chunk, score=relevance[point_id])
            for point_id in selected_ids
        ]
        trace = RetrievalTrace(
            profile_fingerprint=self.profile_fingerprint,
            source_kind=source_kind,
            document_id=document_id,
            targets=[asdict(target) for target in targets],
            queries=query_traces,
            selected_chunk_ids=[hit.chunk.chunk_id for hit in hits],
            numeric_visual_reserved_chunk_ids=[
                active_chunks[point_id].chunk.chunk_id for point_id in reserved_ids
            ],
            filters=filters.to_dict(),
        )
        return RetrievalResult(hits=hits, trace=trace)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    source_kind TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    active_generation TEXT NOT NULL,
                    document_fingerprint TEXT NOT NULL,
                    profile_fingerprint TEXT NOT NULL,
                    point_ids_json TEXT NOT NULL,
                    PRIMARY KEY(source_kind, document_id)
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    point_id TEXT PRIMARY KEY,
                    source_kind TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    generation TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    page INTEGER,
                    section TEXT,
                    content_kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    colbert_path TEXT NOT NULL,
                    chunk_json TEXT
                );
                CREATE INDEX IF NOT EXISTS chunks_target
                    ON chunks(source_kind, document_id, generation);
                CREATE TABLE IF NOT EXISTS sparse_postings (
                    point_id TEXT NOT NULL REFERENCES chunks(point_id) ON DELETE CASCADE,
                    token_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    PRIMARY KEY(point_id, token_id)
                );
                CREATE INDEX IF NOT EXISTS sparse_token ON sparse_postings(token_id);
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(chunks)").fetchall()
            }
            if "chunk_json" not in columns:
                connection.execute("ALTER TABLE chunks ADD COLUMN chunk_json TEXT")

    def _write_profile_manifest(self) -> None:
        path = self.profile_dir / "profile.json"
        payload = {
            "profile_fingerprint": self.profile_fingerprint,
            "profile": self.config.profile_payload(),
        }
        raw = (
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise IndexIntegrityError(
                    f"BGE index profile manifest가 손상되었습니다: {exc}"
                ) from exc
            if existing != payload:
                raise IndexIntegrityError(
                    "BGE index profile directory에 다른 profile이 있습니다."
                )
        else:
            atomic_write(path, raw)

    def _document_row(self, source_kind: str, document_id: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM documents WHERE source_kind=? AND document_id=?",
                (source_kind, document_id),
            ).fetchone()

    def _active_targets(
        self,
        source_kind: str,
        document_id: str | None,
        *,
        filters: RetrievalFilters | None = None,
    ) -> list[ActiveTarget]:
        statement = (
            "SELECT source_kind,document_id,active_generation FROM documents "
            "WHERE source_kind=?"
        )
        params: list[object] = [source_kind]
        if document_id is not None:
            statement += " AND document_id=?"
            params.append(document_id)
        document_filters = tuple((filters or RetrievalFilters()).document_ids)
        if document_filters:
            placeholders = ",".join("?" for _ in document_filters)
            statement += f" AND document_id IN ({placeholders})"  # noqa: S608
            params.extend(document_filters)
        statement += " ORDER BY document_id"
        with self._connect() as connection:
            rows = connection.execute(statement, params).fetchall()
        return [
            ActiveTarget(
                row["source_kind"], row["document_id"], row["active_generation"]
            )
            for row in rows
        ]

    def _load_active_chunks(
        self, targets: Sequence[ActiveTarget]
    ) -> dict[str, _StoredChunk]:
        if not targets:
            return {}
        clauses = []
        params: list[object] = []
        for target in targets:
            clauses.append("(source_kind=? AND document_id=? AND generation=?)")
            params.extend([target.source_kind, target.document_id, target.generation])
        statement = "SELECT * FROM chunks WHERE " + " OR ".join(clauses)
        with self._connect() as connection:
            rows = connection.execute(statement, params).fetchall()
        result: dict[str, _StoredChunk] = {}
        for row in rows:
            chunk_json = row["chunk_json"]
            if chunk_json:
                try:
                    chunk = Chunk.model_validate(json.loads(chunk_json))
                except (json.JSONDecodeError, ValueError) as exc:
                    raise IndexIntegrityError(
                        f"저장된 chunk JSON이 손상되었습니다: {row['point_id']}: {exc}"
                    ) from exc
            else:
                # Databases created before the locator-rich Chunk schema did not
                # have chunk_json. Keep them readable until their next reindex.
                chunk = Chunk(
                    chunk_id=row["chunk_id"],
                    source_kind=row["source_kind"],
                    document_id=row["document_id"],
                    page=row["page"],
                    section=row["section"],
                    content_kind=row["content_kind"],
                    text=row["text"],
                    content_hash=row["content_hash"],
                )
            result[row["point_id"]] = _StoredChunk(
                point_id=row["point_id"],
                generation=row["generation"],
                colbert_path=row["colbert_path"],
                chunk=chunk,
            )
        return result

    def _sparse_search(
        self,
        query_indices: Any,
        query_values: Any,
        active_chunks: dict[str, _StoredChunk],
        limit: int,
    ) -> list[DenseCandidate]:
        query_weights = {
            int(token_id): float(weight)
            for token_id, weight in zip(query_indices, query_values, strict=True)
            if float(weight) != 0.0
        }
        if not query_weights or not active_chunks or limit <= 0:
            return []
        token_ids = sorted(query_weights)
        placeholders = ",".join("?" for _ in token_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT point_id,token_id,weight FROM sparse_postings "
                f"WHERE token_id IN ({placeholders})",  # noqa: S608 - placeholders only
                token_ids,
            ).fetchall()
        scores: dict[str, float] = defaultdict(float)
        for row in rows:
            point_id = row["point_id"]
            if point_id in active_chunks:
                scores[point_id] += query_weights[row["token_id"]] * float(
                    row["weight"]
                )
        return [
            DenseCandidate(point_id, score)
            for point_id, score in sorted(
                scores.items(), key=lambda item: (-item[1], item[0])
            )[:limit]
        ]

    def _write_colbert(self, content_hash: str, value: Any) -> str:
        import numpy as np

        array = np.asarray(value, dtype=np.float16)
        if array.ndim != 2 or array.shape[1] != self.config.colbert_dimension:
            raise IndexIntegrityError(
                f"ColBERT matrix shape가 잘못되었습니다: {array.shape}"
            )
        if array.shape[0] > self.config.max_passage_tokens:
            raise IndexIntegrityError(
                f"ColBERT token 수가 hard cap을 초과했습니다: {array.shape[0]}"
            )
        relative = Path(content_hash[:2]) / f"{content_hash}.npy"
        path = self.colbert_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self._validate_colbert_file(path)
            return relative.as_posix()
        temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("wb") as handle:
                np.save(handle, array, allow_pickle=False)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return relative.as_posix()

    def _load_colbert(self, relative: str) -> Any:
        path = (self.colbert_dir / relative).resolve()
        if not path.is_relative_to(self.colbert_dir.resolve()):
            raise IndexIntegrityError(
                "ColBERT sidecar 경로가 profile 디렉터리를 벗어났습니다."
            )
        return self._validate_colbert_file(path)

    def _validate_colbert_file(self, path: Path) -> Any:
        import numpy as np

        if not path.is_file():
            raise IndexIntegrityError(f"ColBERT sidecar가 없습니다: {path}")
        try:
            value = np.load(path, mmap_mode="r", allow_pickle=False)
        except Exception as exc:  # noqa: BLE001 - numpy raises several formats
            raise IndexIntegrityError(
                f"ColBERT sidecar를 읽을 수 없습니다: {path}: {exc}"
            ) from exc
        if value.dtype != np.float16:
            raise IndexIntegrityError(
                f"ColBERT sidecar dtype이 float16이 아닙니다: {value.dtype}"
            )
        if value.ndim != 2 or value.shape[1] != self.config.colbert_dimension:
            raise IndexIntegrityError(
                f"ColBERT sidecar shape가 잘못되었습니다: {value.shape}"
            )
        if value.shape[0] > self.config.max_passage_tokens:
            raise IndexIntegrityError(
                "ColBERT sidecar가 token hard cap을 초과했습니다."
            )
        return value

    def _delete_stale_rows(self, point_ids: Sequence[str]) -> None:
        with self._connect() as connection:
            connection.executemany(
                "DELETE FROM chunks WHERE point_id=?", [(item,) for item in point_ids]
            )


def reciprocal_rank_fusion_ids(
    rankings: Sequence[Sequence[str]], *, k: int = 60
) -> list[tuple[str, float]]:
    if k < 1:
        raise ValueError("RRF k는 1 이상이어야 합니다.")
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        seen: set[str] = set()
        for rank, point_id in enumerate(ranking, start=1):
            if point_id in seen:
                continue
            seen.add(point_id)
            scores[point_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def maxsim_score(query: Any, document: Any) -> float:
    """BGE-M3 ColBERT score: mean query-token maximum similarity."""

    import numpy as np

    query_array = np.asarray(query, dtype=np.float32)
    document_array = np.asarray(document, dtype=np.float32)
    if query_array.ndim != 2 or document_array.ndim != 2:
        raise IndexIntegrityError("MaxSim 입력은 2차원 matrix여야 합니다.")
    if query_array.shape[0] == 0 or document_array.shape[0] == 0:
        raise IndexIntegrityError("MaxSim 입력은 빈 token matrix일 수 없습니다.")
    if query_array.shape[1] != document_array.shape[1]:
        raise IndexIntegrityError("MaxSim query/document dimension이 다릅니다.")
    return float(np.max(query_array @ document_array.T, axis=1).mean())


_VISUAL_CONTENT_KINDS = frozenset({"table", "caption", "figure", "chart", "diagram"})
_VISUAL_REFERENCE_PATTERN = re.compile(
    r"(?ix)"
    r"(?:\b(table|fig(?:ure)?\.?|chart|diagram)\s*(?:no\.?\s*)?"
    r"([0-9]+|[ivxlcdm]+)\b)"
    r"|(?:(표|그림|도표)\s*([0-9]+|[ivxlcdm]+))"
)
_VISUAL_CUE_PATTERN = re.compile(
    r"(?i)(?:\b(?:table|fig(?:ure)?\.?|chart|diagram)\b|표|그림|도표)"
)
_NUMERIC_LITERAL_PATTERN = re.compile(
    r"(?i)(?<![\w.+-])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:\s*(?:%|×|x|ki?b|mi?b|gi?b|ti?b|ms|ns|us|k|m|g|t|s))?(?![a-z])"
)
_NUMERIC_QUESTION_PATTERN = re.compile(
    r"(?i)(?:\b(?:how\s+(?:many|much)|by\s+what|what|which|compare)\b|"
    r"몇|얼마|어느|비교)"
)
_NUMERIC_METRIC_PATTERN = re.compile(
    r"(?i)(?:\b(?:number|numeric|value|percent(?:age)?|ratio|rate|range|"
    r"speedups?|latenc(?:y|ies)|throughput|bandwidth|capacity|memory|tokens?|"
    r"batch(?:\s+size)?|context(?:\s+length)?|overhead|accuracy|scores?|time|"
    r"bytes?)\b|수치|값|범위|백분율|퍼센트|배속|지연|처리량|대역폭|용량|"
    r"메모리|토큰|배치|컨텍스트|오버헤드|정확도|점수|시간)"
)
_LEXICAL_TOKEN_PATTERN = re.compile(
    r"[A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)*|[가-힣]{2,}"
)
_LEXICAL_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "between",
        "by",
        "compare",
        "compared",
        "does",
        "for",
        "from",
        "how",
        "in",
        "is",
        "many",
        "much",
        "number",
        "numeric",
        "of",
        "on",
        "or",
        "paper",
        "percent",
        "percentage",
        "range",
        "ranges",
        "report",
        "reported",
        "result",
        "results",
        "show",
        "shown",
        "the",
        "to",
        "value",
        "values",
        "versus",
        "vs",
        "what",
        "which",
        "with",
        "그림",
        "도표",
        "보고",
        "비교",
        "수치",
        "어느",
        "얼마",
        "결과",
    }
)


def _rank_relevant_numeric_visuals(
    query: str,
    candidate_ids: Sequence[str],
    active_chunks: dict[str, _StoredChunk],
    relevance: dict[str, float],
) -> list[str]:
    """Rank evidence-rich visuals only when the query actually calls for them.

    This operates strictly inside the filtered dense/sparse top-k union. One
    matching locator may be admitted at the fixed RRF top-32 boundary, and the
    same predicate is applied again after ColBERT. It therefore cannot introduce
    an otherwise unretrieved visual. Exact labels such as ``Table I`` or
    ``Figure 5`` must match. For an unlabeled numeric question, at least one exact
    numeric literal or meaningful lexical term must also occur in the evidence.
    """

    query_references = _visual_references(query)
    if not query_references and not _query_has_numeric_or_visual_intent(query):
        return []
    query_numbers = _numeric_terms(query)
    query_words = _lexical_terms(query)
    ranked: list[tuple[tuple[int, int, int, int, float, str], str]] = []
    for point_id in dict.fromkeys(candidate_ids):
        stored = active_chunks.get(point_id)
        if stored is None or stored.chunk.content_kind not in _VISUAL_CONTENT_KINDS:
            continue
        chunk = stored.chunk
        searchable = "\n".join(
            value for value in (chunk.object_label, chunk.section, chunk.text) if value
        )
        candidate_references = _visual_references(searchable)
        exact_reference_matches = query_references.intersection(candidate_references)
        if query_references and not exact_reference_matches:
            continue
        number_overlap = query_numbers.intersection(_numeric_terms(searchable))
        lexical_overlap = query_words.intersection(_lexical_terms(searchable))
        if not query_references and not number_overlap and not lexical_overlap:
            continue
        kind_alignment = _visual_kind_alignment(query_references, chunk.content_kind)
        locator_precision = _visual_locator_precision(chunk)
        score = (
            len(exact_reference_matches),
            len(number_overlap),
            len(lexical_overlap),
            kind_alignment * 10 + locator_precision,
            relevance.get(point_id, 0.0),
            _reverse_lexical_key(point_id),
        )
        ranked.append((score, point_id))
    return [point_id for _, point_id in sorted(ranked, reverse=True)]


def _query_has_numeric_or_visual_intent(query: str) -> bool:
    if _visual_references(query):
        return True
    if _NUMERIC_LITERAL_PATTERN.search(query):
        return True
    if _VISUAL_CUE_PATTERN.search(query) and _lexical_terms(query):
        return True
    return bool(
        _NUMERIC_QUESTION_PATTERN.search(query)
        and _NUMERIC_METRIC_PATTERN.search(query)
    )


def _visual_references(value: str) -> set[tuple[str, str]]:
    references: set[tuple[str, str]] = set()
    for match in _VISUAL_REFERENCE_PATTERN.finditer(value):
        english_kind, english_label, korean_kind, korean_label = match.groups()
        raw_kind = (english_kind or korean_kind or "").lower().rstrip(".")
        raw_label = english_label or korean_label or ""
        canonical_kind = "table" if raw_kind in {"table", "표"} else "figure"
        references.add((canonical_kind, raw_label.upper()))
    return references


def _numeric_terms(value: str) -> set[str]:
    return {
        re.sub(r"\s+", "", match.group(0)).replace(",", "").replace("×", "x").lower()
        for match in _NUMERIC_LITERAL_PATTERN.finditer(value)
    }


def _lexical_terms(value: str) -> set[str]:
    terms: set[str] = set()
    for match in _LEXICAL_TOKEN_PATTERN.finditer(value):
        token = match.group(0).lower()
        if token in _LEXICAL_STOP_WORDS:
            continue
        terms.add(token)
        if token.isascii() and token.endswith("s") and len(token) > 4:
            terms.add(token[:-1])
    return terms


def _visual_kind_alignment(references: set[tuple[str, str]], content_kind: str) -> int:
    requested_kinds = {kind for kind, _ in references}
    if "table" in requested_kinds:
        return {"table": 5, "caption": 3}.get(content_kind, 0)
    if "figure" in requested_kinds:
        return {"figure": 5, "chart": 5, "diagram": 5, "caption": 3}.get(
            content_kind, 0
        )
    return {
        "table": 5,
        "chart": 4,
        "figure": 3,
        "diagram": 3,
        "caption": 2,
    }.get(content_kind, 0)


def _visual_locator_precision(chunk: Chunk) -> int:
    if chunk.content_kind == "table" and chunk.table_cells:
        return 4
    if chunk.crop_hash or chunk.extraction_method == "vision":
        return 3
    if chunk.bbox is not None:
        return 2
    if chunk.object_label:
        return 1
    return 0


def maximal_marginal_relevance_ids(
    candidates: Sequence[str],
    relevance: dict[str, float],
    vectors: dict[str, Any],
    *,
    limit: int,
    lambda_mult: float = 0.7,
    reserved: Sequence[str] = (),
) -> list[str]:
    if limit <= 0 or not candidates:
        return []
    maximum = max((relevance[item] for item in candidates), default=1.0) or 1.0
    remaining = list(dict.fromkeys(candidates))
    candidate_rank = {point_id: rank for rank, point_id in enumerate(remaining)}
    reserved_ids = sorted(
        [
            point_id
            for point_id in dict.fromkeys(reserved)
            if point_id in candidate_rank
        ][:limit],
        key=candidate_rank.__getitem__,
    )
    selected: list[str] = []
    while remaining and len(selected) < limit:

        def score(point_id: str) -> tuple[float, float, str]:
            normalized_relevance = relevance[point_id] / maximum
            redundancy = max(
                (_cosine(vectors[point_id], vectors[chosen]) for chosen in selected),
                default=0.0,
            )
            mmr = lambda_mult * normalized_relevance - (1.0 - lambda_mult) * redundancy
            return (mmr, relevance[point_id], _reverse_lexical_key(point_id))

        winner = max(remaining, key=score)
        selected.append(winner)
        remaining.remove(winner)

    # A visual reservation is an inclusion guarantee, not a rank boost.  Run
    # the natural MMR ordering first, then replace only the lowest-ranked
    # eligible non-reserved tail entries for locators that would otherwise be
    # absent.  Existing selections retain their relative order and newly
    # admitted locators occupy the minimum tail positions needed.
    missing_reserved = [
        point_id for point_id in reserved_ids if point_id not in selected
    ]
    if missing_reserved:
        reserved_set = set(reserved_ids)
        replacement_positions = [
            index
            for index in range(len(selected) - 1, -1, -1)
            if selected[index] not in reserved_set
        ][: len(missing_reserved)]
        replaced = set(replacement_positions)
        selected = [
            point_id for index, point_id in enumerate(selected) if index not in replaced
        ]
        selected.extend(missing_reserved[: len(replacement_positions)])
    return selected


def _reverse_lexical_key(value: str) -> str:
    # ``max`` is used by MMR. Invert code points so lexical-ascending ids win
    # deterministic ties without relying on insertion order.
    return "".join(chr(0x10FFFF - ord(character)) for character in value)


def _validate_embedder(config: BGERetrievalConfig, embedder: object) -> None:
    model_id = str(getattr(embedder, "model_id", ""))
    revision = str(getattr(embedder, "revision", ""))
    if "openai" in model_id.lower() or model_id.lower().startswith("text-embedding-"):
        raise ConfigurationError(
            "OpenAI embedding adapter는 BGE 검색에 연결할 수 없습니다."
        )
    if model_id != config.model_id or revision.lower() != config.model_revision.lower():
        raise ConfigurationError(
            "embedder model identity가 BGE index profile과 다릅니다."
        )
    embedder_files = getattr(embedder, "files_sha256", None)
    if (
        embedder_files is not None
        and str(embedder_files).lower() != config.model_files_sha256.lower()
    ):
        raise ConfigurationError(
            "embedder model file hash가 BGE index profile과 다릅니다."
        )
    if getattr(embedder, "dense_dimension", None) != config.dense_dimension:
        raise ConfigurationError("embedder dense dimension이 index profile과 다릅니다.")
    if getattr(embedder, "colbert_dimension", None) != config.colbert_dimension:
        raise ConfigurationError(
            "embedder ColBERT dimension이 index profile과 다릅니다."
        )


def _validate_representation(
    config: BGERetrievalConfig, representation: MultiRepresentation
) -> None:
    import numpy as np

    dense = np.asarray(representation.dense)
    sparse_indices = np.asarray(representation.sparse_indices)
    sparse_values = np.asarray(representation.sparse_values)
    colbert = np.asarray(representation.colbert)
    if dense.shape != (config.dense_dimension,) or not np.isfinite(dense).all():
        raise IndexIntegrityError(
            f"dense representation이 유효하지 않습니다: {dense.shape}"
        )
    if sparse_indices.ndim != 1 or sparse_values.shape != sparse_indices.shape:
        raise IndexIntegrityError("sparse representation shape가 유효하지 않습니다.")
    if not np.isfinite(sparse_values).all() or (sparse_values < 0).any():
        raise IndexIntegrityError("sparse representation 값이 유효하지 않습니다.")
    if colbert.ndim != 2 or colbert.shape[1] != config.colbert_dimension:
        raise IndexIntegrityError(
            f"ColBERT representation이 유효하지 않습니다: {colbert.shape}"
        )
    if colbert.shape[0] == 0 or colbert.shape[0] > config.max_passage_tokens:
        raise IndexIntegrityError("ColBERT token 수가 유효하지 않습니다.")
    if not np.isfinite(colbert).all():
        raise IndexIntegrityError("ColBERT representation 값이 유효하지 않습니다.")


def _document_fingerprint(
    profile_fingerprint: str,
    source_kind: str,
    document_id: str,
    chunks: Sequence[Chunk],
) -> str:
    payload = {
        "profile_fingerprint": profile_fingerprint,
        "source_kind": source_kind,
        "document_id": document_id,
        "chunks": [chunk.model_dump(mode="json", exclude={"text"}) for chunk in chunks],
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _embedding_text(chunk: Chunk) -> str:
    """Include structural labels in every retrieval representation."""

    prefixes: list[str] = []
    if chunk.section:
        prefixes.append(f"Section: {chunk.section}")
    if chunk.object_label:
        prefixes.append(f"Object: {chunk.object_label}")
    return "\n".join([*prefixes, chunk.text]) if prefixes else chunk.text


def _point_id(
    profile: str,
    source_kind: str,
    document_id: str,
    generation: str,
    chunk_id: str,
) -> str:
    identity = "|".join((profile, source_kind, document_id, generation, chunk_id))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def _chroma_target_filter(targets: Sequence[ActiveTarget]) -> dict[str, object]:
    clauses: list[dict[str, object]] = []
    for target in targets:
        clauses.append(
            {
                "$and": [
                    {"source_kind": {"$eq": target.source_kind}},
                    {"document_id": {"$eq": target.document_id}},
                    {"generation": {"$eq": target.generation}},
                ]
            }
        )
    return clauses[0] if len(clauses) == 1 else {"$or": clauses}


def _matches_filters(stored: _StoredChunk, filters: RetrievalFilters) -> bool:
    chunk = stored.chunk
    if filters.document_ids and chunk.document_id not in filters.document_ids:
        return False
    if filters.versions and not (
        (
            chunk.document_version is not None
            and chunk.document_version in filters.versions
        )
        or stored.generation in filters.versions
    ):
        return False
    if filters.pages and chunk.page not in filters.pages:
        return False
    if filters.sections and chunk.section not in filters.sections:
        return False
    if filters.content_kinds and chunk.content_kind not in filters.content_kinds:
        return False
    return True


def _cosine(left: Any, right: Any) -> float:
    import numpy as np

    a = np.asarray(left, dtype=np.float32)
    b = np.asarray(right, dtype=np.float32)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(a, b) / denominator)


def _float_list(value: Any) -> list[float]:
    import numpy as np

    return np.asarray(value, dtype=np.float32).tolist()
