"""LangGraph orchestration for evidence-first multi-paper technical research."""

from __future__ import annotations

import hashlib
import json
import re
import resource
import shutil
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import BoundedSemaphore
from typing import Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from paper_review_agent.config import AppConfig
from paper_review_agent.artifacts import atomic_write
from paper_review_agent.bge_retrieval import RetrievalFilters
from paper_review_agent.documents import DocumentService
from paper_review_agent.evidence_context import expand_caption_linked_context
from paper_review_agent.evidence_ids import (
    EVIDENCE_ID_VERSION,
    evidence_element_id,
    format_table_cell_suffix,
    table_aggregate_suffix,
)
from paper_review_agent.exceptions import DependencyError, IngestionError, ProviderError
from paper_review_agent.source_paths import extract_source_paths
from paper_review_agent.schemas import (
    FACET_FIELDS,
    FACETS,
    Chunk,
    ParsedDocument,
    TokenUsage,
    utc_now,
)
from paper_review_agent.technical_models import (
    TechnicalModelGateway,
    assemble_dossier_facets,
    finalize_dossier_extraction,
    merge_dossier_extractions,
)
from paper_review_agent.technical_schemas import (
    TECHNICAL_SCHEMA_VERSION,
    DossierExtraction,
    EvidenceLocator,
    TechnicalArtifactRef,
    TechnicalAudit,
    TechnicalComparison,
    TechnicalDiagnostic,
    TechnicalDossier,
    TechnicalEvidence,
    TechnicalFacetExtraction,
    TechnicalQuality,
    TechnicalResearchEnvelope,
    TechnicalResearchRequest,
    TechnicalRunMetadata,
    TechnicalVisionRunMetadata,
    ResearchQueryPlan,
    TextSpan,
)
from paper_review_agent.technical_validation import (
    analysis_audit_item_ids,
    evidence_resolution_rates,
    validate_comparison_contract,
    validate_dossier_contract,
)


class TechnicalRetrievalService(Protocol):
    def index_chunks(self, chunks: list[Chunk], *, force: bool = False) -> bool: ...

    def retrieve(
        self,
        source_kind: str,
        document_id: str | None,
        queries: list[str],
        limit: int,
        *,
        filters: RetrievalFilters | None = None,
    ) -> list[Chunk]: ...


class VisualEnrichmentService(Protocol):
    def enrich(
        self,
        *,
        source_path: Path,
        parsed: ParsedDocument,
        queries: list[str],
        retrieved_element_ids: set[str] | None = None,
    ) -> list[Chunk]: ...


class ResearchState(TypedDict, total=False):
    request: dict
    job_id: str
    started_at: str
    source_paths: list[str]
    common_source_paths: list[str]
    common_hashes: dict[str, str]
    paper_work: list[dict]
    dossiers: list[dict]
    evidence: list[dict]
    audits: list[dict]
    comparison: dict
    errors: list[str]
    warnings: list[str]
    failure_status: str
    token_usage: dict
    retrieval_traces: list[dict]
    final_envelope: dict


@dataclass(slots=True)
class ResearchServices:
    documents: DocumentService
    retrieval: TechnicalRetrievalService
    models: TechnicalModelGateway
    visuals: VisualEnrichmentService | None = None


class _PaperResearchFailure(ValueError):
    """Paper-scoped failure carrying bounded diagnostics to the graph boundary."""

    def __init__(
        self,
        message: str,
        *,
        status: str,
        token_usage: TokenUsage | None = None,
        retrieval_traces: list[dict] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.token_usage = token_usage or TokenUsage()
        self.retrieval_traces = list(retrieval_traces or [])


_FAILURE_STATUS_PRECEDENCE = {
    "failed_quality": 0,
    "failed_ingestion": 1,
    "provider_error": 2,
}


class TechnicalResearchWorkflow:
    def __init__(self, config: AppConfig, services: ResearchServices):
        self.config = config
        self.services = services
        # Paper stages may themselves run concurrently.  A workflow-wide gate
        # keeps the nested facet calls within the provider-safe global limit.
        self._facet_slots = BoundedSemaphore(3)

    def resolve_sources(self, state: ResearchState) -> dict:
        request = TechnicalResearchRequest.model_validate(state["request"])
        try:
            sources = _resolve_sources(
                request, self.config.root_dir, self.services.documents
            )
            common_sources = _resolve_common_sources(
                request, self.config.root_dir, self.services.documents
            )
            paper_hashes = {_sha256_file(path) for path in sources}
            duplicate_common = [
                path for path in common_sources if _sha256_file(path) in paper_hashes
            ]
            common_sources = [
                path
                for path in common_sources
                if _sha256_file(path) not in paper_hashes
            ]
            warnings = (
                [
                    "paper 입력과 동일한 common source를 배경 코퍼스에서 제외했습니다: "
                    + ", ".join(str(path) for path in duplicate_common)
                ]
                if duplicate_common
                else []
            )
            self._event(
                state,
                "resolve_sources",
                "ok",
                documents=len(sources),
                common_documents=len(common_sources),
            )
            return {
                "source_paths": [str(path) for path in sources],
                "common_source_paths": [str(path) for path in common_sources],
                "warnings": warnings,
            }
        except (FileNotFoundError, ValueError, IngestionError) as exc:
            self._event(state, "resolve_sources", "failed", error=type(exc).__name__)
            return {
                "failure_status": "failed_ingestion",
                "errors": [str(exc)],
            }

    def index_common_sources(self, state: ResearchState) -> dict:
        """Prepare the explicitly approved background corpus once per research run."""

        request = TechnicalResearchRequest.model_validate(state["request"])
        try:
            common_hashes = self._index_common_sources(
                [Path(raw) for raw in state.get("common_source_paths", [])],
                force=request.force_reindex,
            )
            self._event(
                state,
                "index_common_sources",
                "ok",
                common_documents=len(common_hashes),
            )
            return {"common_hashes": common_hashes}
        except Exception as exc:  # noqa: BLE001 - graph failure boundary
            status = _failure_status_for_exception(exc)
            self._event(
                state,
                "index_common_sources",
                "failed",
                error=type(exc).__name__,
                failure_status=status,
            )
            return {
                "failure_status": status,
                "errors": [f"<common-corpus>: {type(exc).__name__}: {exc}"],
                "paper_work": [],
            }

    def parse_documents(self, state: ResearchState) -> dict:
        """Parse papers and resolve valid paper-level caches before expensive work."""

        request = TechnicalResearchRequest.model_validate(state["request"])
        common_hashes = dict(state.get("common_hashes", {}))

        def parse_one(work: dict) -> dict:
            path = Path(work["source_path"])
            parsed = self.services.documents.parse(
                path,
                document_id=paper_id_for_path(path),
                source_kind="paper",
                arxiv_id=(
                    path.stem
                    if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", path.stem)
                    else None
                ),
                enforce_quality=True,
            )
            cache_path = _paper_research_cache_path(
                self.config,
                self.services.retrieval,
                self.services.visuals,
                parsed,
                request,
                common_hashes,
            )
            base = {
                **work,
                "paper_id": parsed.metadata.paper_id,
                "parsed_document": parsed.model_dump(mode="json"),
                "cache_path": str(cache_path),
                "token_usage": TokenUsage().model_dump(),
                "retrieval_traces": [],
            }
            if not request.force_reindex:
                cached = _load_paper_research_cache(cache_path, parsed)
                if cached is not None:
                    dossier, evidence, audit, traces = cached
                    return _completed_paper_work(
                        base,
                        dossier=dossier,
                        evidence=evidence,
                        audit=audit,
                        traces=traces,
                        usage=TokenUsage(),
                        completion="cache_hit",
                    )
                recovered = _recover_failed_paper_draft(
                    config=self.config,
                    parsed=parsed,
                    common_hashes=common_hashes,
                    models=self.services.models,
                )
                if recovered is not None:
                    dossier, evidence, audit, recovered_usage, traces = recovered
                    _save_paper_research_cache(
                        cache_path, dossier, evidence, audit, traces
                    )
                    return _completed_paper_work(
                        base,
                        dossier=dossier,
                        evidence=evidence,
                        audit=audit,
                        traces=traces,
                        usage=recovered_usage,
                        completion="failed_draft_recovered",
                    )
            return {**base, "stage": "inventory_pending"}

        initial = [
            {"source_path": raw, "stage": "parse_pending"}
            for raw in state.get("source_paths", [])
        ]
        return self._map_paper_stage(
            state,
            node="parse_documents",
            work_items=initial,
            eligible={"parse_pending"},
            operation=parse_one,
        )

    def seed_critical_inventory(self, state: ResearchState) -> dict:
        """Create deterministic headline-claim search seeds before indexing.

        The final ``CriticalClaimInventory`` remains a grounded extraction result.
        This stage is deliberately limited to a search seed so it cannot turn an
        unverified abstract/conclusion phrase into a dossier claim.
        """

        def seed_one(work: dict) -> dict:
            parsed = ParsedDocument.model_validate(work["parsed_document"])
            title = parsed.metadata.title or parsed.metadata.paper_id
            sections = list(
                dict.fromkeys(
                    chunk.section
                    for chunk in parsed.chunks
                    if chunk.section
                    and re.search(
                        r"abstract|contribut|conclusion|limitation|future\s+work",
                        chunk.section,
                        re.IGNORECASE,
                    )
                )
            )
            return {
                **work,
                "inventory_seed": {
                    "critical_inventory": [
                        f'"{title}" abstract contributions conclusion headline results'
                    ],
                    "source_sections": sections,
                },
                "stage": "index_pending",
            }

        return self._map_paper_stage(
            state,
            node="seed_critical_inventory",
            eligible={"inventory_pending"},
            operation=seed_one,
        )

    def index_paper_sources(self, state: ResearchState) -> dict:
        request = TechnicalResearchRequest.model_validate(state["request"])

        def index_one(work: dict) -> dict:
            parsed = ParsedDocument.model_validate(work["parsed_document"])
            self.services.retrieval.index_chunks(
                parsed.chunks, force=request.force_reindex
            )
            return {**work, "stage": "query_pending"}

        return self._map_paper_stage(
            state,
            node="index_paper_sources",
            eligible={"index_pending"},
            operation=index_one,
        )

    def plan_paper_queries(self, state: ResearchState) -> dict:
        request = TechnicalResearchRequest.model_validate(state["request"])

        def plan_one(work: dict) -> dict:
            parsed = ParsedDocument.model_validate(work["parsed_document"])
            plan, usage = self.services.models.plan_queries(
                parsed.metadata, request.instruction
            )
            payload = plan.model_dump(mode="python")
            for key, values in work.get("inventory_seed", {}).items():
                if key in payload and isinstance(values, list):
                    payload[key] = list(dict.fromkeys([*payload[key], *values]))
            plan = ResearchQueryPlan.model_validate(payload)
            return {
                **work,
                "query_plan": plan.model_dump(mode="json"),
                "token_usage": _merge_usage_dicts(
                    work.get("token_usage", {}), usage.model_dump()
                ),
                "stage": "retrieval_pending",
            }

        return self._map_paper_stage(
            state,
            node="plan_paper_queries",
            eligible={"query_pending"},
            operation=plan_one,
        )

    def retrieve_paper_evidence(self, state: ResearchState) -> dict:
        common_hashes = dict(state.get("common_hashes", {}))
        common_filters = RetrievalFilters(document_ids=tuple(sorted(common_hashes)))

        def retrieve_one(work: dict) -> dict:
            parsed = ParsedDocument.model_validate(work["parsed_document"])
            query_groups = ResearchQueryPlan.model_validate(
                work["query_plan"]
            ).model_dump(mode="python")
            selected: list[Chunk] = []
            traces = list(work.get("retrieval_traces", []))
            for queries in query_groups.values():
                selected.extend(
                    self._retrieve_with_trace(
                        "paper", parsed.metadata.paper_id, queries, 8, traces
                    )
                )
                if common_hashes:
                    selected.extend(
                        self._retrieve_with_trace(
                            "common",
                            None,
                            queries,
                            4,
                            traces,
                            filters=common_filters,
                        )
                    )
            selected = expand_caption_linked_context(selected, parsed.chunks)
            return {
                **work,
                "selected_chunks": [
                    item.model_dump(mode="json") for item in selected
                ],
                "retrieval_traces": traces,
                "stage": "vision_pending",
            }

        return self._map_paper_stage(
            state,
            node="retrieve_paper_evidence",
            eligible={"retrieval_pending"},
            operation=retrieve_one,
        )

    def enrich_paper_visuals(self, state: ResearchState) -> dict:
        common_hashes = dict(state.get("common_hashes", {}))

        def enrich_one(work: dict) -> dict:
            parsed = ParsedDocument.model_validate(work["parsed_document"])
            selected = [Chunk.model_validate(item) for item in work["selected_chunks"]]
            traces = list(work.get("retrieval_traces", []))
            plan = ResearchQueryPlan.model_validate(work["query_plan"])
            if self.services.visuals is not None:
                visual_chunks = self.services.visuals.enrich(
                    source_path=Path(work["source_path"]),
                    parsed=parsed,
                    queries=plan.visuals,
                    retrieved_element_ids={
                        item.element_id for item in selected if item.element_id
                    },
                )
                selected = _unique_chunks([*selected, *visual_chunks])
            _upsert_source_chunk_manifest(
                traces,
                selected,
                owner_document_id=parsed.metadata.paper_id,
            )
            source_hashes = {
                parsed.metadata.paper_id: parsed.metadata.source_hash,
                **common_hashes,
            }
            evidence = _unique_evidence(
                [
                    item
                    for chunk in selected
                    for item in _technical_evidences(
                        chunk, source_hashes[chunk.document_id]
                    )
                ]
            )
            return {
                **work,
                "selected_chunks": [item.model_dump(mode="json") for item in selected],
                "evidence": [item.model_dump(mode="json") for item in evidence],
                "retrieval_traces": traces,
                "repair_feedback": [],
                "required_missing_topics": [],
                "attempt": 0,
                "stage": "extraction_pending",
            }

        return self._map_paper_stage(
            state,
            node="enrich_paper_visuals",
            eligible={"vision_pending"},
            operation=enrich_one,
        )

    def extract_paper_dossiers(self, state: ResearchState) -> dict:
        request = TechnicalResearchRequest.model_validate(state["request"])

        def extract_one(work: dict) -> dict:
            parsed = ParsedDocument.model_validate(work["parsed_document"])
            evidence = [
                TechnicalEvidence.model_validate(item) for item in work["evidence"]
            ]
            previous = (
                DossierExtraction.model_validate(work["previous_extraction"])
                if work.get("previous_extraction")
                else None
            )
            feedback = list(work.get("repair_feedback", []))
            facet_method = getattr(
                self.services.models, "extract_dossier_facet", None
            )
            facet_payloads: dict[str, TechnicalFacetExtraction] = {
                name: TechnicalFacetExtraction.model_validate(payload)
                for name, payload in work.get("facet_extractions", {}).items()
            }
            if callable(facet_method):
                requested_facets = list(
                    work.get("repair_facets") or FACETS
                )
                requested_facets = [
                    facet for facet in FACETS if facet in requested_facets
                ]
                if not requested_facets:
                    raise ValueError("facet repair was requested without a failed facet")
                workers = max(
                    1,
                    min(
                        len(requested_facets),
                        int(getattr(self.config, "research_concurrency", 3)),
                        3,
                    ),
                )
                results: dict[str, TechnicalFacetExtraction] = {}
                usages: dict[str, TokenUsage] = {}

                def extract_facet(facet: str):
                    prior_facet = facet_payloads.get(facet)
                    facet_feedback = _facet_repair_feedback(
                        facet,
                        feedback,
                        prior_facet,
                        paper_id=parsed.metadata.paper_id,
                    )
                    with self._facet_slots:
                        return facet_method(
                            facet=facet,
                            paper=parsed.metadata,
                            evidence=evidence,
                            instruction=request.instruction,
                            output_language=request.output_language,
                            repair_feedback=facet_feedback,
                        )

                with ThreadPoolExecutor(
                    max_workers=workers,
                    thread_name_prefix="technical-facet",
                ) as pool:
                    futures = {
                        pool.submit(extract_facet, facet): facet
                        for facet in requested_facets
                    }
                    for future in as_completed(futures):
                        facet = futures[future]
                        result, facet_usage = future.result()
                        result = TechnicalFacetExtraction.model_validate(result)
                        if result.facet != facet:
                            raise ProviderError(
                                "기술조사 facet 응답 불일치: "
                                f"requested={facet}, returned={result.facet}"
                            )
                        results[facet] = result
                        usages[facet] = facet_usage
                facet_payloads.update(results)
                candidate = assemble_dossier_facets(
                    [facet_payloads[facet] for facet in FACETS]
                )
                usage = _sum_usage(
                    [usages[facet] for facet in FACETS if facet in usages]
                )
            else:
                # Backward compatibility for test/custom gateways that still
                # implement the original monolithic contract only.
                candidate, usage = self.services.models.extract_dossier(
                    paper=parsed.metadata,
                    evidence=evidence,
                    instruction=request.instruction,
                    output_language=request.output_language,
                    repair_feedback=_repair_feedback_with_previous_draft(
                        feedback, previous
                    ),
                )
            candidate = finalize_dossier_extraction(
                candidate,
                evidence=evidence,
                paper_id=parsed.metadata.paper_id,
            )
            # A facet repair already starts from the two previously accepted
            # facet payloads and replaces only the requested facet above.
            # Merging that complete assembly with ``previous`` a second time
            # retained every older wording whose text changed during repair,
            # causing analysis lists (and the audit prompt) to grow on each
            # round. The additive merger remains necessary for legacy/custom
            # monolithic gateways, which are allowed to return a sparse patch.
            if previous is not None and not callable(facet_method):
                candidate = merge_dossier_extractions(
                    previous,
                    candidate,
                    repair_feedback=feedback,
                )
            extraction = finalize_dossier_extraction(
                candidate,
                evidence=evidence,
                paper_id=parsed.metadata.paper_id,
            )
            dossier = _dossier_from_extraction(parsed, extraction)
            return {
                **work,
                "facet_extractions": {
                    facet: payload.model_dump(mode="json")
                    for facet, payload in facet_payloads.items()
                },
                "current_extraction": extraction.model_dump(mode="json"),
                "dossier": dossier.model_dump(mode="json"),
                "token_usage": _merge_usage_dicts(
                    work.get("token_usage", {}), usage.model_dump()
                ),
                "stage": "audit_pending",
            }

        return self._map_paper_stage(
            state,
            node="extract_paper_dossiers",
            eligible={"extraction_pending"},
            operation=extract_one,
        )

    def audit_paper_dossiers(self, state: ResearchState) -> dict:
        request = TechnicalResearchRequest.model_validate(state["request"])
        common_hashes = dict(state.get("common_hashes", {}))
        common_filters = RetrievalFilters(document_ids=tuple(sorted(common_hashes)))
        max_repairs = int(getattr(self.config, "max_quality_repairs", 2))

        def audit_one(work: dict) -> dict:
            parsed = ParsedDocument.model_validate(work["parsed_document"])
            dossier = TechnicalDossier.model_validate(work["dossier"])
            evidence = [
                TechnicalEvidence.model_validate(item) for item in work["evidence"]
            ]
            audit, usage = self.services.models.audit_dossier(dossier, evidence)
            token_usage = _merge_usage_dicts(
                work.get("token_usage", {}), usage.model_dump()
            )
            errors, _ = validate_dossier_contract(dossier, evidence, audit)
            traces = list(work.get("retrieval_traces", []))
            if not errors:
                _save_paper_research_cache(
                    Path(work["cache_path"]), dossier, evidence, audit, traces
                )
                return _completed_paper_work(
                    work,
                    dossier=dossier,
                    evidence=evidence,
                    audit=audit,
                    traces=traces,
                    usage=TokenUsage.model_validate(token_usage),
                    completion="extracted",
                )

            # The independent audit sees the complete current dossier.  Once
            # it no longer reports a topic, that topic has been repaired and
            # must not remain as stale feedback in later attempts.
            required_topics = list(dict.fromkeys(audit.missing_critical_topics))
            feedback = [
                *errors,
                *[f"REQUIRED_CRITICAL_TOPIC: {topic}" for topic in required_topics],
            ]
            repair_facets = _failed_dossier_facets(
                dossier=dossier,
                audit=audit,
                errors=feedback,
                facet_extractions=work.get("facet_extractions", {}),
            )
            attempt = int(work.get("attempt", 0))
            if attempt < max_repairs:
                selected = [
                    Chunk.model_validate(item) for item in work["selected_chunks"]
                ]
                if required_topics:
                    selected.extend(
                        self._retrieve_with_trace(
                            "paper",
                            parsed.metadata.paper_id,
                            required_topics,
                            8,
                            traces,
                        )
                    )
                    if common_hashes:
                        selected.extend(
                            self._retrieve_with_trace(
                                "common",
                                None,
                                required_topics,
                                4,
                                traces,
                                filters=common_filters,
                            )
                        )
                    selected = _unique_chunks(selected)
                    _upsert_source_chunk_manifest(
                        traces,
                        selected,
                        owner_document_id=parsed.metadata.paper_id,
                    )
                    source_hashes = {
                        parsed.metadata.paper_id: parsed.metadata.source_hash,
                        **common_hashes,
                    }
                    evidence = _unique_evidence(
                        [
                            item
                            for chunk in selected
                            for item in _technical_evidences(
                                chunk, source_hashes[chunk.document_id]
                            )
                        ]
                    )
                return {
                    **work,
                    "selected_chunks": [
                        item.model_dump(mode="json") for item in selected
                    ],
                    "evidence": [item.model_dump(mode="json") for item in evidence],
                    "audit": audit.model_dump(mode="json"),
                    "previous_extraction": work["current_extraction"],
                    "repair_feedback": feedback,
                    "repair_facets": repair_facets,
                    "required_missing_topics": required_topics,
                    "retrieval_traces": traces,
                    "token_usage": token_usage,
                    "attempt": attempt + 1,
                    "stage": "extraction_pending",
                }

            draft_path = _write_failed_paper_draft(
                config=self.config,
                job_id=state.get("job_id") or request.job_id or "unknown-job",
                dossier=dossier,
                evidence=evidence,
                audit=audit,
                errors=feedback,
                traces=traces,
                token_usage=TokenUsage.model_validate(token_usage),
                attempts=max_repairs + 1,
            )
            message = (
                "기술조사 품질 보강 2회 후에도 근거 계약을 통과하지 못했습니다: "
                + "; ".join(feedback)
                + f"; 실패 진단 초안: {draft_path}"
            )
            return _failed_paper_work(
                work,
                status="failed_quality",
                message=message,
                usage=TokenUsage.model_validate(token_usage),
                traces=traces,
            )

        return self._map_paper_stage(
            state,
            node="audit_paper_dossiers",
            eligible={"audit_pending"},
            operation=audit_one,
        )

    def route_after_paper_audit(self, state: ResearchState) -> str:
        if any(
            item.get("stage") == "extraction_pending"
            for item in state.get("paper_work", [])
        ):
            return "extract_paper_dossiers"
        return "collect_documents"

    def collect_documents(self, state: ResearchState) -> dict:
        if state.get("failure_status") and not state.get("paper_work"):
            return {
                "failure_status": state["failure_status"],
                "errors": state.get("errors", []),
                "token_usage": state.get("token_usage", TokenUsage().model_dump()),
                "retrieval_traces": state.get("retrieval_traces", []),
            }

        results: list[
            tuple[
                TechnicalDossier,
                list[TechnicalEvidence],
                TechnicalAudit,
                TokenUsage,
                list[dict],
            ]
        ] = []
        failures: list[tuple[str, str, str, TokenUsage, list[dict]]] = []
        for work in state.get("paper_work", []):
            usage = TokenUsage.model_validate(work.get("token_usage", {}))
            traces = list(work.get("retrieval_traces", []))
            if work.get("stage") == "completed":
                results.append(
                    (
                        TechnicalDossier.model_validate(work["dossier"]),
                        [
                            TechnicalEvidence.model_validate(item)
                            for item in work["evidence"]
                        ],
                        TechnicalAudit.model_validate(work["audit"]),
                        usage,
                        traces,
                    )
                )
            else:
                failures.append(
                    (
                        str(work.get("source_path", "<unknown-paper>")),
                        str(work.get("failure_status", "failed_quality")),
                        str(work.get("error", "paper research did not complete")),
                        usage,
                        traces,
                    )
                )

        if failures:
            results.sort(key=lambda item: item[0].paper.paper_id)
            failures.sort(key=lambda item: (item[0], item[2]))
            status = max(
                (item[1] for item in failures),
                key=lambda value: _FAILURE_STATUS_PRECEDENCE[value],
            )
            usage = _sum_usage(
                [item[3] for item in results] + [item[3] for item in failures]
            )
            traces = [value for item in results for value in item[4]] + [
                value for item in failures for value in item[4]
            ]
            traces = [
                item
                for item in traces
                if item.get("trace_kind") != "source_chunk_manifest"
            ]
            errors = [f"{source}: {message}" for source, _, message, _, _ in failures]
            self._event(
                state,
                "collect_documents",
                "failed",
                errors=len(errors),
                failure_status=status,
                partial_token_usage=usage.total_tokens,
                partial_retrieval_traces=len(traces),
            )
            return {
                "failure_status": status,
                "errors": errors,
                "token_usage": usage.model_dump(),
                "retrieval_traces": traces,
            }

        results.sort(key=lambda item: item[0].paper.paper_id)
        usage = _sum_usage([item[3] for item in results])
        evidence = _unique_evidence([value for item in results for value in item[1]])
        traces = [value for item in results for value in item[4]]
        self._event(
            state,
            "collect_documents",
            "ok",
            dossiers=len(results),
            evidence=len(evidence),
        )
        return {
            "dossiers": [item[0].model_dump(mode="json") for item in results],
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "audits": [item[2].model_dump(mode="json") for item in results],
            "token_usage": usage.model_dump(),
            "retrieval_traces": traces,
        }

    def research_documents(self, state: ResearchState) -> dict:
        """Legacy direct-call wrapper retained for service/test compatibility."""

        request = TechnicalResearchRequest.model_validate(state["request"])
        results: list[
            tuple[
                TechnicalDossier,
                list[TechnicalEvidence],
                TechnicalAudit,
                TokenUsage,
                list[dict],
            ]
        ] = []
        failures: list[tuple[str, str, str, TokenUsage, list[dict]]] = []
        workers = max(1, min(int(getattr(self.config, "research_concurrency", 3)), 3))
        try:
            common_hashes = self._index_common_sources(
                [Path(raw) for raw in state.get("common_source_paths", [])],
                force=request.force_reindex,
            )
            with ThreadPoolExecutor(
                max_workers=workers, thread_name_prefix="technical-paper"
            ) as pool:
                futures = {
                    pool.submit(
                        self._research_one,
                        Path(raw),
                        request,
                        common_hashes,
                        job_id=state["job_id"],
                    ): raw
                    for raw in state["source_paths"]
                }
                for future in as_completed(futures):
                    raw = futures[future]
                    try:
                        results.append(future.result())
                    except _PaperResearchFailure as exc:
                        failures.append(
                            (
                                raw,
                                exc.status,
                                str(exc),
                                exc.token_usage,
                                exc.retrieval_traces,
                            )
                        )
                    except IngestionError as exc:
                        failures.append(
                            (raw, "failed_ingestion", str(exc), TokenUsage(), [])
                        )
                    except ProviderError as exc:
                        failures.append(
                            (raw, "provider_error", str(exc), TokenUsage(), [])
                        )
                    except Exception as exc:  # noqa: BLE001 - graph boundary
                        failures.append(
                            (
                                raw,
                                "failed_quality",
                                f"{type(exc).__name__}: {exc}",
                                TokenUsage(),
                                [],
                            )
                        )
        except Exception as exc:  # noqa: BLE001
            failures.append(
                (
                    "<research-execution>",
                    _failure_status_for_exception(exc),
                    f"{type(exc).__name__}: {exc}",
                    TokenUsage(),
                    [],
                )
            )

        if failures:
            results.sort(key=lambda item: item[0].paper.paper_id)
            failures.sort(key=lambda item: (item[0], item[2]))
            status = max(
                (item[1] for item in failures),
                key=lambda value: _FAILURE_STATUS_PRECEDENCE[value],
            )
            usage = _sum_usage(
                [item[3] for item in results] + [item[3] for item in failures]
            )
            traces = [value for item in results for value in item[4]] + [
                value for item in failures for value in item[4]
            ]
            traces = [
                item
                for item in traces
                if item.get("trace_kind") != "source_chunk_manifest"
            ]
            errors = [f"{source}: {message}" for source, _, message, _, _ in failures]
            self._event(
                state,
                "research_documents",
                "failed",
                errors=len(errors),
                failure_status=status,
                partial_token_usage=usage.total_tokens,
                partial_retrieval_traces=len(traces),
            )
            return {
                "failure_status": status,
                "errors": errors,
                "token_usage": usage.model_dump(),
                "retrieval_traces": traces,
            }

        results.sort(key=lambda item: item[0].paper.paper_id)
        usage = _sum_usage([item[3] for item in results])
        evidence = _unique_evidence([value for item in results for value in item[1]])
        traces = [value for item in results for value in item[4]]
        self._event(
            state,
            "research_documents",
            "ok",
            dossiers=len(results),
            evidence=len(evidence),
        )
        return {
            "dossiers": [item[0].model_dump(mode="json") for item in results],
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "audits": [item[2].model_dump(mode="json") for item in results],
            "token_usage": usage.model_dump(),
            "retrieval_traces": traces,
        }

    def _map_paper_stage(
        self,
        state: ResearchState,
        *,
        node: str,
        eligible: set[str],
        operation,
        work_items: list[dict] | None = None,
    ) -> dict:
        """Run one real paper stage concurrently while retaining bounded failures."""

        items = [dict(item) for item in (work_items or state.get("paper_work", []))]
        active = [
            (index, item)
            for index, item in enumerate(items)
            if item.get("stage") in eligible
        ]
        workers = max(1, min(int(getattr(self.config, "research_concurrency", 3)), 3))
        failed = 0
        if active:
            with ThreadPoolExecutor(
                max_workers=workers, thread_name_prefix=f"technical-{node}"
            ) as pool:
                futures = {
                    pool.submit(operation, dict(item)): (index, item)
                    for index, item in active
                }
                for future in as_completed(futures):
                    index, prior = futures[future]
                    try:
                        items[index] = future.result()
                    except _PaperResearchFailure as exc:
                        failed += 1
                        items[index] = _failed_paper_work(
                            prior,
                            status=exc.status,
                            message=str(exc),
                            usage=exc.token_usage,
                            traces=exc.retrieval_traces,
                        )
                    except Exception as exc:  # noqa: BLE001 - stage boundary
                        failed += 1
                        current_usage = TokenUsage.model_validate(
                            prior.get("token_usage", {})
                        )
                        items[index] = _failed_paper_work(
                            prior,
                            status=_failure_status_for_exception(exc),
                            message=(
                                str(exc)
                                if isinstance(exc, (IngestionError, ProviderError))
                                else f"{type(exc).__name__}: {exc}"
                            ),
                            usage=current_usage,
                            traces=list(prior.get("retrieval_traces", [])),
                        )
        self._event(
            state,
            node,
            "failed" if failed else "ok",
            processed=len(active),
            failed=failed,
            skipped=len(items) - len(active),
        )
        return {"paper_work": items}

    def compare(self, state: ResearchState) -> dict:
        request = TechnicalResearchRequest.model_validate(state["request"])
        dossiers = [TechnicalDossier.model_validate(item) for item in state["dossiers"]]
        evidence = [
            TechnicalEvidence.model_validate(item) for item in state["evidence"]
        ]
        comparison_evidence = _comparison_evidence(dossiers, evidence)
        feedback: list[str] = []
        usage_items: list[TokenUsage] = []
        try:
            max_repairs = int(getattr(self.config, "max_quality_repairs", 2))
            for attempt in range(max_repairs + 1):
                comparison, usage = self.services.models.compare(
                    instruction=request.instruction,
                    dossiers=dossiers,
                    evidence=comparison_evidence,
                    repair_feedback=feedback,
                )
                usage_items.append(usage)
                feedback = validate_comparison_contract(comparison, dossiers, evidence)
                if not feedback:
                    self._event(state, "compare", "ok", attempts=attempt + 1)
                    return {
                        "comparison": comparison.model_dump(mode="json"),
                        "token_usage": _merge_usage_dicts(
                            state.get("token_usage", {}),
                            _sum_usage(usage_items).model_dump(),
                        ),
                    }
            self._event(state, "compare", "failed", errors=len(feedback))
            return {
                "failure_status": "failed_quality",
                "errors": feedback,
                "token_usage": _merge_usage_dicts(
                    state.get("token_usage", {}), _sum_usage(usage_items).model_dump()
                ),
            }
        except ProviderError as exc:
            self._event(state, "compare", "failed", error=type(exc).__name__)
            return {
                "failure_status": "provider_error",
                "errors": [str(exc)],
                "token_usage": _merge_usage_dicts(
                    state.get("token_usage", {}), _sum_usage(usage_items).model_dump()
                ),
            }

    def finalize(self, state: ResearchState) -> dict:
        status = state.get("failure_status") or "succeeded"
        dossiers = [
            TechnicalDossier.model_validate(item) for item in state.get("dossiers", [])
        ]
        evidence = [
            TechnicalEvidence.model_validate(item) for item in state.get("evidence", [])
        ]
        comparison = (
            TechnicalComparison.model_validate(state["comparison"])
            if state.get("comparison") is not None
            else None
        )
        job_dir = self.config.output_dir / state["job_id"]
        base = job_dir / "technical"
        staging = job_dir / f".technical.{uuid.uuid4().hex}.staging"
        staging.mkdir(parents=True, exist_ok=False)
        artifacts: list[TechnicalArtifactRef] = []
        evidence_path: Path | None = None
        try:
            evidence, visual_artifacts, visual_errors = _stage_visual_artifacts(
                evidence,
                staging=staging,
                published_base=base,
                work_dir=self.config.work_dir,
                previous_base=base,
            )
            artifacts.extend(visual_artifacts)
            if dossiers:
                for dossier in dossiers:
                    relative = (
                        Path("dossiers") / f"{_safe_name(dossier.paper.paper_id)}.json"
                    )
                    artifacts.append(
                        _write_artifact(
                            staging / relative,
                            dossier,
                            "dossier",
                            "research_documents",
                            published_path=base / relative,
                        )
                    )
            if evidence:
                evidence_path = base / "evidence_registry.json"
                artifacts.append(
                    _write_json_artifact(
                        staging / "evidence_registry.json",
                        [item.model_dump(mode="json") for item in evidence],
                        "evidence_registry",
                        "research_documents",
                        published_path=evidence_path,
                    )
                )
            if comparison is not None:
                artifacts.append(
                    _write_artifact(
                        staging / "comparison.json",
                        comparison,
                        "comparison",
                        "compare",
                        published_path=base / "comparison.json",
                    )
                )
            safe_traces = _sanitize_failed_draft_value(
                state.get("retrieval_traces", [])
            )
            trace_lines = "".join(
                json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n"
                for item in safe_traces
            )
            _atomic_text(staging / "retrieval_traces.jsonl", trace_lines)
            trace_digest = hashlib.sha256(trace_lines.encode("utf-8")).hexdigest()
            artifacts.append(
                TechnicalArtifactRef(
                    artifact_id=f"retrieval_trace-{trace_digest[:16]}",
                    type="retrieval_trace",
                    path=str((base / "retrieval_traces.jsonl").resolve()),
                    sha256=trace_digest,
                    producer="research_documents",
                )
            )

            evidence_rate, locator_rate = evidence_resolution_rates(dossiers, evidence)
            inventory = [
                item for dossier in dossiers for item in dossier.critical_inventory
            ]
            inventory_coverage = (
                sum(
                    item.disposition in {"extracted", "excluded", "unverified"}
                    for item in inventory
                )
                / len(inventory)
                if inventory
                else 0.0
            )
            diagnostics = [
                TechnicalDiagnostic(
                    node="technical_research", code="quality_error", message=value
                )
                for value in state.get("errors", [])
            ]
            diagnostics.extend(
                TechnicalDiagnostic(
                    node="finalize", code="visual_artifact_error", message=value
                )
                for value in visual_errors
            )
            quality = TechnicalQuality(
                evidence_resolution_rate=evidence_rate,
                locator_resolution_rate=locator_rate,
                critical_inventory_coverage=inventory_coverage,
                unsupported_numeric_claims=sum(
                    bool(audit.get("numeric_consistency_errors"))
                    for audit in state.get("audits", [])
                ),
                warnings=state.get("warnings", []),
            )
            if status == "succeeded" and (
                evidence_rate != 1.0
                or locator_rate != 1.0
                or inventory_coverage != 1.0
                or quality.unsupported_numeric_claims
                or visual_errors
            ):
                status = "failed_quality"
                diagnostics.append(
                    TechnicalDiagnostic(
                        node="finalize",
                        code="quality_gate",
                        message="기술조사 완전성 또는 근거 게이트를 통과하지 못했습니다.",
                    )
                )

            envelope = TechnicalResearchEnvelope(
                status=status,
                run=TechnicalRunMetadata(
                    job_id=state["job_id"],
                    openai_model=self.config.openai_model,
                    embedding_provider=getattr(
                        self.config, "research_embedding_provider", "bge-m3"
                    ),
                    embedding_model=getattr(self.config, "bge_model_id", "BAAI/bge-m3"),
                    embedding_revision=getattr(self.config, "bge_model_revision", None),
                    index_profile=getattr(self.services.retrieval, "profile_id", None),
                    evidence_id_version=EVIDENCE_ID_VERSION,
                    prompt_version=self.config.prompt_version,
                    index_version=self.config.index_version,
                    vision=_vision_run_metadata(self.config, self.services.visuals),
                    started_at=state["started_at"],
                    finished_at=utc_now(),
                    token_usage=TokenUsage.model_validate(state.get("token_usage", {})),
                    peak_rss_bytes=_peak_rss_bytes(),
                    completed_without_oom=True,
                ),
                artifacts=artifacts,
                dossiers=dossiers,
                comparison=comparison,
                evidence_registry_path=(
                    str(evidence_path.resolve()) if evidence_path else None
                ),
                quality=quality,
                diagnostics=diagnostics,
            )
            result_name = "run.json" if status == "succeeded" else "failure.json"
            _atomic_json(staging / result_name, envelope.model_dump(mode="json"))
            _publish_staged_directory(staging, base)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise
        run_path = base / result_name
        self._event(state, "finalize", "ok", result_status=status, output=str(run_path))
        return {"final_envelope": envelope.model_dump(mode="json")}

    def _research_one(
        self,
        path: Path,
        request: TechnicalResearchRequest,
        common_hashes: dict[str, str] | None = None,
        *,
        job_id: str | None = None,
    ) -> tuple[
        TechnicalDossier,
        list[TechnicalEvidence],
        TechnicalAudit,
        TokenUsage,
        list[dict],
    ]:
        parsed = self.services.documents.parse(
            path,
            document_id=paper_id_for_path(path),
            source_kind="paper",
            arxiv_id=path.stem
            if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", path.stem)
            else None,
            enforce_quality=True,
        )
        cache_path = _paper_research_cache_path(
            self.config,
            self.services.retrieval,
            self.services.visuals,
            parsed,
            request,
            common_hashes or {},
        )
        if not request.force_reindex:
            cached = _load_paper_research_cache(cache_path, parsed)
            if cached is not None:
                dossier, evidence, audit, traces = cached
                return dossier, evidence, audit, TokenUsage(), traces
            recovered = _recover_failed_paper_draft(
                config=self.config,
                parsed=parsed,
                common_hashes=common_hashes or {},
                models=self.services.models,
            )
            if recovered is not None:
                dossier, evidence, audit, recovered_usage, traces = recovered
                _save_paper_research_cache(cache_path, dossier, evidence, audit, traces)
                return dossier, evidence, audit, recovered_usage, traces
        self.services.retrieval.index_chunks(parsed.chunks, force=request.force_reindex)
        plan, plan_usage = self.services.models.plan_queries(
            parsed.metadata, request.instruction
        )
        query_groups = plan.model_dump()
        selected: list[Chunk] = []
        traces: list[dict] = []
        common_hashes = common_hashes or {}
        common_filters = RetrievalFilters(document_ids=tuple(sorted(common_hashes)))
        for name, queries in query_groups.items():
            selected.extend(
                self._retrieve_with_trace(
                    "paper", parsed.metadata.paper_id, queries, 8, traces
                )
            )
            if common_hashes:
                selected.extend(
                    self._retrieve_with_trace(
                        "common",
                        None,
                        queries,
                        4,
                        traces,
                        filters=common_filters,
                    )
                )
        selected = expand_caption_linked_context(
            _unique_chunks(selected), parsed.chunks
        )

        if self.services.visuals is not None:
            try:
                visual_chunks = self.services.visuals.enrich(
                    source_path=path,
                    parsed=parsed,
                    queries=query_groups.get("visuals", []),
                    retrieved_element_ids={
                        item.element_id for item in selected if item.element_id
                    },
                )
            except ProviderError as exc:
                raise _PaperResearchFailure(
                    str(exc),
                    status="provider_error",
                    token_usage=plan_usage,
                    retrieval_traces=traces,
                ) from exc
            if visual_chunks:
                # Vision enrichments are already selected evidence for this run.
                # Keeping them out of the persistent retrieval generation avoids
                # alternating between base-only and visual-enriched fingerprints
                # (and therefore rebuilding the full BGE index on every rerun).
                selected.extend(visual_chunks)
                selected = _unique_chunks(selected)

        _upsert_source_chunk_manifest(
            traces,
            selected,
            owner_document_id=parsed.metadata.paper_id,
        )

        source_hashes = {
            parsed.metadata.paper_id: parsed.metadata.source_hash,
            **common_hashes,
        }
        evidence = _unique_evidence(
            [
                item
                for chunk in selected
                for item in _technical_evidences(
                    chunk, source_hashes[chunk.document_id]
                )
            ]
        )
        repair_feedback: list[str] = []
        required_missing_topics: list[str] = []
        extraction: DossierExtraction | None = None
        previous_extraction: DossierExtraction | None = None
        audit: TechnicalAudit | None = None
        dossier: TechnicalDossier | None = None
        usage_items = [plan_usage]
        max_repairs = int(getattr(self.config, "max_quality_repairs", 2))
        for attempt in range(max_repairs + 1):
            try:
                candidate, extract_usage = self.services.models.extract_dossier(
                    paper=parsed.metadata,
                    evidence=evidence,
                    instruction=request.instruction,
                    output_language=request.output_language,
                    repair_feedback=_repair_feedback_with_previous_draft(
                        repair_feedback, previous_extraction
                    ),
                )
            except ProviderError as exc:
                raise _PaperResearchFailure(
                    str(exc),
                    status="provider_error",
                    token_usage=_sum_usage(usage_items),
                    retrieval_traces=traces,
                ) from exc
            usage_items.append(extract_usage)
            candidate = finalize_dossier_extraction(
                candidate,
                evidence=evidence,
                paper_id=parsed.metadata.paper_id,
            )
            if previous_extraction is not None:
                candidate = merge_dossier_extractions(
                    previous_extraction,
                    candidate,
                    repair_feedback=repair_feedback,
                )
            extraction = finalize_dossier_extraction(
                candidate,
                evidence=evidence,
                paper_id=parsed.metadata.paper_id,
            )
            dossier = TechnicalDossier(
                paper=parsed.metadata,
                analysis=extraction.analysis,
                claims=extraction.claims,
                critical_inventory=extraction.critical_inventory,
                experiment_observations=extraction.experiment_observations,
                unverified_items=extraction.unverified_items,
                evidence_ids=sorted(
                    {
                        value
                        for values in (
                            _analysis_evidence_ids(extraction.analysis),
                            [
                                value
                                for item in extraction.claims
                                for value in [
                                    *item.evidence_ids,
                                    *item.context_evidence_ids,
                                ]
                            ],
                            [
                                value
                                for item in extraction.experiment_observations
                                for value in item.evidence_ids
                            ],
                            [
                                value
                                for item in extraction.critical_inventory
                                for value in item.evidence_ids
                            ],
                        )
                        for value in values
                    }
                ),
            )
            try:
                audit, audit_usage = self.services.models.audit_dossier(
                    dossier, evidence
                )
            except ProviderError as exc:
                raise _PaperResearchFailure(
                    str(exc),
                    status="provider_error",
                    token_usage=_sum_usage(usage_items),
                    retrieval_traces=traces,
                ) from exc
            usage_items.append(audit_usage)
            errors, _ = validate_dossier_contract(dossier, evidence, audit)
            if not errors:
                _save_paper_research_cache(cache_path, dossier, evidence, audit, traces)
                return dossier, evidence, audit, _sum_usage(usage_items), traces
            # Replace, rather than union, the prior audit topic set.  Carrying
            # resolved topics forward makes a repaired dossier fail forever
            # even when the current audit supports the new atomic claim.
            required_missing_topics = list(
                dict.fromkeys(audit.missing_critical_topics)
            )
            repair_feedback = [
                *errors,
                *[
                    f"REQUIRED_CRITICAL_TOPIC: {topic}"
                    for topic in required_missing_topics
                ],
            ]
            previous_extraction = extraction
            if attempt < max_repairs and required_missing_topics:
                extra = self._retrieve_with_trace(
                    "paper",
                    parsed.metadata.paper_id,
                    required_missing_topics,
                    8,
                    traces,
                )
                common_extra = (
                    self._retrieve_with_trace(
                        "common",
                        None,
                        required_missing_topics,
                        4,
                        traces,
                        filters=common_filters,
                    )
                    if common_hashes
                    else []
                )
                selected = _unique_chunks([*selected, *extra, *common_extra])
                _upsert_source_chunk_manifest(
                    traces,
                    selected,
                    owner_document_id=parsed.metadata.paper_id,
                )
                evidence = _unique_evidence(
                    [
                        item
                        for chunk in selected
                        for item in _technical_evidences(
                            chunk, source_hashes[chunk.document_id]
                        )
                    ]
                )
        if dossier is None or audit is None:  # pragma: no cover - loop is non-empty
            raise ValueError("기술조사 품질 보강 루프가 결과 없이 종료되었습니다.")
        draft_path = _write_failed_paper_draft(
            config=self.config,
            job_id=job_id or request.job_id or "unknown-job",
            dossier=dossier,
            evidence=evidence,
            audit=audit,
            errors=repair_feedback,
            traces=traces,
            token_usage=_sum_usage(usage_items),
            attempts=max_repairs + 1,
        )
        raise _PaperResearchFailure(
            "기술조사 품질 보강 2회 후에도 근거 계약을 통과하지 못했습니다: "
            + "; ".join(repair_feedback)
            + f"; 실패 진단 초안: {draft_path}",
            status="failed_quality",
            token_usage=_sum_usage(usage_items),
            retrieval_traces=traces,
        )

    def _retrieve_with_trace(
        self,
        source_kind: str,
        document_id: str | None,
        queries: list[str],
        limit: int,
        traces: list[dict],
        *,
        filters: RetrievalFilters | None = None,
    ) -> list[Chunk]:
        method = getattr(self.services.retrieval, "retrieve_with_trace", None)
        if callable(method):
            result = (
                method(source_kind, document_id, queries, limit, filters=filters)
                if filters is not None
                else method(source_kind, document_id, queries, limit)
            )
            trace = getattr(result, "trace", None)
            if trace is not None:
                traces.append(
                    trace.to_dict() if hasattr(trace, "to_dict") else dict(trace)
                )
            return _as_chunks(getattr(result, "hits", getattr(result, "chunks", [])))
        result = (
            self.services.retrieval.retrieve(
                source_kind, document_id, queries, limit, filters=filters
            )
            if filters is not None
            else self.services.retrieval.retrieve(
                source_kind, document_id, queries, limit
            )
        )
        return _as_chunks(result)

    def _index_common_sources(
        self, paths: list[Path], *, force: bool
    ) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for path in paths:
            parsed = self.services.documents.parse(
                path,
                document_id=common_id_for_path(path),
                source_kind="common",
                enforce_quality=True,
            )
            self.services.retrieval.index_chunks(parsed.chunks, force=force)
            hashes[parsed.metadata.paper_id] = parsed.metadata.source_hash
        return hashes

    def _event(
        self, state: ResearchState, node: str, status: str, **details: object
    ) -> None:
        payload = {
            "timestamp": utc_now().isoformat(),
            "job_id": state.get("job_id"),
            "node": node,
            "status": status,
            **details,
        }
        path = self.config.work_dir / f"research-{state.get('job_id', 'unknown')}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def build_technical_research_graph(config: AppConfig, services: ResearchServices):
    workflow = TechnicalResearchWorkflow(config, services)
    document_graph = _build_document_research_subgraph(workflow)
    graph = StateGraph(ResearchState)
    graph.add_node("resolve_sources", workflow.resolve_sources)
    graph.add_node("research_documents", document_graph)
    graph.add_node("compare", workflow.compare)
    graph.add_node("finalize", workflow.finalize)
    graph.add_edge(START, "resolve_sources")
    graph.add_conditional_edges(
        "resolve_sources",
        lambda state: (
            "finalize" if state.get("failure_status") else "research_documents"
        ),
        {"finalize": "finalize", "research_documents": "research_documents"},
    )
    graph.add_conditional_edges(
        "research_documents",
        lambda state: "finalize" if state.get("failure_status") else "compare",
        {"finalize": "finalize", "compare": "compare"},
    )
    graph.add_edge("compare", "finalize")
    graph.add_edge("finalize", END)
    checkpointer = None
    if config.checkpoint_enabled:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise DependencyError("기술조사 체크포인트 의존성이 없습니다.") from exc
        checkpoint_path = getattr(
            config,
            "research_checkpoint_path",
            config.work_dir / "research-checkpoints.sqlite",
        )
        connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
        checkpointer = SqliteSaver(connection)
    return graph.compile(checkpointer=checkpointer, name="technical-research")


def _build_document_research_subgraph(workflow: TechnicalResearchWorkflow):
    """Expose truthful, checkpointable paper-research execution boundaries."""

    graph = StateGraph(ResearchState)
    graph.add_node("index_common_sources", workflow.index_common_sources)
    graph.add_node("parse_documents", workflow.parse_documents)
    graph.add_node("seed_critical_inventory", workflow.seed_critical_inventory)
    graph.add_node("index_paper_sources", workflow.index_paper_sources)
    graph.add_node("plan_paper_queries", workflow.plan_paper_queries)
    graph.add_node("retrieve_paper_evidence", workflow.retrieve_paper_evidence)
    graph.add_node("enrich_paper_visuals", workflow.enrich_paper_visuals)
    graph.add_node("extract_paper_dossiers", workflow.extract_paper_dossiers)
    graph.add_node("audit_paper_dossiers", workflow.audit_paper_dossiers)
    graph.add_node("collect_documents", workflow.collect_documents)

    graph.add_edge(START, "index_common_sources")
    graph.add_conditional_edges(
        "index_common_sources",
        lambda state: (
            "collect_documents" if state.get("failure_status") else "parse_documents"
        ),
        {
            "collect_documents": "collect_documents",
            "parse_documents": "parse_documents",
        },
    )
    graph.add_edge("parse_documents", "seed_critical_inventory")
    graph.add_edge("seed_critical_inventory", "index_paper_sources")
    graph.add_edge("index_paper_sources", "plan_paper_queries")
    graph.add_edge("plan_paper_queries", "retrieve_paper_evidence")
    graph.add_edge("retrieve_paper_evidence", "enrich_paper_visuals")
    graph.add_edge("enrich_paper_visuals", "extract_paper_dossiers")
    graph.add_edge("extract_paper_dossiers", "audit_paper_dossiers")
    graph.add_conditional_edges(
        "audit_paper_dossiers",
        workflow.route_after_paper_audit,
        {
            "extract_paper_dossiers": "extract_paper_dossiers",
            "collect_documents": "collect_documents",
        },
    )
    graph.add_edge("collect_documents", END)
    return graph.compile(name="paper-research-stages")


def _resolve_sources(
    request: TechnicalResearchRequest, cwd: Path, documents: DocumentService
) -> list[Path]:
    raw = list(request.sources)
    if not raw:
        raw = [str(path) for path in extract_source_paths(request.instruction, cwd)]
    if not raw:
        raise ValueError(
            "자연어 지시 또는 --source로 PDF/TXT/Markdown/arXiv 입력을 지정하세요."
        )
    resolved: list[Path] = []
    seen: set[str] = set()
    for source in raw:
        path, _ = documents.resolve_source(source)
        digest = _sha256_file(path)
        if digest not in seen:
            seen.add(digest)
            resolved.append(path)
    return resolved


def _resolve_common_sources(
    request: TechnicalResearchRequest, cwd: Path, documents: DocumentService
) -> list[Path]:
    """Resolve only the explicitly approved common-corpus allow-list."""

    resolved: list[Path] = []
    seen: set[str] = set()
    for source in request.common_sources:
        path, _ = documents.resolve_source(source)
        digest = _sha256_file(path)
        if digest not in seen:
            seen.add(digest)
            resolved.append(path)
    return resolved


def _technical_evidences(chunk: Chunk, source_hash: str) -> list[TechnicalEvidence]:
    """Expand a retrieved table into an aggregate plus independently citable cells."""

    aggregate = _technical_evidence(chunk, source_hash, table_cells=[])
    if not chunk.table_cells:
        return [aggregate]
    cells: list[TechnicalEvidence] = []
    for cell in chunk.table_cells:
        context = [
            chunk.object_label or "table",
            f"row={cell.row_index}",
            f"column={cell.column_index}",
        ]
        if cell.row_header:
            context.append(f"row_header={cell.row_header}")
        if cell.column_header:
            context.append(f"column_header={cell.column_header}")
        context.append(f"value={cell.raw_text}")
        snippet = "; ".join(context)
        cells.append(
            _technical_evidence(
                chunk,
                source_hash,
                table_cells=[cell.model_dump(mode="python")],
                snippet=snippet,
                content_hash=hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
                suffix=format_table_cell_suffix(
                    cell.row_index, cell.column_index
                ),
            )
        )
    return [aggregate, *cells]


def _upsert_source_chunk_manifest(
    traces: list[dict],
    chunks: list[Chunk],
    *,
    owner_document_id: str,
) -> None:
    """Bind published locators to selected source chunks without copying text.

    ``validate-technical`` can use this record to resolve every evidence entry
    against the exact chunk that produced it.  Only hashes and locator metadata
    are recorded; source prose is already bounded separately by evidence
    snippets and is not duplicated into the trace log.
    """

    traces[:] = [
        item
        for item in traces
        if not (
            item.get("trace_kind") == "source_chunk_manifest"
            and item.get("owner_document_id") == owner_document_id
        )
    ]
    manifests: list[dict[str, object]] = []
    for chunk in sorted(chunks, key=lambda item: item.chunk_id):
        raw = chunk.model_dump(mode="json")
        manifests.append(
            {
                "source_chunk_id": chunk.chunk_id,
                "source_kind": chunk.source_kind,
                "document_id": chunk.document_id,
                "document_version": chunk.document_version,
                "physical_page": chunk.page,
                "section": chunk.section,
                "content_kind": chunk.content_kind,
                "content_hash": chunk.content_hash,
                "text_length": len(chunk.text),
                "source_element_id": chunk.element_id
                or f"{chunk.content_kind}-{chunk.chunk_id}",
                "parent_element_id": chunk.parent_element_id,
                "object_label": chunk.object_label,
                "printed_page_label": chunk.printed_page,
                "bbox_pt": _bbox_tuple_from_chunk(raw.get("bbox")),
                "text_span": raw.get("text_span")
                or ({"start": 0, "end": len(chunk.text)} if chunk.text else None),
                "extraction_method": chunk.extraction_method,
                "crop_sha256": chunk.crop_hash,
                "table_cells": [
                    {
                        "row_index": cell.row_index,
                        "column_index": cell.column_index,
                        "sha256": _table_cell_locator_hash(
                            cell.row_index,
                            cell.column_index,
                            cell.raw_text,
                            cell.row_header,
                            cell.column_header,
                        ),
                    }
                    for cell in chunk.table_cells
                ],
            }
        )
    traces.append(
        {
            "trace_kind": "source_chunk_manifest",
            "manifest_version": EVIDENCE_ID_VERSION,
            "owner_document_id": owner_document_id,
            "chunks": manifests,
        }
    )


def _bbox_tuple_from_chunk(value: object) -> list[float] | None:
    if not isinstance(value, dict):
        return None
    try:
        return [float(value[key]) for key in ("x0", "y0", "x1", "y1")]
    except (KeyError, TypeError, ValueError):
        return None


def _table_cell_locator_hash(
    row_index: int,
    column_index: int,
    raw_text: str,
    row_header: str | None,
    column_header: str | None,
) -> str:
    payload = json.dumps(
        [row_index, column_index, raw_text, row_header, column_header],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _technical_evidence(
    chunk: Chunk,
    source_hash: str,
    *,
    table_cells: list[dict] | None = None,
    snippet: str | None = None,
    content_hash: str | None = None,
    suffix: str | None = None,
) -> TechnicalEvidence:
    raw = chunk.model_dump(mode="python")
    page = raw.get("page")
    source_element_id = (
        raw.get("element_id") or f"{raw.get('content_kind', 'text')}-{chunk.chunk_id}"
    )
    bbox = raw.get("bbox_pt") or raw.get("bbox")
    bbox_tuple = None
    page_size = raw.get("page_size_pt")
    if isinstance(bbox, dict):
        bbox_tuple = tuple(float(bbox[key]) for key in ("x0", "y0", "x1", "y1"))
        if not page_size and bbox.get("page_width") and bbox.get("page_height"):
            page_size = (float(bbox["page_width"]), float(bbox["page_height"]))
    elif bbox:
        bbox_tuple = tuple(bbox)
    resolved_cells = (
        raw.get("table_cells") or [] if table_cells is None else table_cells
    )
    content_kind = raw.get("content_kind", "text")
    if content_kind not in {"text", "table", "caption", "figure", "chart", "diagram"}:
        content_kind = "text"
    element_id, normalized_object_label = evidence_element_id(
        object_label=raw.get("object_label"),
        content_kind=content_kind,
        source_element_id=str(source_element_id),
    )
    if suffix is None:
        suffix = (
            table_aggregate_suffix(
                chunk_text=chunk.text,
                span_end=(raw.get("text_span") or {}).get("end", len(chunk.text)),
                row_indices=[cell.row_index for cell in chunk.table_cells],
                chunk_id=chunk.chunk_id,
            )
            if chunk.content_kind == "table"
            else "whole"
            if content_kind in {"figure", "chart", "diagram"}
            else f"span-{0:05d}-{len(chunk.text):05d}"
        )
    evidence_id = (
        f"{chunk.source_kind}:{chunk.document_id}@{source_hash[:12]}:"
        f"p{int(page or 0):04d}:{element_id}:{suffix}"
    )
    section = raw.get("section")
    section_path = raw.get("section_path") or ([section] if section else [])
    extraction_method = raw.get("extraction_method") or (
        "pdfplumber" if chunk.content_kind == "table" else "native_text"
    )
    return TechnicalEvidence(
        evidence_id=evidence_id,
        source_kind=chunk.source_kind,
        document_id=chunk.document_id,
        content_kind=content_kind,
        extraction_method=extraction_method,
        snippet=snippet or chunk.text,
        content_hash=content_hash or chunk.content_hash,
        locator=EvidenceLocator(
            document_sha256=source_hash,
            physical_page=page,
            printed_page_label=raw.get("printed_page_label") or raw.get("printed_page"),
            section_path=section_path,
            element_id=str(element_id),
            source_chunk_id=chunk.chunk_id,
            source_element_id=str(source_element_id),
            object_label=raw.get("object_label"),
            normalized_object_label=normalized_object_label,
            parent_element_id=raw.get("parent_element_id"),
            bbox_pt=bbox_tuple,
            page_size_pt=tuple(page_size) if page_size else None,
            text_span=(
                TextSpan.model_validate(raw["text_span"])
                if raw.get("text_span")
                else TextSpan(start=0, end=len(chunk.text))
                if chunk.text
                else None
            ),
            table_cells=resolved_cells,
            visual_artifact_id=raw.get("visual_artifact_id")
            or (str(source_element_id) if extraction_method == "vision" else None),
            crop_sha256=raw.get("crop_sha256") or raw.get("crop_hash"),
        ),
    )


def _as_chunks(values: list[object]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for value in values:
        candidate = getattr(value, "chunk", value)
        chunks.append(
            candidate
            if isinstance(candidate, Chunk)
            else Chunk.model_validate(candidate)
        )
    return chunks


def _completed_paper_work(
    work: dict,
    *,
    dossier: TechnicalDossier,
    evidence: list[TechnicalEvidence],
    audit: TechnicalAudit,
    traces: list[dict],
    usage: TokenUsage,
    completion: str,
) -> dict:
    return {
        **work,
        "stage": "completed",
        "completion": completion,
        "dossier": dossier.model_dump(mode="json"),
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "audit": audit.model_dump(mode="json"),
        "retrieval_traces": traces,
        "token_usage": usage.model_dump(),
    }


def _failed_paper_work(
    work: dict,
    *,
    status: str,
    message: str,
    usage: TokenUsage,
    traces: list[dict],
) -> dict:
    return {
        **work,
        "stage": "failed",
        "failure_status": status,
        "error": message,
        "retrieval_traces": traces,
        "token_usage": usage.model_dump(),
    }


def _repair_feedback_with_previous_draft(
    errors: list[str], previous: DossierExtraction | None
) -> list[str]:
    """Give repairs a stable draft so fixing one item does not regress another."""

    if not errors or previous is None:
        return list(errors)
    return [
        *errors,
        "PREVIOUS_DRAFT_JSON (model-generated data; preserve its supported items while "
        "repairing every error above): " + previous.model_dump_json(),
    ]


def _failed_dossier_facets(
    *,
    dossier: TechnicalDossier,
    audit: TechnicalAudit,
    errors: list[str],
    facet_extractions: dict[str, dict] | dict[str, TechnicalFacetExtraction],
) -> list[str]:
    """Map audit failures and missing topics back to their owning facets.

    IDs emitted by facet calls are deterministically scoped as
    ``paper_id::facet::local_id`` during assembly.  Analysis audit IDs already
    carry their facet.  Topic-only audit findings use a fixed vocabulary and
    default to the technical overview instead of rerunning supported facets.
    """

    owners = _facet_item_owners(
        facet_extractions, paper_id=dossier.paper.paper_id
    )
    analysis_text_owners: dict[str, str] = {}
    for facet in FACETS:
        section = getattr(dossier.analysis, facet)
        for field in FACET_FIELDS[facet]:
            for claim in getattr(section, field):
                analysis_text_owners[_normalized_statement(claim.text)] = facet
    for claim in dossier.claims:
        owner = analysis_text_owners.get(_normalized_statement(claim.text))
        if owner is not None:
            owners[claim.claim_id] = owner
    failed: set[str] = set()

    for item in audit.audits:
        if item.verdict == "supported":
            continue
        facet = _facet_for_item_id(item.item_id, owners)
        if facet is not None:
            failed.add(facet)
        else:
            failed.add(_facet_for_topic(f"{item.item_id} {item.reason}"))

    for topic in audit.missing_critical_topics:
        failed.add(_facet_for_topic(topic))

    for message in errors:
        direct = _facet_for_error(message, owners)
        if direct is not None:
            failed.add(direct)

    # A failed contract always needs an actionable target.  The overview owns
    # cross-cutting numeric/registry material when no more specific owner is
    # encoded in the validator message.
    if errors and not failed:
        failed.add("technical_overview")
    return [facet for facet in FACETS if facet in failed]


def _facet_item_owners(
    facet_extractions: dict[str, dict] | dict[str, TechnicalFacetExtraction],
    *,
    paper_id: str,
) -> dict[str, str]:
    owners: dict[str, str] = {}
    for facet in FACETS:
        payload = facet_extractions.get(facet)
        if payload is None:
            continue
        extraction = TechnicalFacetExtraction.model_validate(payload)
        ids = [
            *[item.claim_id for item in extraction.claims],
            *[
                item.observation_id
                for item in extraction.experiment_observations
            ],
            *[item.inventory_id for item in extraction.critical_inventory],
            *[item.item_id for item in extraction.unverified_items],
        ]
        for raw in ids:
            scoped = raw if raw.startswith(f"{facet}::") else f"{facet}::{raw}"
            final = (
                scoped
                if scoped.startswith(f"{paper_id}::")
                else f"{paper_id}::{scoped}"
            )
            for value in (raw, scoped, final):
                owners[value] = facet
    return owners


def _facet_for_item_id(item_id: str, owners: dict[str, str]) -> str | None:
    analysis_match = re.match(
        r"^analysis\.(technical_overview|scope|limitations)\.", item_id
    )
    if analysis_match is not None:
        return analysis_match.group(1)
    if item_id in owners:
        return owners[item_id]
    # Auto-materialized critical claims retain the originating analysis field
    # only semantically, so their audit reason is handled by the topic mapper.
    return None


def _facet_for_error(message: str, owners: dict[str, str]) -> str | None:
    analysis_match = re.search(
        r"analysis\.(technical_overview|scope|limitations)\.", message
    )
    if analysis_match is not None:
        return analysis_match.group(1)
    for item_id in sorted(owners, key=len, reverse=True):
        if item_id in message:
            return owners[item_id]
    normalized = message.casefold()
    if "problem_definition is empty" in normalized:
        return "technical_overview"
    if "core_approach is empty" in normalized:
        return "technical_overview"
    if "experimental_results is empty" in normalized:
        return "technical_overview"
    if "no limitation or constraint" in normalized:
        return "limitations"
    if normalized.startswith("missing critical topic:") or normalized.startswith(
        "required_critical_topic:"
    ):
        return _facet_for_topic(message.split(":", 1)[-1])
    if normalized.startswith("numeric consistency:"):
        return "technical_overview"
    if normalized.startswith("overgeneralization:"):
        return _facet_for_topic(message)
    return None


def _facet_for_topic(topic: str) -> str:
    normalized = topic.casefold().replace("_", " ")
    limitation_terms = (
        "limitation",
        "constraint",
        "failure case",
        "future work",
        "pending validation",
        "pending physical",
        "physical validation",
        "reproduc",
        "generaliz",
        "not validated",
        "unverified",
        "한계",
        "제약",
        "실패",
        "재현",
        "일반화",
        "미검증",
    )
    scope_terms = (
        "scope",
        "operating condition",
        "applicable",
        "target task",
        "domain",
        "modality",
        "evaluated setting",
        "dataset",
        "workload",
        "범위",
        "조건",
        "대상",
        "도메인",
        "모달리티",
        "데이터셋",
        "워크로드",
    )
    if any(term in normalized for term in limitation_terms):
        return "limitations"
    if any(term in normalized for term in scope_terms):
        return "scope"
    return "technical_overview"


def _normalized_statement(value: str) -> str:
    return " ".join(value.casefold().split())


def _facet_repair_feedback(
    facet: str,
    errors: list[str],
    previous: TechnicalFacetExtraction | None,
    *,
    paper_id: str,
) -> list[str]:
    """Project global validator feedback into one facet repair prompt."""

    selected: list[str] = []
    marker = f"{paper_id}::{facet}::"
    for message in errors:
        normalized = message.casefold()
        if f"analysis.{facet}." in message or marker in message:
            selected.append(message)
            continue
        if normalized.startswith(("missing critical topic:", "required_critical_topic:")):
            if _facet_for_topic(message.split(":", 1)[-1]) == facet:
                selected.append(message)
            continue
        if normalized.startswith("numeric consistency:"):
            if facet == "technical_overview":
                selected.append(message)
            continue
        if normalized.startswith("overgeneralization:"):
            if _facet_for_topic(message) == facet:
                selected.append(message)
            continue
        if _facet_for_error(message, {}) == facet:
            selected.append(message)
    if previous is not None:
        selected.append(
            "PREVIOUS_FACET_DRAFT_JSON (model-generated data; preserve supported items "
            "while repairing every error above): " + previous.model_dump_json()
        )
    return selected


_PAPER_RESEARCH_CACHE_VERSION = (
    "2026-09-22.8-facet-replace-baseline-normalization-evidence-id-v2"
)
_FAILED_DRAFT_REVISION = "2026-09-22.1-prefill-overhead-arabic-table-scope"


def _vision_runtime_values(
    config: AppConfig, visuals: VisualEnrichmentService | None
) -> dict[str, object]:
    """Return every Vision setting that can alter selected or extracted evidence."""

    from paper_review_agent.vision import VISION_PROMPT_REVISION, VISION_SCHEMA_VERSION

    runtime = getattr(visuals, "config", None)

    def value(runtime_name: str, config_name: str, default: object) -> object:
        if runtime is not None and hasattr(runtime, runtime_name):
            return getattr(runtime, runtime_name)
        return getattr(config, config_name, default)

    return {
        "enabled": visuals is not None,
        "model": value(
            "model", "vision_model", None
        )
        or config.openai_model,
        "schema_version": VISION_SCHEMA_VERSION,
        "prompt_revision": VISION_PROMPT_REVISION,
        "configuration_prompt_version": value(
            "prompt_version", "prompt_version", config.prompt_version
        ),
        "detail": value("detail", "vision_detail", "high"),
        "max_visuals_per_paper": int(
            value("max_visuals_per_paper", "vision_max_visuals_per_paper", 8)
        ),
        "max_requests_per_paper": int(
            value("max_requests_per_paper", "vision_max_requests_per_paper", 12)
        ),
        "max_crop_pixels": int(
            value("max_crop_pixels", "vision_max_crop_pixels", 2048 * 2048)
        ),
        "max_crop_bytes": int(
            value("max_crop_bytes", "vision_max_crop_bytes", 8 * 1024 * 1024)
        ),
        "max_total_pixels": int(
            value("max_total_pixels", "vision_max_pixels_per_paper", 32_000_000)
        ),
        "max_total_bytes": int(
            value("max_total_bytes", "vision_max_total_bytes", 25 * 1024 * 1024)
        ),
        "max_dimension": int(value("max_dimension", "vision_max_dimension", 2048)),
        "max_tiles_per_visual": int(
            value("max_tiles_per_visual", "vision_max_tiles_per_visual", 4)
        ),
        "render_dpi": int(value("render_dpi", "vision_render_dpi", 216)),
        "tile_overlap": float(value("tile_overlap", "vision_tile_overlap", 0.10)),
        "max_context_chars": int(
            value("max_context_chars", "vision_max_context_chars", 4000)
        ),
        "max_output_tokens": int(
            value("max_output_tokens", "vision_max_output_tokens", 10_000)
        ),
        "provider_attempts": int(
            value("provider_attempts", "vision_provider_attempts", 3)
        ),
        "max_concurrency": int(
            value("max_concurrency", "vision_concurrency", 2)
        ),
    }


def _vision_run_metadata(
    config: AppConfig, visuals: VisualEnrichmentService | None
) -> TechnicalVisionRunMetadata:
    values = _vision_runtime_values(config, visuals)
    return TechnicalVisionRunMetadata(
        enabled=bool(values["enabled"]),
        model=str(values["model"]) if values["model"] else None,
        schema_version=str(values["schema_version"]),
        prompt_revision=str(values["prompt_revision"]),
        configuration_prompt_version=str(values["configuration_prompt_version"]),
        max_visuals_per_paper=int(values["max_visuals_per_paper"]),
        max_requests_per_paper=int(values["max_requests_per_paper"]),
        max_pixels_per_paper=int(values["max_total_pixels"]),
        max_concurrency=int(values["max_concurrency"]),
    )


def _paper_research_cache_path(
    config: AppConfig,
    retrieval: TechnicalRetrievalService,
    visuals: VisualEnrichmentService | None,
    parsed: ParsedDocument,
    request: TechnicalResearchRequest,
    common_hashes: dict[str, str],
) -> Path:
    payload = {
        "cache_version": _PAPER_RESEARCH_CACHE_VERSION,
        "evidence_id_version": EVIDENCE_ID_VERSION,
        "schema_version": TECHNICAL_SCHEMA_VERSION,
        "source_hash": parsed.metadata.source_hash,
        "source_path": str(Path(parsed.metadata.source_path).resolve()),
        "common_hashes": sorted(common_hashes.items()),
        "instruction": request.instruction,
        "output_language": request.output_language,
        "openai_model": config.openai_model,
        "audit_model": config.audit_model,
        "prompt_version": config.prompt_version,
        "index_version": config.index_version,
        "index_profile": getattr(retrieval, "profile_id", None),
        "vision": _vision_runtime_values(config, visuals),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return config.work_dir / "technical-paper-cache" / f"{digest}.json"


def _load_paper_research_cache(
    path: Path, parsed: ParsedDocument
) -> (
    tuple[
        TechnicalDossier,
        list[TechnicalEvidence],
        TechnicalAudit,
        list[dict],
    ]
    | None
):
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("cache_version") != _PAPER_RESEARCH_CACHE_VERSION
            or payload.get("evidence_id_version") != EVIDENCE_ID_VERSION
        ):
            return None
        dossier = TechnicalDossier.model_validate(payload["dossier"])
        evidence = [
            TechnicalEvidence.model_validate(item) for item in payload["evidence"]
        ]
        audit = TechnicalAudit.model_validate(payload["audit"])
        traces = list(payload.get("retrieval_traces", []))
        if not _traces_resolve_evidence_sources(traces, evidence):
            return None
        if dossier.paper.source_hash != parsed.metadata.source_hash:
            return None
        if (
            Path(dossier.paper.source_path).resolve()
            != Path(parsed.metadata.source_path).resolve()
        ):
            return None
        errors, _ = validate_dossier_contract(dossier, evidence, audit)
        if errors:
            return None
        return dossier, evidence, audit, traces
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _save_paper_research_cache(
    path: Path,
    dossier: TechnicalDossier,
    evidence: list[TechnicalEvidence],
    audit: TechnicalAudit,
    traces: list[dict],
) -> None:
    payload = {
        "cache_version": _PAPER_RESEARCH_CACHE_VERSION,
        "evidence_id_version": EVIDENCE_ID_VERSION,
        "dossier": dossier.model_dump(mode="json"),
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "audit": audit.model_dump(mode="json"),
        "retrieval_traces": traces,
    }
    raw = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n"
    ).encode("utf-8")
    atomic_write(path, raw)


def _recover_failed_paper_draft(
    *,
    config: AppConfig,
    parsed: ParsedDocument,
    common_hashes: dict[str, str],
    models: TechnicalModelGateway | None = None,
) -> (
    tuple[
        TechnicalDossier,
        list[TechnicalEvidence],
        TechnicalAudit,
        TokenUsage,
        list[dict],
    ]
    | None
):
    """Promote a now-valid failed draft without repeating provider calls.

    Failed drafts are diagnostic artifacts, not trusted caches.  Each candidate
    is therefore reparsed and rebound to the current parser metadata, passed
    through the current deterministic finalizer, and checked against the full
    dossier contract.  A changed paper, common corpus, schema, unsupported
    audit, malformed registry, or path mismatch makes the candidate ineligible.
    """

    root = (config.work_dir / "technical-failed-drafts").resolve()
    if not root.is_dir():
        return None
    filename = f"{_safe_name(parsed.metadata.paper_id)}.json"
    candidates: list[tuple[int, Path]] = []
    try:
        for candidate in root.glob(f"*/{filename}"):
            resolved = candidate.resolve()
            if (
                candidate.is_symlink()
                or not resolved.is_relative_to(root)
                or not resolved.is_file()
            ):
                continue
            candidates.append((resolved.stat().st_mtime_ns, resolved))
    except (OSError, RuntimeError):
        return None

    for _, candidate in sorted(candidates, reverse=True):
        recovered = _load_failed_paper_draft(
            candidate,
            parsed=parsed,
            common_hashes=common_hashes,
        )
        if recovered is not None:
            return recovered
        if models is None:
            continue
        repairable = _load_failed_paper_draft(
            candidate,
            parsed=parsed,
            common_hashes=common_hashes,
            require_supported_audit=False,
        )
        if repairable is None:
            continue
        dossier, evidence, previous_audit, prior_usage, traces = repairable
        # Re-audit only when deterministic normalization changed the public
        # item set (for example, a fixed auto-claim projection).  A draft whose
        # same items were genuinely judged partial/unsupported must return to
        # extraction rather than laundering that verdict through recovery.
        expected_ids = {
            *[item.claim_id for item in dossier.claims],
            *[item.observation_id for item in dossier.experiment_observations],
            *analysis_audit_item_ids(dossier),
        }
        if {item.item_id for item in previous_audit.audits} == expected_ids:
            continue
        audit, audit_usage = models.audit_dossier(dossier, evidence)
        errors, _ = validate_dossier_contract(dossier, evidence, audit)
        if not errors:
            return (
                dossier,
                evidence,
                audit,
                _sum_usage([prior_usage, audit_usage]),
                traces,
            )
    return None


def _load_failed_paper_draft(
    path: Path,
    *,
    parsed: ParsedDocument,
    common_hashes: dict[str, str],
    require_supported_audit: bool = True,
) -> (
    tuple[
        TechnicalDossier,
        list[TechnicalEvidence],
        TechnicalAudit,
        TokenUsage,
        list[dict],
    ]
    | None
):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("schema_version") != TECHNICAL_SCHEMA_VERSION
            or payload.get("cache_version") != _PAPER_RESEARCH_CACHE_VERSION
            or payload.get("draft_revision") != _FAILED_DRAFT_REVISION
            or payload.get("evidence_id_version") != EVIDENCE_ID_VERSION
            or payload.get("kind") != "failed_paper_technical_draft"
            or payload.get("paper_id") != parsed.metadata.paper_id
        ):
            return None

        stored_dossier = TechnicalDossier.model_validate(payload["dossier"])
        evidence = [
            TechnicalEvidence.model_validate(item) for item in payload["evidence"]
        ]
        audit = TechnicalAudit.model_validate(payload["audit"])
        token_usage = TokenUsage.model_validate(payload.get("token_usage", {}))
        raw_traces = payload.get("retrieval_traces", [])
        if not isinstance(raw_traces, list) or any(
            not isinstance(item, dict) for item in raw_traces
        ):
            return None
        traces = [dict(item) for item in raw_traces]
        if not _traces_resolve_evidence_sources(traces, evidence):
            return None

        if (
            stored_dossier.paper.paper_id != parsed.metadata.paper_id
            or stored_dossier.paper.source_hash != parsed.metadata.source_hash
            or Path(stored_dossier.paper.source_path).expanduser().resolve()
            != Path(parsed.metadata.source_path).expanduser().resolve()
        ):
            return None
        if any(
            value < 0
            for value in (
                token_usage.input_tokens,
                token_usage.output_tokens,
                token_usage.total_tokens,
            )
        ):
            return None
        if not _failed_draft_evidence_matches_sources(
            evidence,
            parsed=parsed,
            common_hashes=common_hashes,
        ):
            return None

        extraction = finalize_dossier_extraction(
            DossierExtraction(
                analysis=stored_dossier.analysis,
                claims=stored_dossier.claims,
                critical_inventory=stored_dossier.critical_inventory,
                experiment_observations=stored_dossier.experiment_observations,
                unverified_items=stored_dossier.unverified_items,
            ),
            evidence=evidence,
            paper_id=parsed.metadata.paper_id,
        )
        dossier = _dossier_from_extraction(parsed, extraction)

        expected_audit_ids = {
            *[item.claim_id for item in dossier.claims],
            *[item.observation_id for item in dossier.experiment_observations],
            *analysis_audit_item_ids(dossier),
        }
        actual_audit_ids = [item.item_id for item in audit.audits]
        evidence_ids = {item.evidence_id for item in evidence}
        audit_invalid = (
            len(actual_audit_ids) != len(set(actual_audit_ids))
            or set(actual_audit_ids) != expected_audit_ids
            or any(item.verdict != "supported" for item in audit.audits)
            or any(
                evidence_id not in evidence_ids
                for item in audit.audits
                for evidence_id in item.evidence_ids
            )
        )
        if require_supported_audit and audit_invalid:
            return None
        if require_supported_audit:
            errors, _ = validate_dossier_contract(dossier, evidence, audit)
            if errors:
                return None
        return dossier, evidence, audit, token_usage, traces
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
    ):
        return None


def _failed_draft_evidence_matches_sources(
    evidence: list[TechnicalEvidence],
    *,
    parsed: ParsedDocument,
    common_hashes: dict[str, str],
) -> bool:
    ids = [item.evidence_id for item in evidence]
    if not evidence or len(ids) != len(set(ids)):
        return False
    paper_prefix = (
        f"paper:{parsed.metadata.paper_id}@{parsed.metadata.source_hash[:12]}:"
    )
    for item in evidence:
        if (
            hashlib.sha256(item.snippet.encode("utf-8")).hexdigest()
            != item.content_hash
        ):
            return False
        if item.source_kind == "paper":
            if (
                item.document_id != parsed.metadata.paper_id
                or item.locator.document_sha256 != parsed.metadata.source_hash
                or not item.evidence_id.startswith(paper_prefix)
            ):
                return False
        else:
            expected_hash = common_hashes.get(item.document_id)
            if (
                expected_hash is None
                or item.locator.document_sha256 != expected_hash
                or not item.evidence_id.startswith(
                    f"common:{item.document_id}@{expected_hash[:12]}:"
                )
            ):
                return False
    return True


def _traces_resolve_evidence_sources(
    traces: list[dict], evidence: list[TechnicalEvidence]
) -> bool:
    available: set[tuple[str, str, str]] = set()
    for trace in traces:
        if (
            trace.get("trace_kind") != "source_chunk_manifest"
            or trace.get("manifest_version") != EVIDENCE_ID_VERSION
        ):
            continue
        for raw in trace.get("chunks", []):
            if not isinstance(raw, dict):
                return False
            key = (
                raw.get("source_kind"),
                raw.get("document_id"),
                raw.get("source_chunk_id"),
            )
            if not all(isinstance(value, str) and value for value in key):
                return False
            available.add(key)  # type: ignore[arg-type]
    return bool(available) and all(
        item.locator.source_chunk_id is not None
        and (item.source_kind, item.document_id, item.locator.source_chunk_id)
        in available
        for item in evidence
    )


def _dossier_from_extraction(
    parsed: ParsedDocument, extraction: DossierExtraction
) -> TechnicalDossier:
    evidence_ids = sorted(
        {
            value
            for values in (
                _analysis_evidence_ids(extraction.analysis),
                [
                    value
                    for item in extraction.claims
                    for value in [*item.evidence_ids, *item.context_evidence_ids]
                ],
                [
                    value
                    for item in extraction.experiment_observations
                    for value in item.evidence_ids
                ],
                [
                    value
                    for item in extraction.critical_inventory
                    for value in item.evidence_ids
                ],
            )
            for value in values
        }
    )
    return TechnicalDossier(
        paper=parsed.metadata,
        analysis=extraction.analysis,
        claims=extraction.claims,
        critical_inventory=extraction.critical_inventory,
        experiment_observations=extraction.experiment_observations,
        unverified_items=extraction.unverified_items,
        evidence_ids=evidence_ids,
    )


_SENSITIVE_DIAGNOSTIC_FIELDS = {
    "apikey",
    "authorization",
    "geminiapikey",
    "openaiapikey",
    "password",
    "refreshtoken",
    "secret",
    "tokenvalue",
    "accesstoken",
}
_DIAGNOSTIC_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
)


def _write_failed_paper_draft(
    *,
    config: AppConfig,
    job_id: str,
    dossier: TechnicalDossier,
    evidence: list[TechnicalEvidence],
    audit: TechnicalAudit,
    errors: list[str],
    traces: list[dict],
    token_usage: TokenUsage,
    attempts: int,
) -> Path:
    """Persist the last invalid draft without copying parsed source documents.

    The payload is deliberately assembled from the bounded model artifacts and
    retrieval traces.  In particular, ``ParsedDocument``/chunks and process
    environment are never serialized.  Evidence snippets remain available for
    debugging the grounding failure, while credential-like fields and strings
    are redacted defensively.
    """

    destination = (
        config.work_dir
        / "technical-failed-drafts"
        / _safe_name(job_id)
        / f"{_safe_name(dossier.paper.paper_id)}.json"
    )
    payload = {
        "schema_version": TECHNICAL_SCHEMA_VERSION,
        "cache_version": _PAPER_RESEARCH_CACHE_VERSION,
        "draft_revision": _FAILED_DRAFT_REVISION,
        "evidence_id_version": EVIDENCE_ID_VERSION,
        "kind": "failed_paper_technical_draft",
        "job_id": job_id,
        "paper_id": dossier.paper.paper_id,
        "attempts": attempts,
        "content_policy": "selected_evidence_snippets_only",
        "dossier": dossier.model_dump(mode="json"),
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "audit": audit.model_dump(mode="json"),
        "errors": errors,
        "retrieval_traces": traces,
        "token_usage": token_usage.model_dump(mode="json"),
    }
    _atomic_json(destination, _sanitize_failed_draft_value(payload))
    return destination.resolve()


def _sanitize_failed_draft_value(value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            sanitized[key] = (
                "[REDACTED]"
                if normalized in _SENSITIVE_DIAGNOSTIC_FIELDS
                else _sanitize_failed_draft_value(item)
            )
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize_failed_draft_value(item) for item in value]
    if isinstance(value, str):
        sanitized_text = value
        for pattern in _DIAGNOSTIC_SECRET_PATTERNS:
            sanitized_text = pattern.sub("[REDACTED]", sanitized_text)
        return sanitized_text
    return value


def _unique_chunks(chunks: list[Chunk]) -> list[Chunk]:
    return list({item.chunk_id: item for item in chunks}.values())


def _unique_evidence(items: list[TechnicalEvidence]) -> list[TechnicalEvidence]:
    return list({item.evidence_id: item for item in items}.values())


def _sum_usage(values: list[TokenUsage]) -> TokenUsage:
    return TokenUsage(
        input_tokens=sum(item.input_tokens for item in values),
        output_tokens=sum(item.output_tokens for item in values),
        total_tokens=sum(item.total_tokens for item in values),
    )


def _failure_status_for_exception(exc: BaseException) -> str:
    if isinstance(exc, ProviderError):
        return "provider_error"
    if isinstance(exc, (IngestionError, FileNotFoundError)):
        return "failed_ingestion"
    return "failed_quality"


def _merge_usage_dicts(left: dict, right: dict) -> dict:
    return {
        key: int(left.get(key, 0) or 0) + int(right.get(key, 0) or 0)
        for key in ("input_tokens", "output_tokens", "total_tokens")
    }


def _analysis_evidence_ids(analysis: object) -> list[str]:
    """Collect primary and contextual references from the nested PaperAnalysis."""

    result: list[str] = []
    for section_name in ("technical_overview", "scope", "limitations"):
        section = getattr(analysis, section_name)
        for field_name in type(section).model_fields:
            values = getattr(section, field_name)
            if not isinstance(values, list):
                continue
            for value in values:
                result.extend(getattr(value, "evidence_ids", []))
                result.extend(getattr(value, "context_evidence_ids", []))
    return result


def _comparison_evidence(
    dossiers: list[TechnicalDossier], evidence: list[TechnicalEvidence]
) -> list[TechnicalEvidence]:
    """Send only dossier-consumed evidence to the cross-paper model.

    Retrieval may collect dozens of 800-token chunks per paper.  Re-sending all
    of them at comparison time adds no grounded capability—the comparison is
    contractually limited to already extracted dossier facts—and can exceed a
    provider context window.  The full registry remains in graph state/output.
    """

    required = {value for dossier in dossiers for value in dossier.evidence_ids}
    return [
        item
        for item in evidence
        if item.source_kind == "paper" and item.evidence_id in required
    ]


def _stage_visual_artifacts(
    evidence: list[TechnicalEvidence],
    *,
    staging: Path,
    published_base: Path,
    work_dir: Path,
    previous_base: Path,
) -> tuple[list[TechnicalEvidence], list[TechnicalArtifactRef], list[str]]:
    """Copy cited Vision crops into the immutable job generation.

    Retrieval evidence only carries the crop digest.  Resolve that digest from
    the controlled Vision cache (or the prior coherent generation), then make
    the final locator point to a hash-addressed ``visual_crop`` ArtifactRef.
    """

    updated: list[TechnicalEvidence] = []
    refs: dict[str, TechnicalArtifactRef] = {}
    errors: list[str] = []
    source_cache: dict[tuple[str, str], Path | None] = {}
    for item in evidence:
        if item.extraction_method != "vision":
            updated.append(item)
            continue
        crop_sha = item.locator.crop_sha256
        if not crop_sha or not re.fullmatch(r"[0-9a-f]{64}", crop_sha):
            errors.append(f"{item.evidence_id}: Vision crop SHA-256이 없습니다.")
            updated.append(item)
            continue
        artifact_id = f"visual_crop-{crop_sha[:16]}"
        if artifact_id not in refs:
            cache_key = (item.locator.document_sha256, crop_sha)
            source = source_cache.get(cache_key)
            if cache_key not in source_cache:
                candidates = [
                    work_dir / "vision-cache" / item.locator.document_sha256 / "crops",
                    previous_base / "visuals",
                ]
                source = _find_file_by_sha256(candidates, crop_sha)
                source_cache[cache_key] = source
            if source is None:
                errors.append(
                    f"{item.evidence_id}: SHA-256과 일치하는 Vision crop 파일을 찾지 못했습니다."
                )
                updated.append(item)
                continue
            suffix = (
                source.suffix.lower()
                if source.suffix.lower() in {".png", ".jpg", ".jpeg"}
                else ".bin"
            )
            relative = Path("visuals") / f"{artifact_id}{suffix}"
            target = staging / relative
            raw = source.read_bytes()
            if hashlib.sha256(raw).hexdigest() != crop_sha:
                errors.append(
                    f"{item.evidence_id}: Vision crop 파일 해시가 변경되었습니다."
                )
                updated.append(item)
                continue
            atomic_write(target, raw)
            refs[artifact_id] = TechnicalArtifactRef(
                artifact_id=artifact_id,
                type="visual_crop",
                path=str((published_base / relative).resolve()),
                sha256=crop_sha,
                producer="visual_enrichment",
            )
        updated.append(
            item.model_copy(
                update={
                    "locator": item.locator.model_copy(
                        update={"visual_artifact_id": artifact_id}
                    )
                }
            )
        )
    return updated, list(refs.values()), errors


def _find_file_by_sha256(directories: list[Path], expected: str) -> Path | None:
    for directory in directories:
        if not directory.is_dir():
            continue
        for candidate in sorted(path for path in directory.iterdir() if path.is_file()):
            if _sha256_file(candidate) == expected:
                return candidate
    return None


def _publish_staged_directory(staging: Path, destination: Path) -> None:
    """Publish one coherent job generation without mixing stale artifacts."""

    job_dir = destination.parent
    job_dir.mkdir(parents=True, exist_ok=True)
    backup = job_dir / f".technical.{uuid.uuid4().hex}.previous"
    lock_path = job_dir / ".technical.publish.lock"
    with lock_path.open("a+b") as lock_handle:
        try:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        except ImportError:  # pragma: no cover - supported deployment is Linux
            pass
        moved_previous = False
        try:
            if destination.exists():
                destination.replace(backup)
                moved_previous = True
            staging.replace(destination)
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
            # A process killed after a successful rename can leave only obsolete
            # hidden generations.  Clean them while holding the publish lock so
            # another publisher never loses its rollback directory.
            for stale in job_dir.glob(".technical.*.previous"):
                if stale != destination and stale.is_dir():
                    shutil.rmtree(stale, ignore_errors=True)
        except Exception:
            if moved_previous and backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
        finally:
            try:
                import fcntl

                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            except ImportError:  # pragma: no cover
                pass


def publish_technical_failure_envelope(
    output_dir: Path, job_id: str, envelope: TechnicalResearchEnvelope
) -> Path:
    """Atomically replace any prior job generation with one runtime failure."""

    job_dir = output_dir / job_id
    destination = job_dir / "technical"
    staging = job_dir / f".technical.{uuid.uuid4().hex}.staging"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        _atomic_json(staging / "failure.json", envelope.model_dump(mode="json"))
        _publish_staged_directory(staging, destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return (destination / "failure.json").resolve()


def _write_artifact(
    path: Path,
    model,
    artifact_type: str,
    producer: str,
    *,
    published_path: Path | None = None,
) -> TechnicalArtifactRef:
    payload = model.model_dump(mode="json")
    return _write_json_artifact(
        path,
        payload,
        artifact_type,
        producer,
        published_path=published_path,
    )


def _write_json_artifact(
    path: Path,
    payload: object,
    artifact_type: str,
    producer: str,
    *,
    published_path: Path | None = None,
) -> TechnicalArtifactRef:
    serialized = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return TechnicalArtifactRef(
        artifact_id=f"{artifact_type}-{digest[:16]}",
        type=artifact_type,
        path=str((published_path or path).resolve()),
        sha256=digest,
        producer=producer,
    )


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _peak_rss_bytes() -> int:
    """Return the process high-water RSS in bytes on the supported Linux runtime."""

    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", value)[:128]


def paper_id_for_path(path: Path) -> str:
    """Return the stable paper ID shared by research and retrieval benchmarks.

    The source hash suffix prevents same-named files from sharing an index while
    keeping the human-readable filename in dossier and trace identifiers.
    """

    stem = _safe_name(path.stem).strip(".-") or "paper"
    return f"{stem}-{_sha256_file(path)[:8]}"


def common_id_for_path(path: Path) -> str:
    stem = _safe_name(path.stem).strip(".-") or "document"
    return f"common-{stem}-{_sha256_file(path)[:8]}"
