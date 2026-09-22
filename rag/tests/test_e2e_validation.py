from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from paper_review_agent.e2e_validation import (
    E2EValidationArtifactError,
    create_retrieval_e2e_validation_artifact,
)
from paper_review_agent.schemas import (
    LimitationsAnalysis,
    PaperAnalysis,
    PaperMetadata,
    ScopeAnalysis,
    TechnicalOverview,
    ValidationReport,
    utc_now,
)
from paper_review_agent.technical_schemas import (
    CriticalClaimItem,
    RetrievalE2EValidationArtifact,
    TechnicalComparison,
    TechnicalClaim,
    TechnicalDossier,
    TechnicalQuality,
    TechnicalResearchEnvelope,
    TechnicalRunMetadata,
)


def _dossier(paper_id: str, source: Path) -> TechnicalDossier:
    return TechnicalDossier(
        paper=PaperMetadata(
            paper_id=paper_id,
            title=paper_id,
            source_path=str(source),
            source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
            page_count=1,
        ),
        analysis=PaperAnalysis(
            technical_overview=TechnicalOverview(),
            scope=ScopeAnalysis(),
            limitations=LimitationsAnalysis(),
        ),
        critical_inventory=[
            CriticalClaimItem(
                inventory_id=f"inventory-{paper_id}",
                category="scope",
                summary="fixture",
                disposition="unverified",
                reason="fixture",
                searched_queries=["fixture"],
            )
        ],
        claims=[
            TechnicalClaim(
                claim_id=f"claim-{paper_id}",
                text=f"semantic fixture for {paper_id}",
                claim_type="author_claim",
                evidence_ids=[f"paper:{paper_id}:fixture"],
                confidence=1.0,
            )
        ],
    )


def _run_file(tmp_path: Path, *, inventory_coverage: float = 1.0) -> Path:
    sources = [tmp_path / "paper-a.txt", tmp_path / "paper-b.txt"]
    for index, source in enumerate(sources):
        source.write_text(f"paper {index}", encoding="utf-8")
    envelope = TechnicalResearchEnvelope(
        status="succeeded",
        run=TechnicalRunMetadata(
            job_id="e2e-job",
            openai_model="test-openai",
            embedding_provider="bge-m3",
            embedding_model="BAAI/bge-m3",
            embedding_revision="5" * 40,
            index_profile="bge-profile-test",
            started_at=utc_now(),
            finished_at=utc_now(),
        ),
        dossiers=[
            _dossier("paper-a", sources[0]),
            _dossier("paper-b", sources[1]),
        ],
        comparison=TechnicalComparison(),
        evidence_registry_path="evidence_registry.json",
        quality=TechnicalQuality(
            evidence_resolution_rate=1.0,
            locator_resolution_rate=1.0,
            critical_inventory_coverage=inventory_coverage,
            unsupported_numeric_claims=0,
        ),
    )
    run_path = tmp_path / "run.json"
    run_path.write_text(envelope.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return run_path


def test_creates_hash_bound_artifact_atomically_from_valid_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    golden = tmp_path / "retrieval.jsonl"
    golden.write_text('{"case_id":"case"}\n', encoding="utf-8")
    run_path = _run_file(tmp_path)
    monkeypatch.setattr(
        "paper_review_agent.e2e_validation.validate_technical_research",
        lambda path: ValidationReport(valid=True, schema_version="1.0.0"),
    )
    expectations = tmp_path / "dossier-expectations.json"
    expectations.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "papers": [
                    {
                        "selector": {"paper_id_regex": "^paper-a$"},
                        "expectations": [
                            {
                                "expectation_id": "paper-a.fixture",
                                "description": "paper a semantic fixture",
                                "all_of": ["semantic fixture for paper-a"],
                            }
                        ],
                    },
                    {
                        "selector": {"paper_id_regex": "^paper-b$"},
                        "expectations": [
                            {
                                "expectation_id": "paper-b.fixture",
                                "description": "paper b semantic fixture",
                                "all_of": ["semantic fixture for paper-b"],
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    artifact = create_retrieval_e2e_validation_artifact(
        golden,
        run_path,
        peak_rss_bytes=3 * 1024**3,
        completed_without_oom=True,
        expected_index_profile="bge-profile-test",
        expected_paper_ids=["paper-b", "paper-a"],
        dossier_expectations_path=expectations,
    )

    output = golden.with_suffix(".e2e.json")
    stored = RetrievalE2EValidationArtifact.model_validate_json(output.read_bytes())
    assert stored == artifact
    assert artifact.golden_sha256 == hashlib.sha256(golden.read_bytes()).hexdigest()
    assert artifact.technical_run_sha256 == hashlib.sha256(run_path.read_bytes()).hexdigest()
    assert artifact.successful_paper_ids == ["paper-a", "paper-b"]
    assert artifact.dossier_expectations_sha256 == hashlib.sha256(
        expectations.read_bytes()
    ).hexdigest()
    assert artifact.dossier_expectations_path == str(expectations.resolve())
    assert artifact.dossier_expectation_count == 2
    assert not list(tmp_path.glob("*.tmp"))


def test_rejects_run_that_fails_full_contract_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    golden = tmp_path / "retrieval.jsonl"
    golden.write_text("{}\n", encoding="utf-8")
    run_path = _run_file(tmp_path)
    monkeypatch.setattr(
        "paper_review_agent.e2e_validation.validate_technical_research",
        lambda path: ValidationReport(valid=False, errors=["artifact hash mismatch"]),
    )

    with pytest.raises(E2EValidationArtifactError, match="artifact hash mismatch"):
        create_retrieval_e2e_validation_artifact(
            golden,
            run_path,
            peak_rss_bytes=1,
            completed_without_oom=True,
        )


def test_requires_measured_memory_for_legacy_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    golden = tmp_path / "retrieval.jsonl"
    golden.write_text("{}\n", encoding="utf-8")
    run_path = _run_file(tmp_path)
    monkeypatch.setattr(
        "paper_review_agent.e2e_validation.validate_technical_research",
        lambda path: ValidationReport(valid=True),
    )

    with pytest.raises(E2EValidationArtifactError, match="peak_rss_bytes"):
        create_retrieval_e2e_validation_artifact(
            golden,
            run_path,
            completed_without_oom=True,
        )


def test_rejects_quality_summary_below_promotion_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    golden = tmp_path / "retrieval.jsonl"
    golden.write_text("{}\n", encoding="utf-8")
    run_path = _run_file(tmp_path, inventory_coverage=0.5)
    monkeypatch.setattr(
        "paper_review_agent.e2e_validation.validate_technical_research",
        lambda path: ValidationReport(valid=True),
    )

    with pytest.raises(E2EValidationArtifactError, match="critical_inventory_coverage"):
        create_retrieval_e2e_validation_artifact(
            golden,
            run_path,
            peak_rss_bytes=1,
            completed_without_oom=True,
        )
