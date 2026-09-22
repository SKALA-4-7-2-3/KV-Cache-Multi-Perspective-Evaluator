from __future__ import annotations

import hashlib

from paper_review_agent.dossier_expectations import (
    DossierExpectationFile,
    validate_dossier_expectations,
)
from paper_review_agent.schemas import (
    LimitationsAnalysis,
    PaperAnalysis,
    PaperMetadata,
    ScopeAnalysis,
    TechnicalOverview,
    utc_now,
)
from paper_review_agent.technical_schemas import (
    CriticalClaimItem,
    ExperimentObservation,
    TechnicalClaim,
    TechnicalComparison,
    TechnicalDossier,
    TechnicalQuality,
    TechnicalResearchEnvelope,
    TechnicalRunMetadata,
    UnverifiedItem,
)


def _envelope(dossier: TechnicalDossier) -> TechnicalResearchEnvelope:
    # The expectation harness only consumes dossiers.  A second minimal paper
    # keeps the enclosing success contract realistic without affecting selection.
    other = _dossier("other-paper", claim_text="unrelated")
    return TechnicalResearchEnvelope(
        status="succeeded",
        run=TechnicalRunMetadata(
            job_id="expectation-test",
            openai_model="test",
            embedding_provider="bge-m3",
            embedding_model="BAAI/bge-m3",
            index_profile="profile",
            started_at=utc_now(),
            finished_at=utc_now(),
        ),
        dossiers=[dossier, other],
        comparison=TechnicalComparison(),
        evidence_registry_path="evidence_registry.json",
        quality=TechnicalQuality(
            evidence_resolution_rate=1.0,
            locator_resolution_rate=1.0,
            critical_inventory_coverage=1.0,
            unsupported_numeric_claims=0,
        ),
    )


def _dossier(
    paper_id: str = "2607.27187-deadbeef",
    *,
    claim_text: str = "LLaMA-8B 1×A100 host memory 3.3×–27.5×",
    evidence_id: str = "paper:evidence-only-marker",
) -> TechnicalDossier:
    source_hash = hashlib.sha256(paper_id.encode()).hexdigest()
    return TechnicalDossier(
        paper=PaperMetadata(
            paper_id=paper_id,
            title="Fixture Paper",
            source_path=f"/tmp/{paper_id}.pdf",
            source_hash=source_hash,
            page_count=1,
        ),
        analysis=PaperAnalysis(
            technical_overview=TechnicalOverview(),
            scope=ScopeAnalysis(),
            limitations=LimitationsAnalysis(),
        ),
        claims=[
            TechnicalClaim(
                claim_id="claim-1",
                text=claim_text,
                claim_type="observed_result",
                evidence_ids=[evidence_id],
                confidence=1.0,
            )
        ],
        critical_inventory=[
            CriticalClaimItem(
                inventory_id="inventory-1",
                category="result",
                summary="query-only-marker",
                disposition="unverified",
                reason="not recovered",
                searched_queries=["query-only-marker evidence-only-marker"],
            )
        ],
        experiment_observations=[
            ExperimentObservation(
                observation_id="observation-1",
                metric="host-memory speedup",
                value="3.3×–27.5×",
                model="LLaMA-8B",
                hardware="1×A100",
                evaluation_mode="measured",
                evidence_ids=[evidence_id],
                confidence=1.0,
            )
        ],
        unverified_items=[
            UnverifiedItem(
                item_id="unverified-1",
                topic="unverified-topic-marker",
                reason="not found",
                searched_queries=["unverified-topic-marker"],
                attempts=1,
            )
        ],
    )


def _expectations(*checks: dict) -> DossierExpectationFile:
    return DossierExpectationFile.model_validate(
        {
            "schema_version": "1.0.0",
            "papers": [
                {
                    "selector": {"paper_id_regex": "^2607\\.27187"},
                    "expectations": list(checks),
                }
            ],
        }
    )


def test_matches_all_patterns_within_one_semantic_record() -> None:
    report = validate_dossier_expectations(
        _envelope(_dossier()),
        _expectations(
            {
                "expectation_id": "table-row",
                "description": "one complete Table I row",
                "all_of": [
                    "LLaMA-8B",
                    "1\\s*[x×]\\s*A100",
                    "3[.]3\\s*[x×].*27[.]5\\s*[x×]",
                ],
            }
        ),
    )

    assert report.valid
    assert report.passed_count == 1
    assert "LLaMA-8B" in (report.checks[0].matched_record or "")


def test_does_not_match_evidence_ids_queries_or_unverified_inventory_by_default() -> None:
    report = validate_dossier_expectations(
        _envelope(_dossier()),
        _expectations(
            {
                "expectation_id": "not-semantic",
                "description": "must not pass from metadata or queries",
                "all_of": ["evidence-only-marker|query-only-marker"],
            }
        ),
    )

    assert not report.valid
    assert report.passed_count == 0


def test_unverified_items_require_explicit_scope() -> None:
    report = validate_dossier_expectations(
        _envelope(_dossier()),
        _expectations(
            {
                "expectation_id": "explicit-gap",
                "description": "explicitly expected gap",
                "scopes": ["unverified_items"],
                "all_of": ["unverified-topic-marker", "not found"],
            }
        ),
    )

    assert report.valid


def test_record_mode_rejects_patterns_split_across_claims() -> None:
    dossier = _dossier(claim_text="value alpha")
    dossier.claims.append(
        TechnicalClaim(
            claim_id="claim-2",
            text="value beta",
            claim_type="observed_result",
            evidence_ids=["paper:fixture:2"],
            confidence=1.0,
        )
    )
    base = {
        "expectation_id": "co-location",
        "description": "values must co-occur",
        "scopes": ["claims"],
        "all_of": ["alpha", "beta"],
    }

    record_report = validate_dossier_expectations(
        _envelope(dossier), _expectations(base)
    )
    dossier_report = validate_dossier_expectations(
        _envelope(dossier),
        _expectations({**base, "match_within": "dossier"}),
    )

    assert not record_report.valid
    assert dossier_report.valid


def test_selector_must_match_exactly_one_dossier() -> None:
    expectations = DossierExpectationFile.model_validate(
        {
            "papers": [
                {
                    "selector": {"title_regex": "Fixture"},
                    "expectations": [
                        {
                            "expectation_id": "ambiguous",
                            "description": "ambiguous selector",
                            "all_of": ["anything"],
                        }
                    ],
                }
            ]
        }
    )

    report = validate_dossier_expectations(_envelope(_dossier()), expectations)

    assert not report.valid
    assert "2개와 일치" in report.errors[0]
