"""Configuration and policy enforcement."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

from paper_review_agent.exceptions import ConfigurationError


class AppConfig(BaseModel):
    """Runtime configuration with conservative local-MVP defaults."""

    root_dir: Path = Field(default_factory=Path.cwd)
    output_dir: Path | None = None
    input_dir: Path | None = None
    work_dir: Path | None = None
    index_dir: Path | None = None
    model_dir: Path | None = None
    research_checkpoint_path: Path | None = None

    openai_model: str = "gpt-5.6-terra"
    audit_provider: Literal["openai"] = "openai"
    audit_model: str = "gpt-5.6-terra"
    openai_reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"

    chunk_chars: int = 3200
    chunk_overlap_chars: int = 480
    research_embedding_provider: Literal["bge-m3"] = "bge-m3"
    bge_model_id: str = "BAAI/bge-m3"
    bge_model_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    bge_embedding_dimension: int = 1024
    bge_device: Literal["cpu", "cuda", "auto"] = "cpu"
    bge_batch_size: int = 1
    bge_chunk_tokens: int = 800
    bge_chunk_overlap_tokens: int = 120
    bge_chunk_hard_limit: int = 896
    bge_query_max_tokens: int = 128
    bge_dense_k: int = 24
    bge_sparse_k: int = 24
    bge_fusion_k: int = 32
    bge_mmr_lambda: float = 0.7
    vision_model: str | None = None
    vision_max_visuals_per_paper: int = 8
    vision_max_requests_per_paper: int = 12
    vision_max_pixels_per_paper: int = 32_000_000
    vision_concurrency: int = 2
    research_concurrency: int = 3
    max_quality_repairs: int = 2
    min_text_chars: int = 1000
    checkpoint_enabled: bool = True
    prompt_version: str = "1.0.0"
    index_version: str = "1.2.0"

    @model_validator(mode="after")
    def resolve_paths_and_enforce_policy(self) -> AppConfig:
        root = self.root_dir.expanduser().resolve()
        self.root_dir = root
        self.output_dir = (self.output_dir or root / "outputs").expanduser().resolve()
        self.input_dir = (self.input_dir or root / "inputs").expanduser().resolve()
        self.work_dir = (self.work_dir or root / "work").expanduser().resolve()
        self.index_dir = (self.index_dir or root / "data" / "index").expanduser().resolve()
        self.model_dir = (self.model_dir or root / "data" / "models").expanduser().resolve()
        self.research_checkpoint_path = (
            self.research_checkpoint_path or self.work_dir / "research-checkpoints.sqlite"
        ).expanduser().resolve()
        research_provider = self.research_embedding_provider.lower()
        if research_provider != "bge-m3" or "openai" in self.bge_model_id.lower():
            raise ConfigurationError("기술조사 임베딩은 bge-m3만 허용되며 OpenAI 임베딩은 금지됩니다.")
        if self.bge_model_id != "BAAI/bge-m3":
            raise ConfigurationError("기술조사 기본 임베딩 모델은 BAAI/bge-m3로 고정됩니다.")
        if self.bge_model_revision != "5617a9f61b028005a4858fdac845db406aefb181":
            raise ConfigurationError(
                "기술조사 BGE-M3 revision은 검증된 commit "
                "5617a9f61b028005a4858fdac845db406aefb181로 고정됩니다."
            )
        if self.bge_embedding_dimension != 1024:
            raise ConfigurationError("BGE-M3 dense 차원은 1024로 고정됩니다.")
        if self.bge_chunk_overlap_tokens >= self.bge_chunk_tokens:
            raise ConfigurationError("BGE 청크 중첩은 목표 청크 크기보다 작아야 합니다.")
        if self.bge_chunk_tokens > self.bge_chunk_hard_limit or self.bge_chunk_hard_limit > 896:
            raise ConfigurationError("BGE 청크는 target<=hard_limit<=896이어야 합니다.")
        if self.bge_batch_size < 1:
            raise ConfigurationError("BGE batch size는 1 이상이어야 합니다.")
        if not 0.0 <= self.bge_mmr_lambda <= 1.0:
            raise ConfigurationError("BGE MMR lambda는 0과 1 사이여야 합니다.")
        if min(
            self.bge_dense_k,
            self.bge_sparse_k,
            self.bge_fusion_k,
            self.vision_max_visuals_per_paper,
            self.vision_max_requests_per_paper,
            self.vision_max_pixels_per_paper,
            self.vision_concurrency,
            self.research_concurrency,
        ) < 1:
            raise ConfigurationError("BGE 검색·Vision·연구 동시성 설정은 1 이상이어야 합니다.")
        if self.vision_max_requests_per_paper < self.vision_max_visuals_per_paper:
            raise ConfigurationError("Vision request 한도는 visual 한도 이상이어야 합니다.")
        if self.chunk_overlap_chars >= self.chunk_chars:
            raise ConfigurationError("chunk_overlap_chars는 chunk_chars보다 작아야 합니다.")
        return self

    @classmethod
    def from_env(cls, root_dir: Path | None = None) -> AppConfig:
        """Load non-secret settings from PRA_* variables; keys stay in provider SDKs."""

        effective_root = (root_dir or Path.cwd()).expanduser().resolve()
        load_dotenv(effective_root / ".env", override=False)
        # Paper text and company context must not be copied to a third-party
        # tracing backend merely because a developer-wide .env enables
        # LangSmith.  Provider SDK calls remain available, but tracing is
        # fail-closed for every CLI/API entry point that builds AppConfig.
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGSMITH_TRACING"] = "false"
        values: dict[str, object] = {}
        values["root_dir"] = effective_root
        mappings = {
            "PRA_OPENAI_MODEL": "openai_model",
            "PRA_AUDIT_MODEL": "audit_model",
            "PRA_OPENAI_REASONING_EFFORT": "openai_reasoning_effort",
            "PRA_OUTPUT_DIR": "output_dir",
            "PRA_INPUT_DIR": "input_dir",
            "PRA_WORK_DIR": "work_dir",
            "PRA_INDEX_DIR": "index_dir",
            "PRA_MODEL_DIR": "model_dir",
            "PRA_RESEARCH_EMBEDDING_PROVIDER": "research_embedding_provider",
            "PRA_BGE_MODEL_ID": "bge_model_id",
            "PRA_BGE_MODEL_REVISION": "bge_model_revision",
            "PRA_BGE_DEVICE": "bge_device",
            "PRA_VISION_MODEL": "vision_model",
        }
        for env_name, field_name in mappings.items():
            value = os.getenv(env_name)
            if value:
                values[field_name] = value
        integer_mappings = {
            "PRA_BGE_BATCH_SIZE": "bge_batch_size",
            "PRA_BGE_CHUNK_TOKENS": "bge_chunk_tokens",
            "PRA_BGE_CHUNK_OVERLAP_TOKENS": "bge_chunk_overlap_tokens",
            "PRA_BGE_CHUNK_HARD_LIMIT": "bge_chunk_hard_limit",
            "PRA_BGE_QUERY_MAX_TOKENS": "bge_query_max_tokens",
            "PRA_BGE_DENSE_K": "bge_dense_k",
            "PRA_BGE_SPARSE_K": "bge_sparse_k",
            "PRA_BGE_FUSION_K": "bge_fusion_k",
            "PRA_VISION_MAX_VISUALS_PER_PAPER": "vision_max_visuals_per_paper",
            "PRA_VISION_MAX_REQUESTS_PER_PAPER": "vision_max_requests_per_paper",
            "PRA_VISION_MAX_PIXELS_PER_PAPER": "vision_max_pixels_per_paper",
            "PRA_VISION_CONCURRENCY": "vision_concurrency",
            "PRA_RESEARCH_CONCURRENCY": "research_concurrency",
        }
        for env_name, field_name in integer_mappings.items():
            raw = os.getenv(env_name)
            if raw:
                try:
                    values[field_name] = int(raw)
                except ValueError as exc:
                    raise ConfigurationError(f"{env_name} 값은 정수여야 합니다.") from exc
        if os.getenv("PRA_BGE_MMR_LAMBDA"):
            try:
                values["bge_mmr_lambda"] = float(os.environ["PRA_BGE_MMR_LAMBDA"])
            except ValueError as exc:
                raise ConfigurationError("PRA_BGE_MMR_LAMBDA 값은 숫자여야 합니다.") from exc
        return cls(**values)

    def ensure_runtime_dirs(self) -> None:
        # The application contract permits only model APIs and explicit arXiv downloads.
        # Prevent ambient shell/.env settings from exporting paper content to LangSmith.
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        for path in (
            self.output_dir,
            self.input_dir,
            self.work_dir,
            self.index_dir,
            self.model_dir,
            self.research_checkpoint_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)
