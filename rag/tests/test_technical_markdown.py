from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from paper_review_agent.schemas import (
    GroundedClaim,
    LimitationsAnalysis,
    PaperAnalysis,
    PaperMetadata,
    ScopeAnalysis,
    TechnicalOverview,
    utc_now,
)
from paper_review_agent.technical_markdown import export_technical_markdown
from paper_review_agent.technical_schemas import (
    CriticalClaimItem,
    EvidenceLocator,
    TechnicalClaim,
    TechnicalComparison,
    TechnicalDossier,
    TechnicalEvidence,
    TechnicalQuality,
    TechnicalResearchEnvelope,
    TechnicalRunMetadata,
)


def _write_fixture(root: Path, *, recorded_evidence_path: str | None = None) -> Path:
    evidence_id = "paper:paper-a@" + "a" * 12 + ":p0001:text-01:span-00000-00006"
    snippet = "result"
    evidence = TechnicalEvidence(
        evidence_id=evidence_id,
        source_kind="paper",
        document_id="paper-a",
        content_kind="text",
        snippet=snippet,
        content_hash=hashlib.sha256(snippet.encode()).hexdigest(),
        locator=EvidenceLocator(
            document_sha256="a" * 64,
            physical_page=1,
            element_id="text-01",
            source_chunk_id="chunk-1",
        ),
    )
    grounded = GroundedClaim(
        text="검증된 기술 설명",
        claim_type="author_claim",
        evidence_ids=[evidence_id],
        confidence=0.9,
    )
    dossier = TechnicalDossier(
        paper=PaperMetadata(
            paper_id="paper-a",
            title="Example Paper",
            source_path="inputs/paper-a.pdf",
            source_hash="a" * 64,
            page_count=1,
        ),
        analysis=PaperAnalysis(
            technical_overview=TechnicalOverview(
                problem_definition=[grounded],
                core_approach=[grounded],
                experimental_results=[grounded],
            ),
            scope=ScopeAnalysis(target_tasks=[grounded]),
            limitations=LimitationsAnalysis(author_stated=[grounded]),
        ),
        claims=[
            TechnicalClaim(
                claim_id="paper-a::technical_overview::c1",
                text="검증된 기술 설명",
                claim_type="author_claim",
                evidence_ids=[evidence_id],
                confidence=0.9,
                critical=True,
            )
        ],
        critical_inventory=[
            CriticalClaimItem(
                inventory_id="paper-a::technical_overview::i1",
                category="contribution",
                summary="핵심 기여",
                disposition="extracted",
                claim_ids=["paper-a::technical_overview::c1"],
                evidence_ids=[evidence_id],
            )
        ],
        evidence_ids=[evidence_id],
    )
    evidence_path = root / "evidence_registry.json"
    evidence_path.write_text(
        json.dumps([evidence.model_dump(mode="json")]), encoding="utf-8"
    )
    envelope = TechnicalResearchEnvelope(
        status="succeeded",
        run=TechnicalRunMetadata(
            job_id="markdown-test",
            openai_model="test-model",
            embedding_provider="bge-m3",
            embedding_model="BAAI/bge-m3",
            started_at=utc_now(),
            finished_at=utc_now(),
        ),
        dossiers=[dossier],
        comparison=TechnicalComparison(),
        evidence_registry_path=recorded_evidence_path or str(evidence_path),
        quality=TechnicalQuality(
            evidence_resolution_rate=1.0,
            locator_resolution_rate=1.0,
            critical_inventory_coverage=1.0,
        ),
    )
    run_path = root / "run.json"
    run_path.write_text(envelope.model_dump_json(), encoding="utf-8")
    return run_path


def test_export_technical_markdown(tmp_path: Path):
    run_path = _write_fixture(tmp_path)

    written = export_technical_markdown(run_path, tmp_path / "markdown")

    assert {path.relative_to(tmp_path).as_posix() for path in written} == {
        "markdown/README.md",
        "markdown/comparison.md",
        "markdown/evidence_registry.md",
        "markdown/dossiers/paper-a.md",
    }
    overview = (tmp_path / "markdown" / "README.md").read_text(encoding="utf-8")
    dossier = (tmp_path / "markdown" / "dossiers" / "paper-a.md").read_text(
        encoding="utf-8"
    )
    evidence = (tmp_path / "markdown" / "evidence_registry.md").read_text(
        encoding="utf-8"
    )
    assert "# 기술조사 결과 검토본" in overview
    assert "## 기술 개요" in dossier
    assert "../evidence_registry.md#ev-001" in dossier
    assert '<a id="ev-001"></a>' in evidence


def test_export_uses_sibling_registry_when_recorded_path_is_stale(tmp_path: Path):
    run_path = _write_fixture(
        tmp_path, recorded_evidence_path="/missing/evidence_registry.json"
    )

    written = export_technical_markdown(run_path)

    assert tmp_path / "markdown" / "evidence_registry.md" in written


@pytest.mark.parametrize(
    ("value_fields", "unit", "expected_value"),
    [
        ({"value": "350"}, "ns", "350"),
        ({"value": "2690"}, "ms", "2690"),
        ({"value": "82"}, "%", "82"),
        ({"value": "0"}, "ms", "0"),
        ({"value_min": 10, "value_max": 20}, "GB/s", "10–20"),
        ({"value_min": 10}, "GB", "≥ 10"),
        ({"value_max": 20}, "ms", "≤ 20"),
        ({"value": "1.5x"}, None, "1.5x"),
    ],
)
def test_export_preserves_observation_values_and_units(
    tmp_path: Path, value_fields: dict, unit: str | None, expected_value: str
):
    run_path = _write_fixture(tmp_path)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["dossiers"][0]["experiment_observations"] = [{
        "observation_id": "observation-1",
        "metric": "sample metric",
        **value_fields,
        "unit": unit,
        "evaluation_mode": "measured",
        "evidence_ids": run["dossiers"][0]["evidence_ids"],
        "confidence": 0.9,
    }]
    run_path.write_text(json.dumps(run), encoding="utf-8")
    source_before = run_path.read_bytes()

    export_technical_markdown(run_path)

    dossier = (tmp_path / "markdown/dossiers/paper-a.md").read_text(encoding="utf-8")
    assert "| 값 | 단위 | Baseline |" in dossier
    row = next(line for line in dossier.splitlines() if line.startswith("| `observation-1` |"))
    cells = [cell.strip() for cell in row.split("|")[1:-1]]
    assert cells[2:4] == [expected_value, unit or "-"]
    assert run_path.read_bytes() == source_before
