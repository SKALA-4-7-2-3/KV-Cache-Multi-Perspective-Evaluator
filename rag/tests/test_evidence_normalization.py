from __future__ import annotations

import pytest

from paper_review_agent.evidence_normalization import (
    EvidenceIdNormalizer,
    augment_observation_evaluation_modes,
    augment_precise_numeric_references,
    normalize_evidence_references,
)
from paper_review_agent.schemas import (
    GroundedClaim,
    LimitationsAnalysis,
    PaperAnalysis,
    PaperMetadata,
    ScopeAnalysis,
    TechnicalOverview,
)
from paper_review_agent.technical_schemas import (
    CriticalClaimItem,
    DossierExtraction,
    EvidenceLocator,
    ExperimentObservation,
    TableCellLocator,
    TechnicalClaim,
    TechnicalDossier,
    TechnicalEvidence,
    TextSpan,
)


def _evidence(
    *,
    document_id: str = "paper-a",
    source_kind: str = "paper",
    page: int = 9,
    element_id: str = "elem-paper-a",
    suffix: str = "span-00000-00042",
) -> TechnicalEvidence:
    digest = "a" * 64 if source_kind == "paper" else "b" * 64
    return TechnicalEvidence(
        evidence_id=(
            f"{source_kind}:{document_id}@{digest[:12]}:p{page:04d}:"
            f"{element_id}:{suffix}"
        ),
        source_kind=source_kind,
        document_id=document_id,
        content_kind="text",
        snippet="Directly supported technical evidence.",
        content_hash="c" * 64,
        locator=EvidenceLocator(
            document_sha256=digest,
            physical_page=page,
            element_id=element_id,
        ),
    )


def _claim(primary: str, context: str | None = None) -> GroundedClaim:
    return GroundedClaim(
        text="근거가 있는 주장",
        claim_type="author_claim",
        evidence_ids=[primary],
        context_evidence_ids=[context] if context else [],
        confidence=0.9,
    )


def test_normalizes_all_dossier_reference_fields_from_unique_locator_tails():
    paper = _evidence()
    common = _evidence(
        document_id="common-a",
        source_kind="common",
        page=3,
        element_id="elem-common-a",
    )
    malformed = (
        "paper:paper-aaaaaaaaaaaa:p0009:elem-paper-a:span-00000-00042"
    )
    duplicated = (
        "paper:paper-a@aaaaaaaaaaaa:p0009:elem-"
        "paper:paper-a@aaaaaaaaaaaa:p0009:elem-paper-a:span-00000-00042"
    )
    short_common = "elem-common-a:span-00000-00042"
    analysis = PaperAnalysis(
        technical_overview=TechnicalOverview(
            problem_definition=[_claim(malformed, short_common)],
            core_approach=[_claim(duplicated, malformed)],
            experimental_results=[_claim(malformed)],
        ),
        scope=ScopeAnalysis(),
        limitations=LimitationsAnalysis(author_stated=[_claim(malformed)]),
    )
    dossier = TechnicalDossier(
        paper=PaperMetadata(
            paper_id="paper-a",
            source_path="/paper-a.pdf",
            source_hash="a" * 64,
            page_count=10,
        ),
        analysis=analysis,
        claims=[
            TechnicalClaim(
                claim_id="claim-1",
                text="기술 주장",
                claim_type="author_claim",
                evidence_ids=[malformed],
                context_evidence_ids=[short_common],
                confidence=0.9,
            )
        ],
        critical_inventory=[
            CriticalClaimItem(
                inventory_id="inventory-1",
                category="contribution",
                summary="기여",
                disposition="extracted",
                claim_ids=["claim-1"],
                evidence_ids=[duplicated],
            )
        ],
        experiment_observations=[
            ExperimentObservation(
                observation_id="obs-1",
                metric="latency",
                value="1 ms",
                evaluation_mode="measured",
                evidence_ids=[malformed],
                confidence=0.9,
            )
        ],
        evidence_ids=[malformed, duplicated],
    )

    normalized = normalize_evidence_references(dossier, [paper, common])

    assert normalized.analysis.technical_overview.problem_definition[0].evidence_ids == [
        paper.evidence_id
    ]
    assert normalized.analysis.technical_overview.problem_definition[
        0
    ].context_evidence_ids == [common.evidence_id]
    assert normalized.analysis.technical_overview.core_approach[0].evidence_ids == [
        paper.evidence_id
    ]
    assert (
        normalized.analysis.technical_overview.core_approach[0].context_evidence_ids
        == []
    )
    assert normalized.claims[0].evidence_ids == [paper.evidence_id]
    assert normalized.claims[0].context_evidence_ids == [common.evidence_id]
    assert normalized.critical_inventory[0].evidence_ids == [paper.evidence_id]
    assert normalized.experiment_observations[0].evidence_ids == [
        paper.evidence_id
    ]
    assert normalized.evidence_ids == [paper.evidence_id]


def test_normalizer_preserves_ambiguous_unknown_and_conflicting_page_references():
    left = _evidence(document_id="left", element_id="shared", suffix="whole")
    right = _evidence(document_id="right", element_id="shared", suffix="whole")
    unique = _evidence(document_id="unique", element_id="unique", suffix="whole")
    normalizer = EvidenceIdNormalizer([left, right, unique])

    ambiguous = "p0009:shared:whole"
    unknown = "p0009:not-supplied:whole"
    conflicting_page = "paper:broken:p0010:unique:whole"

    assert normalizer.resolve(ambiguous) == ambiguous
    assert normalizer.resolve(unknown) == unknown
    assert normalizer.resolve(conflicting_page) == conflicting_page
    assert normalizer.resolve(left.evidence_id) == left.evidence_id


def test_normalizer_repairs_unique_parser_element_alias_by_page_and_span():
    evidence = _evidence(
        page=5,
        element_id="elem-paper-a-p0005-text-007-deadbeef",
        suffix="span-00000-00532",
    )
    alias = (
        "paper:paper-a@aaaaaaaaaaaa:p0005:"
        "elem-paper-a-p0005-text-group-007-deadbeef:span-00000-00532"
    )

    assert EvidenceIdNormalizer([evidence]).resolve(alias) == evidence.evidence_id


def test_normalizer_repairs_reverse_parser_element_alias():
    evidence = _evidence(
        page=5,
        element_id="elem-paper-a-p0005-text-group-007-deadbeef",
        suffix="span-00000-00532",
    )
    alias = evidence.evidence_id.replace("text-group-007", "text-007")

    assert EvidenceIdNormalizer([evidence]).resolve(alias) == evidence.evidence_id


@pytest.mark.parametrize(
    "old,new",
    [
        ("paper:paper-a@", "paper:other@"),
        ("@aaaaaaaaaaaa", "@bbbbbbbbbbbb"),
        (":p0005:", ":p0006:"),
        ("text-group-007", "text-group-008"),
        ("deadbeef", "cafebabe"),
        ("span-00000-00532", "span-00000-00533"),
        ("text-group-007", "table-007"),
    ],
)
def test_normalizer_rejects_parser_alias_with_conflicting_identity(old, new):
    evidence = _evidence(
        page=5,
        element_id="elem-paper-a-p0005-text-007-deadbeef",
        suffix="span-00000-00532",
    )
    alias = evidence.evidence_id.replace("text-007", "text-group-007")
    reference = alias.replace(old, new)

    assert EvidenceIdNormalizer([evidence]).resolve(reference) == reference


@pytest.mark.parametrize("suffix", ["whole", "cell-r01-c01", "rows-r01-r02"])
def test_normalizer_does_not_alias_non_span_evidence(suffix):
    evidence = _evidence(
        page=5,
        element_id="elem-paper-a-p0005-text-007-deadbeef",
        suffix=suffix,
    )
    alias = evidence.evidence_id.replace("text-007", "text-group-007")

    assert EvidenceIdNormalizer([evidence]).resolve(alias) == alias


def test_normalizer_does_not_rebind_unknown_whole_to_unique_page_evidence():
    evidence = _evidence(page=5, element_id="table-01", suffix="whole")
    reference = "paper:other@bbbbbbbbbbbb:p0005:table-02:whole"

    assert EvidenceIdNormalizer([evidence]).resolve(reference) == reference


def test_normalizer_does_not_repair_ambiguous_page_and_span_alias():
    first = _evidence(
        document_id="first",
        page=5,
        element_id="elem-first-text-007",
        suffix="span-00000-00532",
    )
    second = _evidence(
        document_id="second",
        page=5,
        element_id="elem-second-text-007",
        suffix="span-00000-00532",
    )
    alias = "paper:unknown:p0005:elem-alias:span-00000-00532"

    assert EvidenceIdNormalizer([first, second]).resolve(alias) == alias


def test_extraction_normalization_covers_analysis_claims_inventory_and_observations():
    evidence = _evidence()
    bad = "p0009:elem-paper-a:span-00000-00042"
    extraction = DossierExtraction(
        analysis=PaperAnalysis(
            technical_overview=TechnicalOverview(
                problem_definition=[_claim(bad)],
                core_approach=[_claim(bad)],
                experimental_results=[_claim(bad)],
            ),
            scope=ScopeAnalysis(),
            limitations=LimitationsAnalysis(author_stated=[_claim(bad)]),
        ),
        claims=[
            TechnicalClaim(
                claim_id="claim-1",
                text="기술 주장",
                claim_type="author_claim",
                evidence_ids=[bad],
                confidence=0.9,
            )
        ],
        critical_inventory=[
            CriticalClaimItem(
                inventory_id="inventory-1",
                category="contribution",
                summary="기여",
                disposition="extracted",
                claim_ids=["claim-1"],
                evidence_ids=[bad],
            )
        ],
        experiment_observations=[
            ExperimentObservation(
                observation_id="obs-1",
                metric="latency",
                value="1 ms",
                evaluation_mode="measured",
                evidence_ids=[bad],
                confidence=0.9,
            )
        ],
    )

    normalized = normalize_evidence_references(extraction, [evidence])

    assert normalized.analysis.technical_overview.problem_definition[0].evidence_ids == [
        evidence.evidence_id
    ]
    assert normalized.claims[0].evidence_ids == [evidence.evidence_id]
    assert normalized.critical_inventory[0].evidence_ids == [evidence.evidence_id]
    assert normalized.experiment_observations[0].evidence_ids == [
        evidence.evidence_id
    ]


def test_unique_exact_table_cell_is_added_for_numeric_parent_reference():
    aggregate = _evidence(element_id="table-01", suffix="whole").model_copy(
        update={
            "content_kind": "table",
            "snippet": "At 128K the measured speedup is 4.5×.",
        }
    )
    cell = aggregate.model_copy(
        update={
            "evidence_id": aggregate.evidence_id.removesuffix("whole")
            + "cell-r001-c001",
            "snippet": "row_header=128K; column_header=Speedup; value=4.5×",
            "locator": aggregate.locator.model_copy(
                update={
                    "table_cells": [
                        TableCellLocator(
                            row_index=1,
                            column_index=1,
                            raw_text="4.5×",
                            row_header="128K",
                            column_header="Speedup",
                        )
                    ]
                }
            ),
        }
    )
    claim = TechnicalClaim(
        claim_id="claim-1",
        text="128K에서 4.5× speedup을 측정했다.",
        claim_type="observed_result",
        evidence_ids=[aggregate.evidence_id],
        confidence=0.9,
    )

    normalized = augment_precise_numeric_references(claim, [aggregate, cell])

    assert normalized.evidence_ids == [aggregate.evidence_id, cell.evidence_id]


def test_numeric_augmentation_treats_space_and_comma_thousands_as_equal():
    aggregate = _evidence(element_id="table-12", suffix="whole").model_copy(
        update={
            "content_kind": "table",
            "snippet": "FullKV prefill (FA2) | 28 843 | baseline",
        }
    )
    cell = aggregate.model_copy(
        update={
            "evidence_id": aggregate.evidence_id.removesuffix("whole")
            + "cell-r01-c01",
            "snippet": (
                "row_header=FullKV prefill (FA2); column_header=Time (ms); "
                "value=28 843"
            ),
            "locator": aggregate.locator.model_copy(
                update={
                    "table_cells": [
                        TableCellLocator(
                            row_index=1,
                            column_index=1,
                            raw_text="28 843",
                            row_header="FullKV prefill (FA2)",
                            column_header="Time (ms)",
                        )
                    ]
                }
            ),
        }
    )
    claim = TechnicalClaim(
        claim_id="claim-thousands-separator",
        text="FullKV prefill (FA2)는 28,843 ms이다.",
        claim_type="observed_result",
        evidence_ids=[aggregate.evidence_id],
        confidence=0.9,
    )

    normalized = augment_precise_numeric_references(claim, [aggregate, cell])

    assert normalized.evidence_ids == [aggregate.evidence_id, cell.evidence_id]


def test_numeric_augmentation_uses_unique_lexical_narrative_fallback():
    aggregate = _evidence(element_id="figure-05", suffix="whole").model_copy(
        update={
            "snippet": "The aggregate evaluation summary contains a 256K result.",
            "locator": _evidence().locator.model_copy(
                update={
                    "element_id": "figure-05",
                    "text_span": None,
                }
            ),
        }
    )
    narrative = _evidence(
        page=10,
        element_id="paragraph-conclusion",
        suffix="span-00000-00080",
    ).model_copy(
        update={
            "snippet": "The study evaluates five open-source models in total.",
            "locator": _evidence(
                page=10,
                element_id="paragraph-conclusion",
                suffix="span-00000-00080",
            ).locator.model_copy(
                update={"text_span": TextSpan(start=0, end=53)}
            ),
        }
    )
    decoy = _evidence(
        page=11,
        element_id="paragraph-budgets",
        suffix="span-00000-00060",
    ).model_copy(
        update={
            "snippet": "The appendix defines five cache budgets for evaluation.",
            "locator": _evidence(
                page=11,
                element_id="paragraph-budgets",
                suffix="span-00000-00060",
            ).locator.model_copy(
                update={"text_span": TextSpan(start=0, end=54)}
            ),
        }
    )
    claim = TechnicalClaim(
        claim_id="claim-five-models",
        text="The evaluation covers 5 open-source models across workloads.",
        claim_type="observed_result",
        evidence_ids=[aggregate.evidence_id],
        confidence=0.9,
    )

    normalized = augment_precise_numeric_references(
        claim, [aggregate, narrative, decoy]
    )

    assert normalized.evidence_ids == [aggregate.evidence_id, narrative.evidence_id]


def test_numeric_augmentation_breaks_lexical_tie_by_cited_page_proximity():
    cited = _evidence(page=9, element_id="memory-text", suffix="whole").model_copy(
        update={"snippet": "RDKV reports a 1.9× memory reduction at 128K."}
    )
    same_page = _evidence(
        page=9,
        element_id="figure-5-caption",
        suffix="span-00000-00080",
    ).model_copy(
        update={
            "snippet": (
                "Figure 5 evaluates RDKV and FullKV on one A100 64 GB at 128K."
            ),
            "locator": _evidence(
                page=9,
                element_id="figure-5-caption",
                suffix="span-00000-00080",
            ).locator.model_copy(update={"text_span": TextSpan(start=0, end=68)}),
        }
    )
    far_page = _evidence(
        page=21,
        element_id="appendix-overhead",
        suffix="span-00000-00080",
    ).model_copy(
        update={
            "snippet": (
                "The appendix evaluates RDKV and FullKV on one A100 64 GB at 128K."
            ),
            "locator": _evidence(
                page=21,
                element_id="appendix-overhead",
                suffix="span-00000-00080",
            ).locator.model_copy(update={"text_span": TextSpan(start=0, end=70)}),
        }
    )
    claim = TechnicalClaim(
        claim_id="claim-memory",
        text="RDKV와 FullKV를 단일 A100 64 GB, 128K에서 비교했다.",
        claim_type="observed_result",
        evidence_ids=[cited.evidence_id],
        confidence=0.9,
    )

    normalized = augment_precise_numeric_references(
        claim, [cited, same_page, far_page]
    )

    assert normalized.evidence_ids == [cited.evidence_id, same_page.evidence_id]


def test_table_result_claim_adds_named_model_and_platform_cells_from_same_row():
    base = _evidence(element_id="table-01", suffix="whole").model_copy(
        update={"content_kind": "table", "snippet": "Table I benchmark matrix"}
    )

    def cell(column: int, raw: str, header: str) -> TechnicalEvidence:
        return base.model_copy(
            update={
                "evidence_id": base.evidence_id.removesuffix("whole")
                + f"cell-r002-c{column:03d}",
                "snippet": (
                    f"Table I; row=2; column={column}; "
                    f"column_header={header}; value={raw}"
                ),
                "locator": base.locator.model_copy(
                    update={
                        "table_cells": [
                            TableCellLocator(
                                row_index=2,
                                column_index=column,
                                raw_text=raw,
                                row_header="LLaMA-8B",
                                column_header=header,
                            )
                        ]
                    }
                ),
            }
        )

    model = cell(0, "LLaMA-8B", "Model")
    platform = cell(1, "1×H100", "Platform")
    result = cell(2, "1.9×-11.8×", "Host Memory")
    other_row = result.model_copy(
        update={
            "evidence_id": result.evidence_id.replace("r002", "r003"),
            "snippet": result.snippet.replace("row=2", "row=3").replace(
                "1.9×-11.8×", "1.5×-17.2×"
            ),
            "locator": result.locator.model_copy(
                update={
                    "table_cells": [
                        result.locator.table_cells[0].model_copy(
                            update={"row_index": 3, "raw_text": "1.5×-17.2×"}
                        )
                    ]
                }
            ),
        }
    )
    claim = TechnicalClaim(
        claim_id="claim-table-row",
        text=(
            "Table I에서 LLaMA-8B/1×H100 Host Memory speedup은 "
            "1.9×-11.8×이다."
        ),
        claim_type="observed_result",
        evidence_ids=[result.evidence_id],
        confidence=0.9,
    )

    normalized = augment_precise_numeric_references(
        claim, [base, model, platform, result, other_row]
    )

    assert normalized.evidence_ids == [
        result.evidence_id,
        model.evidence_id,
        platform.evidence_id,
    ]
    assert other_row.evidence_id not in normalized.evidence_ids

    observation = ExperimentObservation(
        observation_id="obs-table-row",
        metric="Host Memory speedup",
        value="1.9×-11.8×",
        model="LLaMA-8B",
        hardware="1×H100",
        evaluation_mode="measured",
        evidence_ids=[result.evidence_id],
        confidence=0.9,
    )

    normalized_observation = augment_precise_numeric_references(
        observation, [base, model, platform, result, other_row]
    )

    assert normalized_observation.evidence_ids == [
        result.evidence_id,
        model.evidence_id,
        platform.evidence_id,
    ]


def test_observation_mode_is_joined_from_unique_explicit_same_paper_context():
    exact = _evidence(page=7, element_id="latency-result").model_copy(
        update={
            "snippet": (
                "PF Memory Appliance average 64-byte pool-to-host latency is 350 ns."
            ),
            "locator": _evidence(page=7, element_id="latency-result").locator.model_copy(
                update={"text_span": TextSpan(start=0, end=73)}
            ),
        }
    )
    mode = _evidence(page=2, element_id="evaluation-summary").model_copy(
        update={
            "snippet": (
                "We evaluate PF Memory Appliance latency through hardware emulation "
                "on the Veloce platform."
            ),
            "locator": _evidence(page=2, element_id="evaluation-summary").locator.model_copy(
                update={"text_span": TextSpan(start=0, end=92)}
            ),
        }
    )
    extraction = DossierExtraction(
        analysis=PaperAnalysis(
            technical_overview=TechnicalOverview(),
            scope=ScopeAnalysis(),
            limitations=LimitationsAnalysis(),
        ),
        claims=[],
        critical_inventory=[
            CriticalClaimItem(
                inventory_id="seed",
                category="result",
                summary="latency",
                disposition="excluded",
                reason="seed",
            )
        ],
        experiment_observations=[
            ExperimentObservation(
                observation_id="obs-latency",
                metric="PF Memory Appliance pool-to-host latency",
                value="350 ns",
                unit="ns",
                hardware="PF Memory Appliance",
                workload="64-byte access",
                evaluation_mode="not_stated",
                evidence_ids=[exact.evidence_id],
                confidence=0.9,
            )
        ],
    )

    normalized = augment_observation_evaluation_modes(extraction, [exact, mode])
    observation = normalized.experiment_observations[0]

    assert observation.evaluation_mode == "emulated"
    assert observation.evidence_ids == [exact.evidence_id, mode.evidence_id]


def test_observation_mode_stays_not_stated_when_modes_are_lexically_ambiguous():
    exact = _evidence(page=7, element_id="latency-result").model_copy(
        update={"snippet": "PF Memory Appliance latency is 350 ns."}
    )
    emulated = _evidence(page=2, element_id="emulation").model_copy(
        update={"snippet": "PF Memory Appliance latency uses emulation parameters."}
    )
    simulated = _evidence(page=3, element_id="simulation").model_copy(
        update={"snippet": "PF Memory Appliance latency uses simulation parameters."}
    )
    observation = ExperimentObservation(
        observation_id="obs-latency",
        metric="PF Memory Appliance latency",
        value="350 ns",
        evaluation_mode="not_stated",
        evidence_ids=[exact.evidence_id],
        confidence=0.9,
    )

    normalized = augment_observation_evaluation_modes(
        observation, [exact, emulated, simulated]
    )

    assert normalized.evaluation_mode == "not_stated"
    assert normalized.evidence_ids == [exact.evidence_id]
