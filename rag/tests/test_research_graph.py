from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from paper_review_agent.config import AppConfig
from paper_review_agent.documents import LocalDocumentService
from paper_review_agent.research_graph import (
    ResearchServices,
    TechnicalResearchWorkflow,
    _PaperResearchFailure,
    _facet_for_topic,
    _paper_research_cache_path,
    _resolve_common_sources,
    _resolve_sources,
    _stage_visual_artifacts,
    _write_failed_paper_draft,
    build_technical_research_graph,
)
from paper_review_agent.research_api import run_technical_research
from paper_review_agent.schemas import (
    Chunk,
    GroundedClaim,
    LimitationsAnalysis,
    PaperAnalysis,
    PaperMetadata,
    ParsedDocument,
    ScopeAnalysis,
    TechnicalOverview,
    TokenUsage,
    utc_now,
)
from paper_review_agent.technical_schemas import (
    CriticalClaimItem,
    ComparisonCell,
    DifferingAssumption,
    DossierExtraction,
    EvidenceLocator,
    ExperimentObservation,
    MetricComparison,
    PaperAssumption,
    ResearchQueryPlan,
    TechnicalAudit,
    TechnicalAuditItem,
    TechnicalComparison,
    TechnicalEvidence,
    TechnicalFacetExtraction,
    TechnologyRelationship,
    TechnicalResearchEnvelope,
    TechnicalResearchRequest,
    TechnicalClaim,
    UnverifiedItem,
)
from paper_review_agent.technical_validation import analysis_audit_item_ids
from paper_review_agent.technical_validation import validate_technical_research


class FakeDocuments:
    def resolve_source(self, source: str):
        return Path(source).resolve(), None

    def parse(
        self,
        path: Path,
        *,
        document_id: str | None,
        source_kind: str,
        arxiv_id: str | None = None,
        enforce_quality: bool = True,
    ) -> ParsedDocument:
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        paper_id = document_id or path.stem
        text = f"{path.stem}: measured 4.5× decode speedup at 128K context."
        chunk = Chunk(
            chunk_id=f"chunk-{path.stem}",
            source_kind=source_kind,
            document_id=paper_id,
            document_version=source_hash,
            page=1,
            section="Results",
            content_kind="text",
            text=text,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
        )
        return ParsedDocument(
            metadata=PaperMetadata(
                paper_id=paper_id,
                title=f"Paper {path.stem}",
                source_path=str(path),
                source_hash=source_hash,
                page_count=1,
            ),
            elements=[],
            chunks=[chunk],
            character_count=len(text),
        )


class FakeRetrieval:
    profile_id = "test-profile"

    def __init__(self):
        self.chunks: dict[str, list[Chunk]] = {}

    def index_chunks(self, chunks: list[Chunk], *, force: bool = False) -> bool:
        self.chunks[chunks[0].document_id] = list(chunks)
        return True

    def retrieve(self, source_kind, document_id, queries, limit, *, filters=None):
        if document_id is not None:
            return self.chunks.get(document_id, [])[:limit]
        allowed = set(filters.document_ids) if filters is not None else set(self.chunks)
        values = [
            chunk
            for key, chunks in self.chunks.items()
            if key in allowed
            for chunk in chunks
            if chunk.source_kind == source_kind
        ]
        return values[:limit]


class RecordingRetrieval(FakeRetrieval):
    def __init__(self):
        super().__init__()
        self.calls: list[tuple[str, int, tuple[str, ...]]] = []

    def retrieve(self, source_kind, document_id, queries, limit, *, filters=None):
        self.calls.append(
            (
                source_kind,
                limit,
                tuple(filters.document_ids) if filters is not None else (),
            )
        )
        return super().retrieve(
            source_kind, document_id, queries, limit, filters=filters
        )


class FakeTechnicalModels:
    def __init__(self, *, invalid_comparison: bool = False):
        self.invalid_comparison = invalid_comparison

    def plan_queries(self, paper, instruction):
        return ResearchQueryPlan(
            critical_inventory=["abstract contributions"],
            mechanisms=["method"],
            experiments=["results"],
            scope=["scope"],
            limitations=["limitations"],
        ), TokenUsage(total_tokens=1)

    def extract_dossier(
        self,
        *,
        paper,
        evidence,
        instruction,
        output_language,
        repair_feedback=None,
    ):
        evidence_id = evidence[0].evidence_id
        claim_id = f"claim-{paper.paper_id}"
        observation_id = f"obs-{paper.paper_id}"

        def grounded(text: str) -> GroundedClaim:
            return GroundedClaim(
                text=text,
                claim_type="author_claim",
                evidence_ids=[evidence_id],
                confidence=0.8,
            )

        analysis = PaperAnalysis(
            technical_overview=TechnicalOverview(
                problem_definition=[grounded("KV cache가 병목이다.")],
                core_approach=[grounded("KV cache를 압축한다.")],
                experimental_results=[grounded("4.5× decode speedup을 측정했다.")],
            ),
            scope=ScopeAnalysis(),
            limitations=LimitationsAnalysis(
                author_stated=[grounded("추가 환경 검증이 필요하다.")]
            ),
        )
        extraction = DossierExtraction(
            analysis=analysis,
            claims=[
                {
                    "claim_id": claim_id,
                    "text": "KV cache를 압축한다.",
                    "claim_type": "author_claim",
                    "evidence_ids": [evidence_id],
                    "confidence": 0.8,
                    "critical": True,
                }
            ],
            critical_inventory=[
                CriticalClaimItem(
                    inventory_id=f"inventory-{paper.paper_id}",
                    category="contribution",
                    summary="KV cache 압축",
                    disposition="extracted",
                    claim_ids=[claim_id],
                    evidence_ids=[evidence_id],
                )
            ],
            experiment_observations=[
                ExperimentObservation(
                    observation_id=observation_id,
                    metric="decode speedup",
                    value="4.5×",
                    unit="×",
                    direction="higher_is_better",
                    baseline="FullKV FlashAttention-2",
                    model="LLaMA-3.1-8B-Instruct",
                    hardware=f"{paper.paper_id}-GPU",
                    context_length="128K",
                    workload="autoregressive decode",
                    evaluation_mode="measured",
                    evidence_ids=[evidence_id],
                    confidence=0.9,
                )
            ],
        )
        return extraction, TokenUsage(total_tokens=2)

    def audit_dossier(self, dossier, evidence):
        item_ids = (
            [item.claim_id for item in dossier.claims]
            + [item.observation_id for item in dossier.experiment_observations]
            + analysis_audit_item_ids(dossier)
        )
        return TechnicalAudit(
            audits=[
                TechnicalAuditItem(
                    item_id=item_id,
                    verdict="supported",
                    reason="근거 일치",
                )
                for item_id in item_ids
            ]
        ), TokenUsage(total_tokens=1)

    def compare(self, *, instruction, dossiers, evidence, repair_feedback=None):
        observation_ids = [
            dossier.experiment_observations[0].observation_id for dossier in dossiers
        ]
        comparison = TechnicalComparison(
            relationships=[
                TechnologyRelationship(
                    left_paper_id=dossiers[0].paper.paper_id,
                    right_paper_id=dossiers[1].paper.paper_id,
                    relationship="orthogonal",
                    rationale="서로 다른 기술 계층을 다룬다.",
                    evidence_ids=[
                        dossiers[0].evidence_ids[0],
                        dossiers[1].evidence_ids[0],
                    ],
                )
            ],
            differing_assumptions=[
                DifferingAssumption(
                    assumption_id="assumption-hardware",
                    dimension="hardware",
                    paper_assumptions=[
                        PaperAssumption(
                            paper_id=dossier.paper.paper_id,
                            statement=f"{dossier.paper.paper_id}-GPU에서 측정했다.",
                            evidence_ids=[dossier.evidence_ids[0]],
                        )
                        for dossier in dossiers
                    ],
                    implication="측정 하드웨어가 달라 수치를 직접 비교할 수 없다.",
                )
            ],
            matrix=[
                ComparisonCell(
                    dimension="mechanism",
                    paper_id=dossier.paper.paper_id,
                    summary="기술 메커니즘",
                    evidence_ids=[dossier.evidence_ids[0]],
                )
                for dossier in dossiers
            ],
            metric_comparisons=[
                MetricComparison(
                    comparison_id="cmp-decode-speedup",
                    metric="decode speedup",
                    observation_ids=observation_ids,
                    comparability="comparable"
                    if self.invalid_comparison
                    else "not_comparable",
                    reason=(
                        "직접 비교할 수 있다."
                        if self.invalid_comparison
                        else "서로 다른 GPU에서 측정되어 직접 비교할 수 없다."
                    ),
                )
            ],
        )
        return comparison, TokenUsage(total_tokens=1)


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        root_dir=tmp_path,
        checkpoint_enabled=False,
        min_text_chars=1,
        research_concurrency=2,
    )


def _sources(tmp_path: Path) -> list[Path]:
    paths = []
    for name in ("paper-a.txt", "paper-b.txt"):
        path = tmp_path / name
        path.write_text(f"distinct content for {name}", encoding="utf-8")
        paths.append(path)
    return paths


def _run_graph(
    tmp_path: Path, *, invalid_comparison: bool = False
) -> TechnicalResearchEnvelope:
    config = _config(tmp_path)
    paths = _sources(tmp_path)
    services = ResearchServices(
        documents=FakeDocuments(),
        retrieval=FakeRetrieval(),
        models=FakeTechnicalModels(invalid_comparison=invalid_comparison),
    )
    graph = build_technical_research_graph(config, services)
    request = TechnicalResearchRequest(
        instruction="두 논문을 기술적으로 비교해줘",
        sources=[str(path) for path in paths],
        job_id="technical-job",
    )
    result = graph.invoke(
        {
            "request": request.model_dump(mode="json"),
            "job_id": request.job_id,
            "started_at": utc_now().isoformat(),
        }
    )
    return TechnicalResearchEnvelope.model_validate(result["final_envelope"])


def test_technical_research_graph_exposes_real_paper_stage_topology(tmp_path: Path):
    config = _config(tmp_path)
    graph = build_technical_research_graph(
        config,
        ResearchServices(
            documents=FakeDocuments(),
            retrieval=FakeRetrieval(),
            models=FakeTechnicalModels(),
        ),
    )

    expanded = graph.get_graph(xray=True)
    nodes = set(expanded.nodes)
    expected = {
        "research_documents:index_common_sources",
        "research_documents:parse_documents",
        "research_documents:seed_critical_inventory",
        "research_documents:index_paper_sources",
        "research_documents:plan_paper_queries",
        "research_documents:retrieve_paper_evidence",
        "research_documents:enrich_paper_visuals",
        "research_documents:extract_paper_dossiers",
        "research_documents:audit_paper_dossiers",
        "research_documents:collect_documents",
    }
    assert expected <= nodes

    edges = {(edge.source, edge.target) for edge in expanded.edges}
    ordered = [
        "research_documents:index_common_sources",
        "research_documents:parse_documents",
        "research_documents:seed_critical_inventory",
        "research_documents:index_paper_sources",
        "research_documents:plan_paper_queries",
        "research_documents:retrieve_paper_evidence",
        "research_documents:enrich_paper_visuals",
        "research_documents:extract_paper_dossiers",
        "research_documents:audit_paper_dossiers",
    ]
    assert all(pair in edges for pair in zip(ordered, ordered[1:]))
    assert (
        "research_documents:audit_paper_dossiers",
        "research_documents:extract_paper_dossiers",
    ) in edges
    assert (
        "research_documents:audit_paper_dossiers",
        "research_documents:collect_documents",
    ) in edges


def test_staged_graph_repairs_only_the_failed_paper(tmp_path: Path):
    class PaperSelectiveRepairModels(FakeTechnicalModels):
        def __init__(self):
            super().__init__()
            self.extract_calls: dict[str, int] = {}
            self.audit_calls: dict[str, int] = {}

        def extract_dossier(self, **kwargs):
            paper_id = kwargs["paper"].paper_id
            self.extract_calls[paper_id] = self.extract_calls.get(paper_id, 0) + 1
            return super().extract_dossier(**kwargs)

        def audit_dossier(self, dossier, evidence):
            paper_id = dossier.paper.paper_id
            self.audit_calls[paper_id] = self.audit_calls.get(paper_id, 0) + 1
            audit, usage = super().audit_dossier(dossier, evidence)
            if paper_id.startswith("paper-a-") and self.audit_calls[paper_id] == 1:
                audit = audit.model_copy(
                    update={"missing_critical_topics": ["headline result repair"]}
                )
            return audit, usage

    config = _config(tmp_path)
    paths = _sources(tmp_path)
    models = PaperSelectiveRepairModels()
    graph = build_technical_research_graph(
        config,
        ResearchServices(
            documents=FakeDocuments(),
            retrieval=FakeRetrieval(),
            models=models,
        ),
    )
    request = TechnicalResearchRequest(
        instruction="두 논문을 기술적으로 비교해줘",
        sources=[str(path) for path in paths],
        job_id="selective-paper-repair",
    )

    result = graph.invoke(
        {
            "request": request.model_dump(mode="json"),
            "job_id": request.job_id,
            "started_at": utc_now().isoformat(),
        }
    )
    envelope = TechnicalResearchEnvelope.model_validate(result["final_envelope"])

    assert envelope.status == "succeeded"
    paper_a = next(key for key in models.extract_calls if key.startswith("paper-a-"))
    paper_b = next(key for key in models.extract_calls if key.startswith("paper-b-"))
    assert models.extract_calls[paper_a] == 2
    assert models.audit_calls[paper_a] == 2
    assert models.extract_calls[paper_b] == 1
    assert models.audit_calls[paper_b] == 1


def test_staged_graph_runs_facets_concurrently_and_repairs_only_failed_facet(
    tmp_path: Path,
):
    class FacetModels(FakeTechnicalModels):
        def __init__(self):
            super().__init__()
            self.calls: dict[tuple[str, str], int] = {}
            self.audit_calls: dict[str, int] = {}
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def extract_dossier_facet(self, *, facet, **kwargs):
            paper = kwargs["paper"]
            key = (paper.paper_id, facet)
            self.calls[key] = self.calls.get(key, 0) + 1
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            try:
                # Long enough for the per-paper executor and workflow-wide
                # semaphore to demonstrate real overlap without slowing tests.
                time.sleep(0.02)
                full, _ = super().extract_dossier(
                    paper=paper,
                    evidence=kwargs["evidence"],
                    instruction=kwargs["instruction"],
                    output_language=kwargs["output_language"],
                    repair_feedback=kwargs.get("repair_feedback"),
                )
                if facet == "technical_overview":
                    return TechnicalFacetExtraction(
                        facet=facet,
                        technical_overview=full.analysis.technical_overview,
                        claims=full.claims,
                        critical_inventory=full.critical_inventory,
                        experiment_observations=full.experiment_observations,
                    ), TokenUsage(total_tokens=2)
                if facet == "scope":
                    evidence_id = kwargs["evidence"][0].evidence_id
                    scope_text = (
                        "128K context에서 평가했다."
                        if self.calls[key] == 1
                        else "보강 감사 후 128K context 평가 조건을 확인했다."
                    )
                    scope = ScopeAnalysis(
                        operating_conditions=[
                            GroundedClaim(
                                text=scope_text,
                                claim_type="observed_result",
                                evidence_ids=[evidence_id],
                                confidence=0.8,
                            )
                        ]
                    )
                    return TechnicalFacetExtraction(
                        facet=facet,
                        scope=scope,
                    ), TokenUsage(total_tokens=2)
                return TechnicalFacetExtraction(
                    facet=facet,
                    limitations=full.analysis.limitations,
                ), TokenUsage(total_tokens=2)
            finally:
                with self.lock:
                    self.active -= 1

        def audit_dossier(self, dossier, evidence):
            paper_id = dossier.paper.paper_id
            self.audit_calls[paper_id] = self.audit_calls.get(paper_id, 0) + 1
            audit, usage = super().audit_dossier(dossier, evidence)
            if paper_id.startswith("paper-a-") and self.audit_calls[paper_id] == 1:
                audits = [
                    item.model_copy(
                        update={
                            "verdict": "partial",
                            "reason": "scope operating condition needs repair",
                        }
                    )
                    if item.item_id == "analysis.scope.operating_conditions[0]"
                    else item
                    for item in audit.audits
                ]
                audit = audit.model_copy(update={"audits": audits})
            return audit, usage

    config = AppConfig(
        root_dir=tmp_path,
        checkpoint_enabled=False,
        min_text_chars=1,
        research_concurrency=3,
    )
    paths = _sources(tmp_path)
    models = FacetModels()
    graph = build_technical_research_graph(
        config,
        ResearchServices(
            documents=FakeDocuments(),
            retrieval=FakeRetrieval(),
            models=models,
        ),
    )
    request = TechnicalResearchRequest(
        instruction="두 논문을 기술적으로 비교해줘",
        sources=[str(path) for path in paths],
        job_id="facet-selective-repair",
    )

    result = graph.invoke(
        {
            "request": request.model_dump(mode="json"),
            "job_id": request.job_id,
            "started_at": utc_now().isoformat(),
        }
    )
    envelope = TechnicalResearchEnvelope.model_validate(result["final_envelope"])

    assert envelope.status == "succeeded"
    paper_a = next(key for key in models.audit_calls if key.startswith("paper-a-"))
    paper_b = next(key for key in models.audit_calls if key.startswith("paper-b-"))
    assert models.calls[(paper_a, "technical_overview")] == 1
    assert models.calls[(paper_a, "scope")] == 2
    assert models.calls[(paper_a, "limitations")] == 1
    assert models.calls[(paper_b, "technical_overview")] == 1
    assert models.calls[(paper_b, "scope")] == 1
    assert models.calls[(paper_b, "limitations")] == 1
    assert models.audit_calls[paper_a] == 2
    assert models.audit_calls[paper_b] == 1
    assert 2 <= models.max_active <= 3
    repaired = next(
        dossier for dossier in envelope.dossiers if dossier.paper.paper_id == paper_a
    )
    # The repaired facet replaces its prior payload. It must not be additively
    # merged with the complete previous dossier and retain both wordings.
    assert [
        item.text for item in repaired.analysis.scope.operating_conditions
    ] == ["보강 감사 후 128K context 평가 조건을 확인했다."]


@pytest.mark.parametrize(
    ("topic", "expected"),
    [
        ("frozen-after-prefill limitation", "limitations"),
        ("author-stated pending physical validation", "limitations"),
        ("evaluated dataset and operating conditions", "scope"),
        ("headline mechanism and result", "technical_overview"),
    ],
)
def test_missing_audit_topics_map_to_one_deterministic_facet(topic, expected):
    assert _facet_for_topic(topic) == expected


def test_staged_graph_runs_with_sqlite_checkpointer(tmp_path: Path):
    config = AppConfig(
        root_dir=tmp_path,
        checkpoint_enabled=True,
        min_text_chars=1,
        research_concurrency=2,
    )
    config.ensure_runtime_dirs()
    paths = _sources(tmp_path)
    graph = build_technical_research_graph(
        config,
        ResearchServices(
            documents=FakeDocuments(),
            retrieval=FakeRetrieval(),
            models=FakeTechnicalModels(),
        ),
    )
    request = TechnicalResearchRequest(
        instruction="두 논문을 기술적으로 비교해줘",
        sources=[str(path) for path in paths],
        job_id="staged-checkpoint",
    )

    result = graph.invoke(
        {
            "request": request.model_dump(mode="json"),
            "job_id": request.job_id,
            "started_at": utc_now().isoformat(),
        },
        config={"configurable": {"thread_id": request.job_id}},
    )
    envelope = TechnicalResearchEnvelope.model_validate(result["final_envelope"])

    assert envelope.status == "succeeded"
    assert config.research_checkpoint_path.is_file()


def test_public_api_returns_identical_terminal_failure_for_same_checkpointed_job(
    tmp_path: Path,
):
    class CountingModels(FakeTechnicalModels):
        def __init__(self):
            super().__init__(invalid_comparison=True)
            self.compare_calls = 0

        def compare(self, **kwargs):
            self.compare_calls += 1
            return super().compare(**kwargs)

    config = AppConfig(
        root_dir=tmp_path,
        checkpoint_enabled=True,
        min_text_chars=1,
        research_concurrency=2,
    )
    config.ensure_runtime_dirs()
    paths = _sources(tmp_path)
    models = CountingModels()
    services = ResearchServices(
        documents=FakeDocuments(),
        retrieval=FakeRetrieval(),
        models=models,
    )
    request = TechnicalResearchRequest(
        instruction="두 논문을 기술적으로 비교해줘",
        sources=[str(path) for path in paths],
        job_id="terminal-failure",
    )

    first = run_technical_research(request, config, services=services)
    first_calls = models.compare_calls
    failure_path = (
        tmp_path / "outputs" / "terminal-failure" / "technical" / "failure.json"
    )
    first_raw = failure_path.read_bytes()
    second = run_technical_research(request, config, services=services)

    assert first.status == "failed_quality"
    assert first.diagnostics
    assert second == first
    assert second.diagnostics == first.diagnostics
    assert models.compare_calls == first_calls
    assert failure_path.read_bytes() == first_raw


def test_public_api_force_reindex_starts_fresh_checkpoint_attempt(tmp_path: Path):
    class CountingModels(FakeTechnicalModels):
        def __init__(self):
            super().__init__(invalid_comparison=True)
            self.compare_calls = 0

        def compare(self, **kwargs):
            self.compare_calls += 1
            return super().compare(**kwargs)

    config = AppConfig(
        root_dir=tmp_path,
        checkpoint_enabled=True,
        min_text_chars=1,
        research_concurrency=2,
    )
    config.ensure_runtime_dirs()
    paths = _sources(tmp_path)
    models = CountingModels()
    services = ResearchServices(
        documents=FakeDocuments(),
        retrieval=FakeRetrieval(),
        models=models,
    )
    request = TechnicalResearchRequest(
        instruction="두 논문을 기술적으로 비교해줘",
        sources=[str(path) for path in paths],
        job_id="forced-terminal-retry",
    )
    failed = run_technical_research(request, config, services=services)
    failed_calls = models.compare_calls
    models.invalid_comparison = False

    succeeded = run_technical_research(
        request.model_copy(update={"force_reindex": True}),
        config,
        services=services,
    )
    base = tmp_path / "outputs" / "forced-terminal-retry" / "technical"

    assert failed.status == "failed_quality"
    assert succeeded.status == "succeeded"
    assert models.compare_calls > failed_calls
    assert (base / "run.json").is_file()
    assert not (base / "failure.json").exists()
    assert succeeded.diagnostics == []
    assert not list(base.parent.glob(".technical.*.staging"))
    assert not list(base.parent.glob(".technical.*.previous"))


def test_public_api_rejects_incompatible_terminal_job_without_overwrite(
    tmp_path: Path,
):
    config = AppConfig(
        root_dir=tmp_path,
        checkpoint_enabled=True,
        min_text_chars=1,
        research_concurrency=2,
    )
    config.ensure_runtime_dirs()
    paths = _sources(tmp_path)
    services = ResearchServices(
        documents=FakeDocuments(),
        retrieval=FakeRetrieval(),
        models=FakeTechnicalModels(),
    )
    request = TechnicalResearchRequest(
        instruction="두 논문을 기술적으로 비교해줘",
        sources=[str(path) for path in paths],
        job_id="immutable-terminal-job",
    )
    succeeded = run_technical_research(request, config, services=services)
    run_path = (
        tmp_path / "outputs" / "immutable-terminal-job" / "technical" / "run.json"
    )
    original = run_path.read_bytes()

    with pytest.raises(ValueError, match="다른 기술조사 요청"):
        run_technical_research(
            request.model_copy(update={"instruction": "변경된 관점으로 분석해줘"}),
            config,
            services=services,
        )

    assert succeeded.status == "succeeded"
    assert run_path.read_bytes() == original
    assert not (run_path.parent / "failure.json").exists()


def test_public_api_requires_force_when_terminal_source_content_changed(
    tmp_path: Path,
):
    config = AppConfig(
        root_dir=tmp_path,
        checkpoint_enabled=True,
        min_text_chars=1,
        research_concurrency=2,
    )
    config.ensure_runtime_dirs()
    paths = _sources(tmp_path)
    services = ResearchServices(
        documents=FakeDocuments(),
        retrieval=FakeRetrieval(),
        models=FakeTechnicalModels(),
    )
    request = TechnicalResearchRequest(
        instruction="두 논문을 기술적으로 비교해줘",
        sources=[str(path) for path in paths],
        job_id="changed-terminal-source",
    )
    first = run_technical_research(request, config, services=services)
    run_path = (
        tmp_path / "outputs" / "changed-terminal-source" / "technical" / "run.json"
    )
    original = run_path.read_bytes()
    paths[0].write_text("updated paper source", encoding="utf-8")

    with pytest.raises(ValueError, match="--force-reindex"):
        run_technical_research(request, config, services=services)
    assert run_path.read_bytes() == original

    refreshed = run_technical_research(
        request.model_copy(update={"force_reindex": True}),
        config,
        services=services,
    )
    assert first.status == "succeeded"
    assert refreshed.status == "succeeded"
    assert run_path.read_bytes() != original


def test_explicit_sources_take_precedence_and_hash_duplicates_are_removed(
    tmp_path: Path,
):
    first = tmp_path / "first.txt"
    duplicate = tmp_path / "duplicate.txt"
    ignored = tmp_path / "ignored.txt"
    first.write_text("same paper", encoding="utf-8")
    duplicate.write_text("same paper", encoding="utf-8")
    ignored.write_text("different paper", encoding="utf-8")
    config = _config(tmp_path)
    request = TechnicalResearchRequest(
        instruction=f"{ignored}를 분석해줘",
        sources=[str(first), str(duplicate)],
    )

    resolved = _resolve_sources(request, tmp_path, LocalDocumentService(config))

    assert resolved == [first.resolve()]
    assert ignored.resolve() not in resolved


def test_common_sources_are_explicit_and_hash_deduplicated(tmp_path: Path):
    first = tmp_path / "approved.txt"
    duplicate = tmp_path / "approved-copy.txt"
    mentioned_only = tmp_path / "mentioned.txt"
    first.write_text("approved context", encoding="utf-8")
    duplicate.write_text("approved context", encoding="utf-8")
    mentioned_only.write_text("not approved", encoding="utf-8")
    config = _config(tmp_path)
    request = TechnicalResearchRequest(
        instruction=f"{mentioned_only}를 배경으로 사용해줘",
        sources=[str(mentioned_only)],
        common_sources=[str(first), str(duplicate)],
    )

    resolved = _resolve_common_sources(request, tmp_path, LocalDocumentService(config))

    assert resolved == [first.resolve()]
    assert mentioned_only.resolve() not in resolved


def test_research_retrieves_eight_paper_and_four_approved_common_per_facet(
    tmp_path: Path,
):
    paper = tmp_path / "paper.txt"
    common = tmp_path / "common.txt"
    paper.write_text("paper content", encoding="utf-8")
    common.write_text("approved common context", encoding="utf-8")
    retrieval = RecordingRetrieval()
    workflow = TechnicalResearchWorkflow(
        _config(tmp_path),
        ResearchServices(
            documents=FakeDocuments(),
            retrieval=retrieval,
            models=FakeTechnicalModels(),
        ),
    )
    common_hashes = workflow._index_common_sources([common], force=False)
    request = TechnicalResearchRequest(
        instruction="기술적으로 분석해줘",
        sources=[str(paper)],
        common_sources=[str(common)],
    )

    dossier, evidence, _, _, _ = workflow._research_one(paper, request, common_hashes)

    assert dossier.paper.paper_id.startswith("paper-")
    assert {item.source_kind for item in evidence} == {"paper", "common"}
    assert all(limit == 8 for kind, limit, _ in retrieval.calls if kind == "paper")
    assert all(limit == 4 for kind, limit, _ in retrieval.calls if kind == "common")
    assert all(
        allowed == tuple(sorted(common_hashes))
        for kind, _, allowed in retrieval.calls
        if kind == "common"
    )


def test_quality_repair_drops_resolved_required_missing_topics(tmp_path: Path):
    class RepairingModels(FakeTechnicalModels):
        def __init__(self):
            super().__init__()
            self.audit_attempt = 0
            self.feedback: list[list[str]] = []

        def extract_dossier(self, **kwargs):
            self.feedback.append(list(kwargs.get("repair_feedback") or []))
            return super().extract_dossier(**kwargs)

        def audit_dossier(self, dossier, evidence):
            audit, usage = super().audit_dossier(dossier, evidence)
            topics = ["first missing headline", "second missing limitation"]
            missing = (
                [topics[self.audit_attempt]] if self.audit_attempt < len(topics) else []
            )
            self.audit_attempt += 1
            return audit.model_copy(update={"missing_critical_topics": missing}), usage

    paper = tmp_path / "paper.txt"
    paper.write_text("paper content", encoding="utf-8")
    models = RepairingModels()
    workflow = TechnicalResearchWorkflow(
        _config(tmp_path),
        ResearchServices(
            documents=FakeDocuments(), retrieval=FakeRetrieval(), models=models
        ),
    )
    request = TechnicalResearchRequest(
        instruction="기술적으로 분석해줘", sources=[str(paper)]
    )

    workflow._research_one(paper, request)

    assert len(models.feedback) == 3
    assert any("first missing headline" in item for item in models.feedback[1])
    assert not any("first missing headline" in item for item in models.feedback[2])
    assert any("second missing limitation" in item for item in models.feedback[2])


def test_sparse_repair_preserves_prior_analysis_and_adds_repaired_claim(
    tmp_path: Path,
):
    class SparseRepairModels(FakeTechnicalModels):
        def __init__(self):
            super().__init__()
            self.extract_attempt = 0
            self.audit_attempt = 0

        def extract_dossier(self, **kwargs):
            self.extract_attempt += 1
            if self.extract_attempt == 1:
                return super().extract_dossier(**kwargs)
            evidence_id = kwargs["evidence"][0].evidence_id
            repaired = TechnicalClaim(
                claim_id="repaired-frozen-allocation",
                text="Prefill 이후 allocation은 고정된다.",
                claim_type="author_claim",
                evidence_ids=[evidence_id],
                confidence=0.9,
                critical=True,
            )
            return DossierExtraction(
                analysis=PaperAnalysis(
                    technical_overview=TechnicalOverview(),
                    scope=ScopeAnalysis(),
                    limitations=LimitationsAnalysis(),
                ),
                claims=[repaired],
                critical_inventory=[
                    CriticalClaimItem(
                        inventory_id="inventory-frozen-allocation",
                        category="limitation",
                        summary="Prefill 이후 allocation 고정",
                        disposition="extracted",
                        claim_ids=[repaired.claim_id],
                        evidence_ids=[evidence_id],
                    )
                ],
                experiment_observations=[],
                unverified_items=[
                    UnverifiedItem(
                        item_id="physical-e2e-unverified",
                        topic="physical end-to-end deployment",
                        reason="not found in supplied evidence",
                        searched_queries=["physical end-to-end deployment"],
                        attempts=2,
                    )
                ],
            ), TokenUsage(total_tokens=2)

        def audit_dossier(self, dossier, evidence):
            audit, usage = super().audit_dossier(dossier, evidence)
            self.audit_attempt += 1
            if self.audit_attempt == 1:
                audit = audit.model_copy(
                    update={"missing_critical_topics": ["frozen allocation limitation"]}
                )
            return audit, usage

    paper = tmp_path / "paper.txt"
    paper.write_text("paper content", encoding="utf-8")
    models = SparseRepairModels()
    workflow = TechnicalResearchWorkflow(
        _config(tmp_path),
        ResearchServices(
            documents=FakeDocuments(), retrieval=FakeRetrieval(), models=models
        ),
    )
    request = TechnicalResearchRequest(
        instruction="기술적으로 분석해줘", sources=[str(paper)]
    )

    dossier, _, _, _, _ = workflow._research_one(paper, request)

    assert models.extract_attempt == 2
    assert dossier.analysis.technical_overview.experimental_results
    assert dossier.analysis.limitations.author_stated
    assert dossier.experiment_observations
    assert any(
        claim.claim_id.endswith("::repaired-frozen-allocation")
        for claim in dossier.claims
    )
    assert any(
        item.inventory_id.endswith("::inventory-frozen-allocation")
        for item in dossier.critical_inventory
    )
    assert any(
        item.item_id.endswith("::physical-e2e-unverified")
        for item in dossier.unverified_items
    )


def test_successful_paper_research_cache_skips_repeat_model_and_retrieval(
    tmp_path: Path,
):
    class CountingModels(FakeTechnicalModels):
        def __init__(self):
            super().__init__()
            self.plan_calls = 0

        def plan_queries(self, paper, instruction):
            self.plan_calls += 1
            return super().plan_queries(paper, instruction)

    paper = tmp_path / "paper.txt"
    paper.write_text("paper content", encoding="utf-8")
    models = CountingModels()
    retrieval = RecordingRetrieval()
    workflow = TechnicalResearchWorkflow(
        _config(tmp_path),
        ResearchServices(documents=FakeDocuments(), retrieval=retrieval, models=models),
    )
    request = TechnicalResearchRequest(
        instruction="기술적으로 분석해줘", sources=[str(paper)]
    )

    first = workflow._research_one(paper, request)
    retrieval_calls = len(retrieval.calls)
    second = workflow._research_one(paper, request)

    assert models.plan_calls == 1
    assert len(retrieval.calls) == retrieval_calls
    assert second[0] == first[0]
    assert second[1] == first[1]
    assert second[3] == TokenUsage()


def test_paper_cache_fingerprint_includes_vision_runtime_and_versions(tmp_path: Path):
    paper = tmp_path / "paper.txt"
    paper.write_text("paper content", encoding="utf-8")
    config = _config(tmp_path)
    retrieval = FakeRetrieval()
    parsed = FakeDocuments().parse(
        paper,
        document_id="paper-a",
        source_kind="paper",
    )
    request = TechnicalResearchRequest(
        instruction="기술적으로 분석해줘", sources=[str(paper)]
    )
    first_visuals = SimpleNamespace(
        config=SimpleNamespace(
            model="gpt-5.6-terra",
            prompt_version="vision-config-v1",
            max_total_pixels=32_000_000,
        )
    )
    second_visuals = SimpleNamespace(
        config=SimpleNamespace(
            model="gpt-5.6-terra",
            prompt_version="vision-config-v1",
            max_total_pixels=16_000_000,
        )
    )

    first = _paper_research_cache_path(
        config, retrieval, first_visuals, parsed, request, {}
    )
    second = _paper_research_cache_path(
        config, retrieval, second_visuals, parsed, request, {}
    )
    disabled = _paper_research_cache_path(
        config, retrieval, None, parsed, request, {}
    )

    assert first != second
    assert first != disabled


def test_concurrent_failures_use_deterministic_precedence_and_keep_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    paths = _sources(tmp_path)
    third = tmp_path / "paper-c.txt"
    third.write_text("third paper", encoding="utf-8")
    paths.append(third)
    workflow = TechnicalResearchWorkflow(
        _config(tmp_path),
        ResearchServices(
            documents=FakeDocuments(),
            retrieval=FakeRetrieval(),
            models=FakeTechnicalModels(),
        ),
    )
    request = TechnicalResearchRequest(
        instruction="세 논문을 비교해줘",
        sources=[str(path) for path in paths],
        job_id="partial-failure-job",
    )
    success = workflow._research_one(paths[0], request)
    quality_usage = TokenUsage(input_tokens=5, output_tokens=2, total_tokens=7)
    provider_usage = TokenUsage(input_tokens=9, output_tokens=2, total_tokens=11)

    def research_one(path, *_args, **_kwargs):
        if path.name == "paper-a.txt":
            return success
        if path.name == "paper-b.txt":
            raise _PaperResearchFailure(
                "quality failed",
                status="failed_quality",
                token_usage=quality_usage,
                retrieval_traces=[{"queries": ["quality trace"]}],
            )
        raise _PaperResearchFailure(
            "provider failed",
            status="provider_error",
            token_usage=provider_usage,
            retrieval_traces=[{"queries": ["provider trace"]}],
        )

    monkeypatch.setattr(workflow, "_research_one", research_one)
    result = workflow.research_documents(
        {
            "request": request.model_dump(mode="json"),
            "job_id": request.job_id,
            "source_paths": [str(path) for path in paths],
            "common_source_paths": [],
        }
    )

    assert result["failure_status"] == "provider_error"
    assert result["token_usage"]["total_tokens"] == (
        success[3].total_tokens + quality_usage.total_tokens + provider_usage.total_tokens
    )
    assert {tuple(item["queries"]) for item in result["retrieval_traces"]} == {
        ("quality trace",),
        ("provider trace",),
    }
    assert result["errors"] == sorted(result["errors"])


def test_currently_valid_failed_draft_is_recovered_without_provider_calls(
    tmp_path: Path,
):
    class CountingModels(FakeTechnicalModels):
        def __init__(self):
            super().__init__()
            self.plan_calls = 0
            self.extract_calls = 0
            self.audit_calls = 0

        def plan_queries(self, paper, instruction):
            self.plan_calls += 1
            return super().plan_queries(paper, instruction)

        def extract_dossier(self, **kwargs):
            self.extract_calls += 1
            return super().extract_dossier(**kwargs)

        def audit_dossier(self, dossier, evidence):
            self.audit_calls += 1
            return super().audit_dossier(dossier, evidence)

    paper = tmp_path / "paper.txt"
    paper.write_text("paper content", encoding="utf-8")
    config = _config(tmp_path)
    models = CountingModels()
    retrieval = RecordingRetrieval()
    workflow = TechnicalResearchWorkflow(
        config,
        ResearchServices(documents=FakeDocuments(), retrieval=retrieval, models=models),
    )
    request = TechnicalResearchRequest(
        instruction="기술적으로 분석해줘", sources=[str(paper)]
    )
    dossier, evidence, audit, _, traces = workflow._research_one(paper, request)
    for cache_path in (config.work_dir / "technical-paper-cache").glob("*.json"):
        cache_path.unlink()

    canonical_id = evidence[0].evidence_id
    short_id = f"{evidence[0].locator.element_id}:{canonical_id.rsplit(':', 1)[-1]}"
    stale_claim = dossier.claims[0].model_copy(update={"evidence_ids": [short_id]})
    stale_dossier = dossier.model_copy(
        update={"claims": [stale_claim, *dossier.claims[1:]]}
    )
    stored_usage = TokenUsage(input_tokens=40, output_tokens=2, total_tokens=42)
    stored_traces = [
        *traces,
        {"queries": ["cached query"], "selected_chunk_ids": []},
    ]
    _write_failed_paper_draft(
        config=config,
        job_id="prior-failed-job",
        dossier=stale_dossier,
        evidence=evidence,
        audit=audit,
        errors=["old deterministic reference error"],
        traces=stored_traces,
        token_usage=stored_usage,
        attempts=3,
    )
    models.plan_calls = models.extract_calls = models.audit_calls = 0
    retrieval.calls.clear()

    recovered = workflow._research_one(paper, request)

    assert models.plan_calls == 0
    assert models.extract_calls == 0
    assert models.audit_calls == 0
    assert retrieval.calls == []
    assert recovered[3] == stored_usage
    assert recovered[4] == stored_traces
    assert recovered[0].claims[0].evidence_ids == [canonical_id]
    assert list((config.work_dir / "technical-paper-cache").glob("*.json"))


@pytest.mark.parametrize(
    "invalid_field",
    [
        "schema",
        "cache_version",
        "draft_revision",
        "source_hash",
        "source_path",
        "unsupported_audit",
    ],
)
def test_mismatched_or_unsupported_failed_draft_is_never_recovered(
    tmp_path: Path,
    invalid_field: str,
):
    class CountingModels(FakeTechnicalModels):
        def __init__(self):
            super().__init__()
            self.extract_calls = 0

        def extract_dossier(self, **kwargs):
            self.extract_calls += 1
            return super().extract_dossier(**kwargs)

    paper = tmp_path / "paper.txt"
    paper.write_text("paper content", encoding="utf-8")
    config = _config(tmp_path)
    models = CountingModels()
    workflow = TechnicalResearchWorkflow(
        config,
        ResearchServices(
            documents=FakeDocuments(), retrieval=FakeRetrieval(), models=models
        ),
    )
    request = TechnicalResearchRequest(
        instruction="기술적으로 분석해줘", sources=[str(paper)]
    )
    dossier, evidence, audit, _, traces = workflow._research_one(paper, request)
    for cache_path in (config.work_dir / "technical-paper-cache").glob("*.json"):
        cache_path.unlink()
    draft_path = _write_failed_paper_draft(
        config=config,
        job_id="invalid-failed-job",
        dossier=dossier,
        evidence=evidence,
        audit=audit,
        errors=["old error"],
        traces=traces,
        token_usage=TokenUsage(total_tokens=99),
        attempts=3,
    )
    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    if invalid_field == "schema":
        payload["schema_version"] = "0.9.0"
    elif invalid_field == "cache_version":
        payload["cache_version"] = "stale-pipeline-revision"
    elif invalid_field == "draft_revision":
        payload["draft_revision"] = "stale-draft-revision"
    elif invalid_field == "source_hash":
        payload["dossier"]["paper"]["source_hash"] = "0" * 64
    elif invalid_field == "source_path":
        payload["dossier"]["paper"]["source_path"] = str(tmp_path / "another-paper.txt")
    else:
        payload["audit"]["audits"][0]["verdict"] = "unsupported"
    draft_path.write_text(json.dumps(payload), encoding="utf-8")
    models.extract_calls = 0

    workflow._research_one(paper, request)

    assert models.extract_calls == 1


def test_final_paper_quality_failure_preserves_redacted_diagnostic_draft(
    tmp_path: Path,
):
    class TracedRetrieval(FakeRetrieval):
        def retrieve_with_trace(
            self, source_kind, document_id, queries, limit, *, filters=None
        ):
            chunks = self.retrieve(
                source_kind, document_id, queries, limit, filters=filters
            )
            return SimpleNamespace(
                hits=chunks,
                trace={
                    "queries": list(queries),
                    "selected_chunk_ids": [item.chunk_id for item in chunks],
                    "api_key": "sk-trace-secret-1234567890",
                },
            )

    class AlwaysInvalidModels(FakeTechnicalModels):
        def audit_dossier(self, dossier, evidence):
            audit, usage = super().audit_dossier(dossier, evidence)
            return audit.model_copy(
                update={
                    "numeric_consistency_errors": [
                        "forced failure sk-audit-secret-1234567890"
                    ]
                }
            ), usage

    paper = tmp_path / "paper.txt"
    full_source_sentinel = "RAW_FULL_PDF_TEXT_MUST_NOT_BE_COPIED"
    paper.write_text(full_source_sentinel, encoding="utf-8")
    config = _config(tmp_path)
    workflow = TechnicalResearchWorkflow(
        config,
        ResearchServices(
            documents=FakeDocuments(),
            retrieval=TracedRetrieval(),
            models=AlwaysInvalidModels(),
        ),
    )
    request = TechnicalResearchRequest(
        instruction="기술적으로 분석해줘",
        sources=[str(paper)],
        job_id="failed-draft-job",
    )

    with pytest.raises(ValueError) as caught:
        workflow._research_one(paper, request)

    draft_path = (
        config.work_dir
        / "technical-failed-drafts"
        / "failed-draft-job"
        / f"paper-{hashlib.sha256(paper.read_bytes()).hexdigest()[:8]}.json"
    )
    assert str(draft_path.resolve()) in str(caught.value)
    assert draft_path.is_file()
    assert not draft_path.with_suffix(".json.tmp").exists()
    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "failed_paper_technical_draft"
    assert payload["draft_revision"]
    assert payload["attempts"] == 3
    assert payload["dossier"]["paper"]["paper_id"].startswith("paper-")
    assert payload["evidence"]
    assert payload["audit"]["numeric_consistency_errors"]
    assert payload["errors"]
    assert payload["retrieval_traces"]
    assert payload["token_usage"]["total_tokens"] == 10
    serialized = draft_path.read_text(encoding="utf-8")
    assert full_source_sentinel not in serialized
    assert "sk-trace-secret" not in serialized
    assert "sk-audit-secret" not in serialized
    assert serialized.count("[REDACTED]") >= 2


def test_research_graph_writes_success_artifacts(tmp_path: Path):
    envelope = _run_graph(tmp_path)

    assert envelope.status == "succeeded"
    assert len(envelope.dossiers) == 2
    assert envelope.comparison is not None
    assert envelope.quality.evidence_resolution_rate == 1.0
    assert envelope.quality.locator_resolution_rate == 1.0
    assert envelope.quality.critical_inventory_coverage == 1.0
    assert envelope.run.peak_rss_bytes > 0
    assert envelope.run.completed_without_oom is True
    assert envelope.run.contract_schema_version == "1.0.0"
    assert envelope.run.evidence_id_version == "2.0.0"
    assert envelope.run.prompt_version == "1.0.0"
    assert envelope.run.index_version == "1.2.0"
    assert envelope.run.vision is not None
    assert envelope.run.vision.enabled is False
    assert envelope.run.vision.model == "gpt-5.6-terra"
    assert envelope.run.vision.max_visuals_per_paper == 8
    assert envelope.run.vision.max_requests_per_paper == 12
    assert envelope.run.vision.max_pixels_per_paper == 32_000_000
    assert envelope.run.vision.max_concurrency == 2
    assert {artifact.type for artifact in envelope.artifacts} == {
        "dossier",
        "comparison",
        "evidence_registry",
        "retrieval_trace",
    }
    base = tmp_path / "outputs" / "technical-job" / "technical"
    assert (base / "run.json").exists()
    assert (base / "comparison.json").exists()
    assert (base / "evidence_registry.json").exists()
    assert (base / "retrieval_traces.jsonl").exists()
    assert len(list((base / "dossiers").glob("*.json"))) == 2
    assert not (base / "failure.json").exists()


def test_research_graph_writes_failure_artifact_for_invalid_comparison(tmp_path: Path):
    envelope = _run_graph(tmp_path, invalid_comparison=True)

    assert envelope.status == "failed_quality"
    assert envelope.comparison is None
    assert any(
        "incompatible experiment signatures" in diagnostic.message
        for diagnostic in envelope.diagnostics
    )
    base = tmp_path / "outputs" / "technical-job" / "technical"
    assert (base / "failure.json").exists()
    assert not (base / "run.json").exists()
    assert (base / "evidence_registry.json").exists()
    assert len(list((base / "dossiers").glob("*.json"))) == 2


def test_validate_technical_research_checks_published_artifact_hashes(tmp_path: Path):
    _run_graph(tmp_path)
    run_path = tmp_path / "outputs" / "technical-job" / "technical" / "run.json"

    assert validate_technical_research(run_path).valid

    comparison_path = run_path.parent / "comparison.json"
    comparison_path.write_text("{}\n", encoding="utf-8")
    report = validate_technical_research(run_path)

    assert not report.valid
    assert any("artifact hash mismatch" in error for error in report.errors)


def test_validate_technical_research_resolves_locator_against_source(tmp_path: Path):
    _run_graph(tmp_path)
    base = tmp_path / "outputs" / "technical-job" / "technical"
    run_path = base / "run.json"
    run_payload = json.loads(run_path.read_text(encoding="utf-8"))
    registry_path = base / "evidence_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry[0]["locator"]["physical_page"] = 999
    raw = (
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    registry_path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    registry_ref = next(
        item for item in run_payload["artifacts"] if item["type"] == "evidence_registry"
    )
    registry_ref["sha256"] = digest
    registry_ref["artifact_id"] = f"evidence_registry-{digest[:16]}"
    run_path.write_text(
        json.dumps(run_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = validate_technical_research(run_path)

    assert not report.valid
    assert any("physical page is outside" in error for error in report.errors)


def test_validate_technical_research_resolves_locator_against_chunk_manifest(
    tmp_path: Path,
):
    _run_graph(tmp_path)
    base = tmp_path / "outputs" / "technical-job" / "technical"
    run_path = base / "run.json"
    run_payload = json.loads(run_path.read_text(encoding="utf-8"))
    registry_path = base / "evidence_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry[0]["locator"]["source_chunk_id"] = "missing-source-chunk"
    raw = (
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    registry_path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    registry_ref = next(
        item for item in run_payload["artifacts"] if item["type"] == "evidence_registry"
    )
    registry_ref["sha256"] = digest
    registry_ref["artifact_id"] = f"evidence_registry-{digest[:16]}"
    run_path.write_text(
        json.dumps(run_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = validate_technical_research(run_path)

    assert not report.valid
    assert any(
        "source_chunk_id cannot be resolved" in error for error in report.errors
    )


def test_job_generation_publish_replaces_success_with_coherent_failure(tmp_path: Path):
    succeeded = _run_graph(tmp_path)
    assert succeeded.status == "succeeded"
    base = tmp_path / "outputs" / "technical-job" / "technical"
    assert (base / "run.json").exists()

    failed = _run_graph(tmp_path, invalid_comparison=True)

    assert failed.status == "failed_quality"
    assert (base / "failure.json").exists()
    assert not (base / "run.json").exists()
    assert not (base / "comparison.json").exists()
    assert not list(base.parent.glob(".technical.*.staging"))
    assert not list(base.parent.glob(".technical.*.previous"))
    for artifact in failed.artifacts:
        artifact_path = Path(artifact.path)
        assert artifact_path.is_relative_to(base)
        assert artifact_path.is_file()
        assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == artifact.sha256


def test_public_runtime_failure_atomically_replaces_stale_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    succeeded = _run_graph(tmp_path)
    assert succeeded.status == "succeeded"
    base = tmp_path / "outputs" / "technical-job" / "technical"

    def fail_to_build(*_args, **_kwargs):
        raise RuntimeError("forced graph build failure")

    monkeypatch.setattr(
        "paper_review_agent.research_api._build_graph", fail_to_build
    )
    paths = _sources(tmp_path)
    request = TechnicalResearchRequest(
        instruction="두 논문을 기술적으로 비교해줘",
        sources=[str(path) for path in paths],
        job_id="technical-job",
    )
    failed = run_technical_research(
        request,
        _config(tmp_path),
        services=ResearchServices(
            documents=FakeDocuments(),
            retrieval=FakeRetrieval(),
            models=FakeTechnicalModels(),
        ),
    )

    assert failed.status == "provider_error"
    assert (base / "failure.json").is_file()
    assert not (base / "run.json").exists()
    assert not (base / "dossiers").exists()
    assert not (base / "comparison.json").exists()
    assert not list(base.parent.glob(".technical.*.staging"))
    assert not list(base.parent.glob(".technical.*.previous"))


def test_vision_crop_is_published_as_hash_resolvable_artifact(tmp_path: Path):
    raw = b"\x89PNG\r\n\x1a\nminimal-test-crop"
    crop_sha = hashlib.sha256(raw).hexdigest()
    document_sha = "a" * 64
    source = tmp_path / "work" / "vision-cache" / document_sha / "crops" / "crop.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(raw)
    evidence = TechnicalEvidence(
        evidence_id=(
            f"paper:paper-a@{document_sha[:12]}:p0001:elem-vision:span-00000-00004"
        ),
        source_kind="paper",
        document_id="paper-a",
        content_kind="figure",
        extraction_method="vision",
        snippet="data",
        content_hash=hashlib.sha256(b"data").hexdigest(),
        locator=EvidenceLocator(
            document_sha256=document_sha,
            physical_page=1,
            element_id="elem-vision",
            crop_sha256=crop_sha,
            visual_artifact_id="temporary-element-id",
        ),
    )
    staging = tmp_path / "outputs" / "job" / ".technical.stage"
    staging.mkdir(parents=True)
    published = tmp_path / "outputs" / "job" / "technical"

    updated, artifacts, errors = _stage_visual_artifacts(
        [evidence],
        staging=staging,
        published_base=published,
        work_dir=tmp_path / "work",
        previous_base=published,
    )

    assert errors == []
    assert len(artifacts) == 1
    assert artifacts[0].type == "visual_crop"
    assert artifacts[0].sha256 == crop_sha
    assert updated[0].locator.visual_artifact_id == artifacts[0].artifact_id
    staged_crop = next((staging / "visuals").iterdir())
    assert staged_crop.read_bytes() == raw
