"""Public API for local BGE-M3 technical research."""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from paper_review_agent.bge_retrieval import BGERetrievalConfig, BgeM3HybridRetrievalService
from paper_review_agent.config import AppConfig
from paper_review_agent.documents import LocalDocumentService
from paper_review_agent.evidence_ids import EVIDENCE_ID_VERSION
from paper_review_agent.model_management import (
    BGEModelRuntimeConfig,
    LocalBgeM3Embedder,
    load_local_snapshot,
    pull_pinned_snapshot,
)
from paper_review_agent.research_graph import (
    ResearchServices,
    _vision_run_metadata,
    build_technical_research_graph as _build_graph,
    publish_technical_failure_envelope,
)
from paper_review_agent.schemas import TokenUsage, utc_now
from paper_review_agent.technical_models import OpenAITechnicalModelGateway
from paper_review_agent.technical_schemas import (
    ModelInstallReport,
    TechnicalDiagnostic,
    TechnicalQuality,
    TechnicalResearchEnvelope,
    TechnicalResearchRequest,
    TechnicalRunMetadata,
)
from paper_review_agent.technical_validation import validate_technical_research


def run_technical_research(
    request: TechnicalResearchRequest,
    config: AppConfig | None = None,
    *,
    services: ResearchServices | None = None,
) -> TechnicalResearchEnvelope:
    """Run technical research and return the same versioned envelope written to disk."""

    config = config or AppConfig.from_env(Path.cwd())
    config.ensure_runtime_dirs()
    job_id = request.job_id or uuid.uuid4().hex
    started_at = utc_now()
    actual_services: ResearchServices | None = None
    with _technical_job_lock(config.output_dir, job_id):
        try:
            checkpoint = _load_research_checkpoint(config, job_id)
            if checkpoint:
                _validate_checkpoint_request(checkpoint, request, job_id)
                if not request.force_reindex:
                    terminal = _terminal_checkpoint_envelope(checkpoint)
                    if terminal is not None:
                        _validate_checkpoint_sources(checkpoint)
                        return _load_published_terminal_envelope(
                            config, job_id, terminal
                        )
                else:
                    # ``invoke`` merges input with the most recent channel values.
                    # A terminal failure therefore keeps ``failure_status`` unless
                    # the complete thread is removed before a forced new attempt.
                    _delete_research_checkpoint(config, job_id)

            actual_services = services or build_default_research_services(config)
            graph = _build_graph(config, actual_services)
            result = graph.invoke(
                {
                    "request": request.model_dump(mode="json"),
                    "job_id": job_id,
                    "started_at": started_at.isoformat(),
                    "errors": [],
                    "warnings": [],
                    "token_usage": TokenUsage().model_dump(),
                },
                config={"configurable": {"thread_id": job_id}},
            )
            return TechnicalResearchEnvelope.model_validate(result["final_envelope"])
        except _TechnicalJobConflictError:
            # A job ID is an immutable logical run identity.  Never replace its
            # coherent terminal generation with an error for a different request.
            raise
        except Exception as exc:  # noqa: BLE001 - public versioned failure boundary
            envelope = TechnicalResearchEnvelope(
                status="provider_error",
                run=TechnicalRunMetadata(
                    job_id=job_id,
                    openai_model=config.openai_model,
                    embedding_provider=config.research_embedding_provider,
                    embedding_model=config.bge_model_id,
                    embedding_revision=config.bge_model_revision,
                    index_profile=getattr(
                        actual_services.retrieval, "profile_id", None
                    )
                    if actual_services is not None
                    else None,
                    evidence_id_version=EVIDENCE_ID_VERSION,
                    prompt_version=config.prompt_version,
                    index_version=config.index_version,
                    vision=_vision_run_metadata(
                        config,
                        actual_services.visuals if actual_services is not None else None,
                    ),
                    started_at=started_at,
                    finished_at=utc_now(),
                ),
                quality=TechnicalQuality(),
                diagnostics=[
                    TechnicalDiagnostic(
                        node="runtime",
                        code=type(exc).__name__,
                        message=str(exc),
                    )
                ],
            )
            publish_technical_failure_envelope(config.output_dir, job_id, envelope)
            return envelope


class _TechnicalJobConflictError(ValueError):
    """The caller tried to reuse one immutable job ID for incompatible input."""


@contextmanager
def _technical_job_lock(output_dir: Path, job_id: str) -> Iterator[None]:
    """Serialize checkpoint inspection, execution, and publication per job ID."""

    job_dir = output_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    lock_path = job_dir / ".technical.run.lock"
    with lock_path.open("a+b") as handle:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except ImportError:  # pragma: no cover - supported deployment is Linux
            pass
        try:
            yield
        finally:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except ImportError:  # pragma: no cover
                pass


def _load_research_checkpoint(config: AppConfig, job_id: str) -> dict:
    """Read the latest root-graph channel values without loading model services."""

    if not config.checkpoint_enabled or not config.research_checkpoint_path.exists():
        return {}
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        return {}
    with sqlite3.connect(
        config.research_checkpoint_path, check_same_thread=False
    ) as connection:
        checkpoint = SqliteSaver(connection).get_tuple(
            {"configurable": {"thread_id": job_id}}
        )
    if checkpoint is None:
        return {}
    values = checkpoint.checkpoint.get("channel_values", {})
    return dict(values) if isinstance(values, dict) else {}


def _delete_research_checkpoint(config: AppConfig, job_id: str) -> None:
    """Start a forced attempt from an empty LangGraph thread."""

    if not config.checkpoint_enabled or not config.research_checkpoint_path.exists():
        return
    from langgraph.checkpoint.sqlite import SqliteSaver

    with sqlite3.connect(
        config.research_checkpoint_path, check_same_thread=False
    ) as connection:
        SqliteSaver(connection).delete_thread(job_id)


def _validate_checkpoint_request(
    checkpoint: dict, request: TechnicalResearchRequest, job_id: str
) -> None:
    stored_payload = checkpoint.get("request")
    if not isinstance(stored_payload, dict):
        raise _TechnicalJobConflictError(
            f"기존 job_id={job_id} 체크포인트에서 요청 계약을 확인할 수 없습니다. "
            "새 job_id를 사용하세요."
        )
    try:
        stored = TechnicalResearchRequest.model_validate(stored_payload)
    except Exception as exc:  # noqa: BLE001 - corrupted durable checkpoint
        raise _TechnicalJobConflictError(
            f"기존 job_id={job_id} 체크포인트의 요청 계약이 손상되었습니다. "
            "새 job_id를 사용하세요."
        ) from exc

    def identity(value: TechnicalResearchRequest) -> dict:
        payload = value.model_dump(mode="json")
        payload["job_id"] = job_id
        payload.pop("force_reindex", None)
        return payload

    if identity(stored) != identity(request):
        raise _TechnicalJobConflictError(
            f"job_id={job_id}는 다른 기술조사 요청에 이미 사용되었습니다. "
            "instruction, source, common-source, language가 같은 요청만 재사용할 수 "
            "있습니다. 변경된 요청에는 새 job_id를 사용하세요."
        )


def _terminal_checkpoint_envelope(
    checkpoint: dict,
) -> TechnicalResearchEnvelope | None:
    payload = checkpoint.get("final_envelope")
    if not isinstance(payload, dict):
        return None
    try:
        envelope = TechnicalResearchEnvelope.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - corrupted durable checkpoint
        raise _TechnicalJobConflictError(
            "기존 기술조사 종결 체크포인트가 손상되었습니다. 새 job_id를 사용하세요."
        ) from exc
    return envelope if envelope.status != "running" else None


def _validate_checkpoint_sources(checkpoint: dict) -> None:
    """Reject a cached terminal result when any resolved local source changed."""

    expected_by_path: dict[Path, str] = {}
    for dossier in checkpoint.get("dossiers", []):
        if not isinstance(dossier, dict):
            continue
        paper = dossier.get("paper")
        if isinstance(paper, dict) and paper.get("source_path") and paper.get(
            "source_hash"
        ):
            expected_by_path[Path(paper["source_path"]).expanduser().resolve()] = str(
                paper["source_hash"]
            )
    for work in checkpoint.get("paper_work", []):
        if not isinstance(work, dict):
            continue
        parsed = work.get("parsed_document")
        metadata = parsed.get("metadata") if isinstance(parsed, dict) else None
        if isinstance(metadata, dict) and metadata.get("source_path") and metadata.get(
            "source_hash"
        ):
            expected_by_path[
                Path(metadata["source_path"]).expanduser().resolve()
            ] = str(metadata["source_hash"])

    for path, expected in expected_by_path.items():
        if not path.is_file() or _sha256_file(path) != expected:
            raise _TechnicalJobConflictError(
                f"기존 기술조사 원본이 변경되었거나 사라졌습니다: {path}. "
                "같은 job_id로 새 색인을 만들려면 --force-reindex를 사용하세요."
            )

    expected_common = sorted(str(value) for value in checkpoint.get("common_hashes", {}).values())
    common_paths = [
        Path(value).expanduser().resolve()
        for value in checkpoint.get("common_source_paths", [])
    ]
    if expected_common:
        if any(not path.is_file() for path in common_paths):
            raise _TechnicalJobConflictError(
                "기존 기술조사의 승인 공통 코퍼스 원본이 사라졌습니다. "
                "같은 job_id로 새 색인을 만들려면 --force-reindex를 사용하세요."
            )
        current_common = sorted(_sha256_file(path) for path in common_paths)
        if current_common != expected_common:
            raise _TechnicalJobConflictError(
                "기존 기술조사의 승인 공통 코퍼스가 변경되었습니다. "
                "같은 job_id로 새 색인을 만들려면 --force-reindex를 사용하세요."
            )


def _load_published_terminal_envelope(
    config: AppConfig,
    job_id: str,
    checkpoint_envelope: TechnicalResearchEnvelope,
) -> TechnicalResearchEnvelope:
    """Return the atomically published generation bound to a terminal checkpoint."""

    base = (config.output_dir / job_id / "technical").resolve()
    filename = "run.json" if checkpoint_envelope.status == "succeeded" else "failure.json"
    path = base / filename
    opposite = base / ("failure.json" if filename == "run.json" else "run.json")
    try:
        published = TechnicalResearchEnvelope.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except Exception as exc:  # noqa: BLE001 - durable generation integrity boundary
        raise _TechnicalJobConflictError(
            f"job_id={job_id}의 체크포인트와 게시 결과가 일치하지 않습니다. "
            "기존 파일을 보존했으므로 상태를 확인한 뒤 새 job_id를 사용하세요."
        ) from exc
    if opposite.exists() or published != checkpoint_envelope:
        raise _TechnicalJobConflictError(
            f"job_id={job_id}의 체크포인트와 게시 결과가 일치하지 않습니다. "
            "기존 파일을 보존했으므로 상태를 확인한 뒤 새 job_id를 사용하세요."
        )
    for artifact in published.artifacts:
        artifact_path = Path(artifact.path).expanduser().resolve()
        if (
            not artifact_path.is_relative_to(base)
            or not artifact_path.is_file()
            or _sha256_file(artifact_path) != artifact.sha256
        ):
            raise _TechnicalJobConflictError(
                f"job_id={job_id}의 게시 아티팩트가 누락 또는 변경되었습니다: "
                f"{artifact.artifact_id}. 기존 파일을 보존했으므로 새 job_id를 "
                "사용하세요."
            )
    return published


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_default_research_services(config: AppConfig) -> ResearchServices:
    retrieval = build_bge_retrieval_service(config)
    visuals = _build_visual_service(config)
    return ResearchServices(
        documents=LocalDocumentService(
            config,
            tokenizer=_load_local_tokenizer(retrieval.embedder.model_path),
        ),
        retrieval=retrieval,
        models=OpenAITechnicalModelGateway(config),
        visuals=visuals,
    )


def build_bge_retrieval_service(config: AppConfig) -> BgeM3HybridRetrievalService:
    snapshot_dir = config.model_dir / f"bge-m3-{config.bge_model_revision[:12].lower()}"
    snapshot = load_local_snapshot(
        snapshot_dir,
        expected_model_id=config.bge_model_id,
        expected_revision=config.bge_model_revision,
    )
    embedder = LocalBgeM3Embedder(
        BGEModelRuntimeConfig.from_snapshot(
            snapshot,
            device=config.bge_device,
            max_query_tokens=config.bge_query_max_tokens,
            max_passage_tokens=config.bge_chunk_hard_limit,
            cuda_batch_size=max(1, config.bge_batch_size),
        )
    )
    return BgeM3HybridRetrievalService(
        BGERetrievalConfig(
            index_root=config.index_dir,
            model_path=snapshot.path,
            model_revision=snapshot.revision,
            model_id=snapshot.model_id,
            model_files_sha256=snapshot.files_sha256,
            target_chunk_tokens=config.bge_chunk_tokens,
            chunk_overlap_tokens=config.bge_chunk_overlap_tokens,
            max_passage_tokens=config.bge_chunk_hard_limit,
            max_query_tokens=config.bge_query_max_tokens,
            dense_k=config.bge_dense_k,
            sparse_k=config.bge_sparse_k,
            fusion_candidates=config.bge_fusion_k,
            mmr_lambda=config.bge_mmr_lambda,
        ),
        embedder,
    )


def build_technical_research_graph(
    config: AppConfig, services: ResearchServices | None = None
):
    config.ensure_runtime_dirs()
    return _build_graph(config, services or build_default_research_services(config))


def pull_embedding_model(
    model_id: str = "BAAI/bge-m3",
    revision: str = "5617a9f61b028005a4858fdac845db406aefb181",
    config: AppConfig | None = None,
) -> ModelInstallReport:
    config = config or AppConfig.from_env(Path.cwd())
    config.ensure_runtime_dirs()
    if model_id != config.bge_model_id or revision != config.bge_model_revision:
        from paper_review_agent.exceptions import ConfigurationError

        raise ConfigurationError(
            "기술조사 모델은 AppConfig에 고정된 BGE-M3 model_id와 revision만 설치할 수 있습니다."
        )
    target = config.model_dir / f"bge-m3-{revision[:12].lower()}"
    existed = (target / ".paper-review-model.json").is_file()
    snapshot = pull_pinned_snapshot(
        config.model_dir,
        revision=revision,
        model_id=model_id,
    )
    return ModelInstallReport(
        model_id=snapshot.model_id,
        revision=snapshot.revision,
        local_path=str(snapshot.path),
        files_sha256=snapshot.files_sha256,
        already_present=existed,
    )


def _build_visual_service(config: AppConfig):
    """Construct selective visual enrichment when its optional runtime is available."""

    try:
        from paper_review_agent.vision import build_visual_enrichment_service
    except (ImportError, AttributeError):
        return None
    return build_visual_enrichment_service(config)


def _load_local_tokenizer(model_path: Path):
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        from paper_review_agent.exceptions import DependencyError

        raise DependencyError("BGE token 기반 청크에는 transformers가 필요합니다.") from exc
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_path),
        local_files_only=True,
        trust_remote_code=False,
    )
    return lambda text: tokenizer.encode(text, add_special_tokens=False)


__all__ = [
    "build_default_research_services",
    "build_bge_retrieval_service",
    "build_technical_research_graph",
    "pull_embedding_model",
    "run_technical_research",
    "validate_technical_research",
]
