from __future__ import annotations

from paper_review_agent.schemas import (
    Chunk,
    GroundedClaim,
    LimitationsAnalysis,
    PaperAnalysis,
    PaperMetadata,
    ScopeAnalysis,
    TechnicalOverview,
    TableCellRef,
)
from paper_review_agent.research_graph import _technical_evidences
from paper_review_agent.technical_models import (
    _materialize_critical_contract,
    _namespace_extraction_ids,
    merge_dossier_extractions,
)
from paper_review_agent.technical_schemas import (
    CriticalClaimItem,
    DifferingAssumption,
    DossierExtraction,
    EvidenceLocator,
    ExperimentObservation,
    MetricComparison,
    PaperAssumption,
    TechnicalAudit,
    TechnicalAuditItem,
    TechnicalClaim,
    TechnicalComparison,
    TechnicalDossier,
    TechnicalEvidence,
    TechnologyRelationship,
    ComparisonCell,
    TextSpan,
    UnverifiedItem,
)
from paper_review_agent.technical_validation import (
    NUMBER_RE,
    _number_tokens,
    analysis_audit_item_ids,
    validate_comparison_contract,
    validate_dossier_contract,
)


def _evidence(
    *,
    evidence_id: str = "paper:paper-a:evidence-1",
    document_id: str = "paper-a",
    snippet: str = "At 128K context, RDKV achieves a 4.5× decode speedup on A100.",
    with_span: bool = True,
    source_kind: str = "paper",
) -> TechnicalEvidence:
    return TechnicalEvidence(
        evidence_id=evidence_id,
        source_kind=source_kind,
        document_id=document_id,
        content_kind="text",
        snippet=snippet,
        content_hash="b" * 64,
        locator=EvidenceLocator(
            document_sha256="a" * 64,
            physical_page=9,
            section_path=["Results", "Memory and Latency"],
            element_id=f"element-{document_id}",
            text_span=TextSpan(start=0, end=len(snippet)) if with_span else None,
        ),
    )


def _grounded_claim(evidence_id: str, text: str) -> GroundedClaim:
    return GroundedClaim(
        text=text,
        claim_type="author_claim",
        evidence_ids=[evidence_id],
        confidence=0.85,
    )


def _analysis(evidence_id: str) -> PaperAnalysis:
    return PaperAnalysis(
        technical_overview=TechnicalOverview(
            problem_definition=[_grounded_claim(evidence_id, "KV cache가 병목이다.")],
            core_approach=[_grounded_claim(evidence_id, "KV cache를 압축한다.")],
            experimental_results=[
                _grounded_claim(evidence_id, "128K에서 decode speedup을 보고했다.")
            ],
        ),
        scope=ScopeAnalysis(),
        limitations=LimitationsAnalysis(
            author_stated=[
                _grounded_claim(evidence_id, "긴 생성은 추가 검증이 필요하다.")
            ]
        ),
    )


def _dossier(
    evidence: TechnicalEvidence,
    *,
    observation_id: str = "obs-speedup",
    hardware: str = "A100 64 GB",
    value: str = "4.5×",
) -> TechnicalDossier:
    claim_id = f"claim-{evidence.document_id}"
    return TechnicalDossier(
        paper=PaperMetadata(
            paper_id=evidence.document_id,
            title=f"Paper {evidence.document_id}",
            source_path=f"/{evidence.document_id}.pdf",
            source_hash=evidence.locator.document_sha256,
            page_count=10,
        ),
        analysis=_analysis(evidence.evidence_id),
        claims=[
            TechnicalClaim(
                claim_id=claim_id,
                text="RDKV는 KV cache를 압축한다.",
                claim_type="author_claim",
                evidence_ids=[evidence.evidence_id],
                confidence=0.85,
                critical=True,
            )
        ],
        critical_inventory=[
            CriticalClaimItem(
                inventory_id=f"inventory-{evidence.document_id}",
                category="contribution",
                summary="KV cache 압축 기법",
                disposition="extracted",
                claim_ids=[claim_id],
                evidence_ids=[evidence.evidence_id],
            )
        ],
        experiment_observations=[
            ExperimentObservation(
                observation_id=observation_id,
                metric="decode speedup",
                value=value,
                unit="×",
                direction="higher_is_better",
                baseline="FullKV FlashAttention-2",
                model="LLaMA-3.1-8B-Instruct",
                hardware=hardware,
                context_length="128K",
                workload="autoregressive decode",
                evaluation_mode="measured",
                evidence_ids=[evidence.evidence_id],
                confidence=0.9,
            )
        ],
        evidence_ids=[evidence.evidence_id],
    )


def _supported_audit(dossier: TechnicalDossier) -> TechnicalAudit:
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
                reason="직접 근거가 있다.",
            )
            for item_id in item_ids
        ]
    )


def test_critical_inventory_requires_resolved_claims_and_complete_audit():
    evidence = _evidence()
    dossier = _dossier(evidence)

    errors, _ = validate_dossier_contract(
        dossier,
        [evidence],
        _supported_audit(dossier),
    )
    assert errors == []

    unknown_claim = dossier.model_copy(
        update={
            "critical_inventory": [
                dossier.critical_inventory[0].model_copy(
                    update={"claim_ids": ["claim-not-extracted"]}
                )
            ]
        }
    )
    errors, _ = validate_dossier_contract(unknown_claim, [evidence])
    assert any("unknown claim_id claim-not-extracted" in error for error in errors)

    incomplete_audit = _supported_audit(dossier).model_copy(
        update={"missing_critical_topics": ["headline result from abstract"]}
    )
    errors, _ = validate_dossier_contract(dossier, [evidence], incomplete_audit)
    assert "missing critical topic: headline result from abstract" in errors


def test_inferred_analysis_fields_require_analyst_inference_claim_type():
    evidence = _evidence()
    dossier = _dossier(evidence)
    author_inference = _grounded_claim(
        evidence.evidence_id, "제공된 근거는 다른 배포 환경을 확립하지 않는다."
    )
    invalid_analysis = dossier.analysis.model_copy(
        update={
            "scope": dossier.analysis.scope.model_copy(
                update={"inferred_scope": [author_inference]}
            ),
            "limitations": dossier.analysis.limitations.model_copy(
                update={"inferred": [author_inference]}
            ),
        }
    )

    errors, _ = validate_dossier_contract(
        dossier.model_copy(update={"analysis": invalid_analysis}), [evidence]
    )
    assert any("inferred_scope[0]: inferred claim" in error for error in errors)
    assert any("limitations.inferred[0]: inferred claim" in error for error in errors)

    analyst_inference = author_inference.model_copy(
        update={"claim_type": "analyst_inference"}
    )
    valid_analysis = invalid_analysis.model_copy(
        update={
            "scope": invalid_analysis.scope.model_copy(
                update={"inferred_scope": [analyst_inference]}
            ),
            "limitations": invalid_analysis.limitations.model_copy(
                update={"inferred": [analyst_inference]}
            ),
        }
    )
    errors, _ = validate_dossier_contract(
        dossier.model_copy(update={"analysis": valid_analysis}), [evidence]
    )
    assert not [error for error in errors if "inferred claim" in error]


def test_numeric_observation_requires_matching_number_and_precise_locator():
    evidence = _evidence()
    dossier = _dossier(evidence)
    errors, _ = validate_dossier_contract(dossier, [evidence])
    assert not [error for error in errors if "numeric" in error]

    absent_number = _dossier(evidence, value="9.1%")
    errors, _ = validate_dossier_contract(absent_number, [evidence])
    assert any("numeric value '9.1%' is absent" in error for error in errors)

    imprecise_evidence = _evidence(with_span=False)
    errors, _ = validate_dossier_contract(
        _dossier(imprecise_evidence), [imprecise_evidence]
    )
    assert any("numeric evidence requires a text span" in error for error in errors)


def test_numeric_matching_uses_exact_tokens_and_accepts_number_words():
    numeric_only = _evidence(
        snippet=(
            "At 128K context, RDKV achieves a 4.5× decode speedup on A100; "
            "the appendix also reports a 256K run."
        )
    )
    errors, _ = validate_dossier_contract(
        _dossier(numeric_only, value="5"), [numeric_only]
    )

    assert any("numeric value '5' is absent" in error for error in errors)

    number_word = _evidence(
        snippet=(
            "At 128K context, RDKV achieves a 4.5× decode speedup on A100 "
            "and evaluates five open-source models."
        )
    )
    errors, _ = validate_dossier_contract(
        _dossier(number_word, value="5"), [number_word]
    )

    assert not [error for error in errors if "numeric" in error]


def test_numeric_observation_recombines_separate_percent_unit_exactly():
    evidence = _evidence(snippet="The visual reports 82% and 6.35% utilization.")
    percent = _dossier(evidence, value="82").experiment_observations[0].model_copy(
        update={"unit": "%"}
    )
    dossier = _dossier(evidence, value="82").model_copy(
        update={"experiment_observations": [percent]}
    )

    errors, _ = validate_dossier_contract(dossier, [evidence])
    assert not [error for error in errors if "numeric value '82%'" in error]

    strict_observation = percent.model_copy(update={"value": "5", "unit": "×"})
    strict = dossier.model_copy(
        update={"experiment_observations": [strict_observation]}
    )
    errors, _ = validate_dossier_contract(strict, [evidence])
    assert any("numeric value '5' is absent" in error for error in errors)


def test_numeric_observation_recombines_qualified_multiplier_unit():
    evidence = _evidence(
        snippet=(
            "At 128K context, the baseline is 4.5× and the simulation reports "
            "a 6.6× higher result; a separate appendix value is 256."
        )
    )
    observation = _dossier(evidence, value="6.6").experiment_observations[0].model_copy(
        update={"unit": "× higher"}
    )
    dossier = _dossier(evidence, value="6.6").model_copy(
        update={"experiment_observations": [observation]}
    )

    errors, _ = validate_dossier_contract(dossier, [evidence])
    assert not [error for error in errors if "numeric value '6.6'" in error]

    strict_observation = observation.model_copy(update={"value": "5"})
    strict = dossier.model_copy(
        update={"experiment_observations": [strict_observation]}
    )
    errors, _ = validate_dossier_contract(strict, [evidence])
    assert any("numeric value '5' is absent" in error for error in errors)


def test_numeric_observation_recombines_qualified_percent_units():
    evidence = _evidence(
        snippet=(
            "At 128K context, the baseline is 4.5×; utilization is 82% higher "
            "and the miss rate is 6.35% lower."
        )
    )
    base = _dossier(evidence, value="82")

    for value, unit in (("82", "% higher"), ("6.35", "percent lower")):
        observation = base.experiment_observations[0].model_copy(
            update={"value": value, "unit": unit}
        )
        dossier = base.model_copy(update={"experiment_observations": [observation]})
        errors, _ = validate_dossier_contract(dossier, [evidence])
        assert not [
            error for error in errors if f"numeric value {value!r}" in error
        ]


def test_ascii_hyphen_between_numeric_bounds_is_a_range_separator():
    tokens = _number_tokens(
        "Table I reports 3.3×-27.5×, 10%-20%, and 3-5; "
        "a genuine regression remains -4.5×."
    )

    assert {"3.3×", "27.5×", "10%", "20%", "3", "5", "-4.5×"}.issubset(
        tokens
    )
    assert "-27.5×" not in tokens
    assert "-20%" not in tokens

    evidence = _evidence(
        snippet=(
            "At 128K context the reference is 4.5×. "
            "Table I reports a host-memory range of 3.3×-27.5×."
        )
    )
    errors, _ = validate_dossier_contract(
        _dossier(evidence, value="27.5×"), [evidence]
    )
    assert not [error for error in errors if "numeric value '27.5×'" in error]


def test_numeric_tokens_split_braced_sets_but_keep_thousands_values():
    tokens = _number_tokens(
        "n∈{64,128,256,512,1024}; overhead is 1,740 ms and TTFT is 30,583 ms"
    )

    assert {"64", "128", "256", "512", "1024"}.issubset(tokens)
    assert {"1740", "30583"}.issubset(tokens)
    assert "641282565121024" not in tokens


def test_numeric_tokens_accept_pdf_space_grouped_thousands():
    tokens = _number_tokens(
        "FullKV prefill is 28 843 ms and RDKV TTFT is 30\u202f583 ms; "
        "budgets are 64 128 256."
    )

    assert {"28843", "30583"}.issubset(tokens)
    assert {"64", "128", "256"}.issubset(tokens)


def test_numeric_scanner_ignores_model_and_hardware_identifier_digits():
    values = [match.group(0) for match in NUMBER_RE.finditer(
        "LLaMA-3.1-8B on A100 at 128K achieved 4.5× speedup and 9.1%."
    )]

    assert values == ["128", "4.5×", "9.1%"]

    tokens = _number_tokens("LLaMA-3.1-8B and A100-80GB")
    assert not tokens


def test_context_evidence_ids_accept_only_common_corpus_evidence():
    paper_evidence = _evidence()
    dossier = _dossier(paper_evidence)
    problem = dossier.analysis.technical_overview.problem_definition[0]

    invalid_analysis = dossier.analysis.model_copy(
        update={
            "technical_overview": dossier.analysis.technical_overview.model_copy(
                update={
                    "problem_definition": [
                        problem.model_copy(
                            update={
                                "context_evidence_ids": [paper_evidence.evidence_id]
                            }
                        )
                    ]
                }
            )
        }
    )
    invalid = dossier.model_copy(update={"analysis": invalid_analysis})
    errors, _ = validate_dossier_contract(invalid, [paper_evidence])
    assert any(
        "context_evidence_ids require common evidence" in error for error in errors
    )

    common = _evidence(
        evidence_id="common:glossary:evidence-1",
        document_id="approved-glossary",
        source_kind="common",
    )
    valid_analysis = dossier.analysis.model_copy(
        update={
            "technical_overview": dossier.analysis.technical_overview.model_copy(
                update={
                    "problem_definition": [
                        problem.model_copy(
                            update={"context_evidence_ids": [common.evidence_id]}
                        )
                    ]
                }
            )
        }
    )
    valid = dossier.model_copy(update={"analysis": valid_analysis})
    errors, _ = validate_dossier_contract(valid, [paper_evidence, common])
    assert not [error for error in errors if "context_evidence" in error]

    claim_with_common = dossier.claims[0].model_copy(
        update={"context_evidence_ids": [common.evidence_id]}
    )
    valid_claim_context = dossier.model_copy(update={"claims": [claim_with_common]})
    errors, _ = validate_dossier_contract(valid_claim_context, [paper_evidence, common])
    assert not [error for error in errors if "context_evidence" in error]

    claim_with_paper_context = dossier.claims[0].model_copy(
        update={"context_evidence_ids": [paper_evidence.evidence_id]}
    )
    invalid_claim_context = dossier.model_copy(
        update={"claims": [claim_with_paper_context]}
    )
    errors, _ = validate_dossier_contract(invalid_claim_context, [paper_evidence])
    assert any(
        "context_evidence_ids require common evidence" in error for error in errors
    )


def test_incompatible_experiment_signatures_must_be_not_comparable():
    left_evidence = _evidence(
        evidence_id="paper:left:evidence-1",
        document_id="left",
    )
    right_evidence = _evidence(
        evidence_id="paper:right:evidence-1",
        document_id="right",
        snippet="At 128K context, the method achieves a 4.5× decode speedup on H200.",
    )
    left = _dossier(left_evidence, observation_id="obs-left", hardware="A100 64 GB")
    right = _dossier(right_evidence, observation_id="obs-right", hardware="H200 141 GB")

    comparable = TechnicalComparison(
        relationships=[
            TechnologyRelationship(
                left_paper_id="left",
                right_paper_id="right",
                relationship="orthogonal",
                rationale="서로 다른 하드웨어 조건이다.",
                evidence_ids=[left_evidence.evidence_id, right_evidence.evidence_id],
            )
        ],
        differing_assumptions=[
            DifferingAssumption(
                assumption_id="assumption-hardware",
                dimension="hardware",
                paper_assumptions=[
                    PaperAssumption(
                        paper_id="left",
                        statement="A100 64 GB에서 측정했다.",
                        evidence_ids=[left_evidence.evidence_id],
                    ),
                    PaperAssumption(
                        paper_id="right",
                        statement="H200 141 GB에서 측정했다.",
                        evidence_ids=[right_evidence.evidence_id],
                    ),
                ],
                implication="하드웨어 차이 때문에 수치를 직접 비교할 수 없다.",
            )
        ],
        matrix=[
            ComparisonCell(
                dimension="mechanism",
                paper_id="left",
                summary="왼쪽 기술",
                evidence_ids=[left_evidence.evidence_id],
            ),
            ComparisonCell(
                dimension="mechanism",
                paper_id="right",
                summary="오른쪽 기술",
                evidence_ids=[right_evidence.evidence_id],
            ),
        ],
        metric_comparisons=[
            MetricComparison(
                comparison_id="cmp-speedup",
                metric="decode speedup",
                observation_ids=["obs-left", "obs-right"],
                comparability="comparable",
                reason="두 결과를 직접 비교한다.",
            )
        ],
    )
    errors = validate_comparison_contract(
        comparable,
        [left, right],
        [left_evidence, right_evidence],
    )
    assert errors == [
        "cmp-speedup: incompatible experiment signatures must be not_comparable"
    ]

    not_comparable = comparable.model_copy(
        update={
            "metric_comparisons": [
                comparable.metric_comparisons[0].model_copy(
                    update={
                        "comparability": "not_comparable",
                        "reason": "hardware가 A100과 H200으로 다르다.",
                    }
                )
            ]
        }
    )
    assert (
        validate_comparison_contract(
            not_comparable,
            [left, right],
            [left_evidence, right_evidence],
        )
        == []
    )


def test_table_numeric_evidence_is_expanded_to_exact_cell_ids():
    chunk = Chunk(
        chunk_id="table-chunk",
        source_kind="paper",
        document_id="paper-a",
        page=6,
        section="Results",
        content_kind="table",
        text="| Context | Speedup |\n| --- | --- |\n| 128K | 4.5× |",
        content_hash="c" * 64,
        element_id="table-01",
        object_label="Table 1",
        table_cells=[
            TableCellRef(
                row_index=1,
                column_index=1,
                raw_text="4.5×",
                row_header="128K",
                column_header="Speedup",
            )
        ],
        extraction_method="pdfplumber",
    )

    evidence = _technical_evidences(chunk, "a" * 64)

    assert evidence[0].evidence_id.endswith(":table-01:whole")
    assert evidence[0].locator.table_cells == []
    assert evidence[1].evidence_id.endswith(":table-01:cell-r01-c01")
    assert evidence[1].locator.table_cells[0].raw_text == "4.5×"


def test_table_evidence_uses_normalized_roman_object_and_row_group_ids():
    chunk = Chunk(
        chunk_id="abcdef0123456789abcdef01",
        source_kind="paper",
        document_id="paper-a",
        document_version="a" * 64,
        page=6,
        section="Results",
        content_kind="table",
        text="| Model | Throughput |\n| --- | --- |\n| A | 128 GB/s |",
        content_hash="c" * 64,
        element_id="elem-paper-a-p0006-table-003-deadbeef",
        object_label="Table IV",
        text_span={"start": 0, "end": 400},
        table_cells=[
            TableCellRef(
                row_index=3,
                column_index=4,
                raw_text="128 GB/s",
                row_header="A",
                column_header="Throughput",
            )
        ],
        extraction_method="pdfplumber",
    )

    evidence = _technical_evidences(chunk, "a" * 64)

    assert evidence[0].evidence_id.endswith(":table-04:rows-r03-r03")
    assert evidence[1].evidence_id.endswith(":table-04:cell-r03-c04")
    assert evidence[1].locator.element_id == "table-04"
    assert evidence[1].locator.normalized_object_label == "Table 4"
    assert evidence[1].locator.source_element_id == chunk.element_id
    assert evidence[1].locator.source_chunk_id == chunk.chunk_id


def test_model_generated_ids_are_namespaced_and_inventory_references_follow():
    evidence = _evidence()
    dossier = _dossier(evidence)
    extraction = DossierExtraction(
        analysis=dossier.analysis,
        claims=dossier.claims,
        critical_inventory=dossier.critical_inventory,
        experiment_observations=dossier.experiment_observations,
        unverified_items=[],
    )

    scoped = _namespace_extraction_ids(extraction, "paper-a")

    assert scoped.claims[0].claim_id == "paper-a::claim-paper-a"
    assert scoped.critical_inventory[0].claim_ids == ["paper-a::claim-paper-a"]
    assert scoped.critical_inventory[0].inventory_id.startswith("paper-a::")
    assert scoped.experiment_observations[0].observation_id == "paper-a::obs-speedup"


def test_repair_merge_is_lossless_and_strips_provider_meta_records():
    evidence = _evidence()
    dossier = _dossier(evidence)
    previous = DossierExtraction(
        analysis=dossier.analysis,
        claims=dossier.claims,
        critical_inventory=dossier.critical_inventory,
        experiment_observations=dossier.experiment_observations,
        unverified_items=[
            UnverifiedItem(
                item_id="old-unverified",
                topic="physical deployment",
                reason="not found in supplied evidence",
                searched_queries=["physical deployment"],
                attempts=1,
            )
        ],
    )
    replacement = dossier.claims[0].model_copy(
        update={"text": "RDKV는 KV cache 예산을 동적으로 배분한다."}
    )
    repaired = TechnicalClaim(
        claim_id="claim-repaired-limitation",
        text="Prefill 이후 allocation은 고정된다.",
        claim_type="author_claim",
        evidence_ids=[evidence.evidence_id],
        confidence=0.9,
        critical=True,
    )
    invalid = TechnicalClaim(
        claim_id="invalid",
        text="유효하지 않은 evidence ID 때문에 추출 결과를 생성할 수 없다.",
        claim_type="analyst_inference",
        evidence_ids=[evidence.evidence_id],
        confidence=0.1,
        critical=True,
    )
    current = DossierExtraction(
        analysis=PaperAnalysis(
            technical_overview=TechnicalOverview(
                core_approach=[
                    _grounded_claim(
                        evidence.evidence_id,
                        "KV cache 예산을 동적으로 배분한다.",
                    )
                ],
                not_reported=[
                    "수정 필요: 유효하지 않은 evidence ID가 포함되어 있다."
                ],
            ),
            scope=ScopeAnalysis(),
            limitations=LimitationsAnalysis(),
        ),
        claims=[replacement, repaired, invalid],
        critical_inventory=[
            dossier.critical_inventory[0].model_copy(
                update={"summary": "동적 KV cache 배분"}
            ),
            CriticalClaimItem(
                inventory_id="inventory-repaired-limitation",
                category="limitation",
                summary="Prefill 이후 allocation 고정",
                disposition="extracted",
                claim_ids=[repaired.claim_id],
                evidence_ids=[evidence.evidence_id],
            ),
            CriticalClaimItem(
                inventory_id="invalid",
                category="limitation",
                summary="유효하지 않은 evidence ID로 인해 추출 불가",
                disposition="unverified",
                reason="입력 생성 중 evidence ID 형식 오류",
                searched_queries=["invalid evidence ID"],
            ),
        ],
        experiment_observations=[],
        unverified_items=[
            UnverifiedItem(
                item_id="new-unverified",
                topic="multi-tenant evaluation",
                reason="not found in supplied evidence",
                searched_queries=["multi-tenant evaluation"],
                attempts=2,
            ),
            UnverifiedItem(
                item_id="invalid",
                topic="유효한 추출",
                reason="유효하지 않은 evidence ID로 추출 실패",
                searched_queries=["invalid evidence ID"],
                attempts=2,
            ),
        ],
    )

    merged = merge_dossier_extractions(previous, current)

    assert merged.analysis.technical_overview.experimental_results == (
        previous.analysis.technical_overview.experimental_results
    )
    assert merged.analysis.limitations.author_stated == (
        previous.analysis.limitations.author_stated
    )
    assert merged.claims[0].text == replacement.text
    assert {item.claim_id for item in merged.claims} == {
        dossier.claims[0].claim_id,
        repaired.claim_id,
    }
    assert merged.experiment_observations == previous.experiment_observations
    assert {item.item_id for item in merged.unverified_items} == {
        "old-unverified",
        "new-unverified",
    }
    assert all("invalid" not in item.inventory_id for item in merged.critical_inventory)
    assert merged.analysis.technical_overview.not_reported == []


def test_repair_merge_replaces_only_items_explicitly_rejected_by_audit():
    evidence = _evidence()
    dossier = _dossier(evidence)
    rejected = TechnicalClaim(
        claim_id="paper-a::bad-claim",
        text="The paper never evaluates deployment.",
        claim_type="analyst_inference",
        evidence_ids=[evidence.evidence_id],
        confidence=0.4,
        critical=True,
    )
    previous = DossierExtraction(
        analysis=PaperAnalysis(
            technical_overview=TechnicalOverview(
                training_process=[
                    _grounded_claim(
                        evidence.evidence_id,
                        "The paper reports no training process.",
                    )
                ]
            ),
            scope=ScopeAnalysis(),
            limitations=LimitationsAnalysis(),
        ),
        claims=[dossier.claims[0], rejected],
        critical_inventory=[
            dossier.critical_inventory[0],
            CriticalClaimItem(
                inventory_id="bad-inventory",
                category="limitation",
                summary=rejected.text,
                disposition="extracted",
                claim_ids=[rejected.claim_id],
                evidence_ids=rejected.evidence_ids,
            ),
        ],
        experiment_observations=dossier.experiment_observations,
    )
    corrected = TechnicalClaim(
        claim_id="paper-a::corrected-claim",
        text="The supplied evidence concerns inference and does not establish training coverage.",
        claim_type="analyst_inference",
        evidence_ids=[evidence.evidence_id],
        confidence=0.7,
        critical=True,
    )
    current = DossierExtraction(
        analysis=PaperAnalysis(
            technical_overview=TechnicalOverview(
                training_process=[
                    _grounded_claim(evidence.evidence_id, corrected.text)
                ]
            ),
            scope=ScopeAnalysis(),
            limitations=LimitationsAnalysis(),
        ),
        claims=[corrected],
        critical_inventory=[
            CriticalClaimItem(
                inventory_id="corrected-inventory",
                category="limitation",
                summary=corrected.text,
                disposition="extracted",
                claim_ids=[corrected.claim_id],
                evidence_ids=corrected.evidence_ids,
            )
        ],
        experiment_observations=[],
    )

    merged = merge_dossier_extractions(
        previous,
        current,
        repair_feedback=[
            "semantic audit failed: paper-a::bad-claim=unsupported: overbroad",
            "semantic audit failed: analysis.technical_overview.training_process[0]="
            "unsupported: absence is not established",
        ],
    )

    assert rejected.claim_id not in {item.claim_id for item in merged.claims}
    assert "bad-inventory" not in {
        item.inventory_id for item in merged.critical_inventory
    }
    assert merged.analysis.technical_overview.training_process == (
        current.analysis.technical_overview.training_process
    )
    assert dossier.claims[0] in merged.claims
    assert dossier.experiment_observations == merged.experiment_observations


def test_unlinked_critical_claim_is_attached_only_to_unique_evidence_match():
    evidence = _evidence()
    dossier = _dossier(evidence)
    additional = dossier.claims[0].model_copy(
        update={"claim_id": "critical-limitation", "critical": True}
    )
    extraction = DossierExtraction(
        analysis=dossier.analysis,
        claims=[*dossier.claims, additional],
        critical_inventory=dossier.critical_inventory,
        experiment_observations=dossier.experiment_observations,
    )

    scoped = _namespace_extraction_ids(extraction, "paper-a")

    assert scoped.critical_inventory[0].claim_ids == [
        "paper-a::claim-paper-a",
        "paper-a::critical-limitation",
    ]


def test_analysis_and_observations_materialize_as_critical_contract_items():
    evidence = _evidence()
    dossier = _dossier(evidence)
    extraction = DossierExtraction(
        analysis=dossier.analysis,
        claims=dossier.claims,
        critical_inventory=dossier.critical_inventory,
        experiment_observations=dossier.experiment_observations,
    )

    normalized = _namespace_extraction_ids(
        _materialize_critical_contract(extraction), "paper-a"
    )
    linked = {
        claim_id
        for item in normalized.critical_inventory
        for claim_id in item.claim_ids
    }

    assert len(normalized.claims) > len(extraction.claims)
    assert {
        claim.claim_id for claim in normalized.claims if claim.critical
    }.issubset(linked)
    assert any(
        item.category == "result" and "4.5×" in item.summary
        for item in normalized.critical_inventory
    )
    projected = next(
        claim
        for claim in normalized.claims
        if claim.text.startswith("decode speedup:")
    )
    assert "4.5×" in projected.text
    assert "baseline=FullKV FlashAttention-2" in projected.text
    assert "model=LLaMA-3.1-8B-Instruct" in projected.text
    assert "hardware=A100 64 GB" in projected.text
    assert "context=128K" in projected.text
    assert "workload=autoregressive decode" in projected.text
    assert "evaluation_mode=measured" in projected.text


def test_materialized_observation_adds_unit_only_when_value_omits_it():
    evidence = _evidence(snippet="Average emulated access latency is 350 ns.")
    dossier = _dossier(evidence)
    observation = dossier.experiment_observations[0].model_copy(
        update={
            "metric": "average access latency",
            "value": "350",
            "unit": "ns",
            "baseline": "electrical CXL pool",
            "hardware": None,
            "context_length": None,
            "workload": "64-byte access",
            "evaluation_mode": "emulated",
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
                reason="seed item",
            )
        ],
        experiment_observations=[observation],
    )

    normalized = _materialize_critical_contract(extraction)
    claim = next(item for item in normalized.claims if "350" in item.text)

    assert "average access latency: 350 ns" in claim.text
    assert "baseline=electrical CXL pool" in claim.text
    assert "workload=64-byte access" in claim.text
    assert "evaluation_mode=emulated" in claim.text


def test_missing_inventory_claim_ids_parse_and_link_by_shared_evidence():
    evidence = _evidence()
    dossier = _dossier(evidence)
    payload = DossierExtraction(
        analysis=dossier.analysis,
        claims=dossier.claims,
        critical_inventory=dossier.critical_inventory,
        experiment_observations=dossier.experiment_observations,
        unverified_items=[],
    ).model_dump(mode="json")
    payload["critical_inventory"][0].pop("claim_ids")

    parsed = DossierExtraction.model_validate(payload)
    assert parsed.critical_inventory[0].claim_ids == []

    scoped = _namespace_extraction_ids(parsed, "paper-a")

    assert scoped.critical_inventory[0].claim_ids == [
        "paper-a::claim-paper-a"
    ]


def test_contract_rejects_extracted_inventory_with_missing_claim_or_evidence():
    evidence = _evidence()
    dossier = _dossier(evidence)
    item = dossier.critical_inventory[0]

    missing_claim = dossier.model_copy(
        update={
            "critical_inventory": [item.model_copy(update={"claim_ids": []})]
        }
    )
    errors, _ = validate_dossier_contract(missing_claim, [evidence])
    assert any(
        item.inventory_id in error and "claim_ids" in error for error in errors
    )

    missing_evidence = dossier.model_copy(
        update={
            "critical_inventory": [item.model_copy(update={"evidence_ids": []})]
        }
    )
    errors, _ = validate_dossier_contract(missing_evidence, [evidence])
    assert any(
        item.inventory_id in error and "evidence_ids" in error for error in errors
    )


def test_multi_paper_comparison_requires_relationship_matrix_and_assumptions():
    left_evidence = _evidence(evidence_id="paper:left:evidence-1", document_id="left")
    right_evidence = _evidence(
        evidence_id="paper:right:evidence-1", document_id="right"
    )
    errors = validate_comparison_contract(
        TechnicalComparison(),
        [_dossier(left_evidence), _dossier(right_evidence)],
        [left_evidence, right_evidence],
    )

    assert (
        "technical comparison relationships must not be empty for multiple papers"
        in errors
    )
    assert "technical comparison matrix must not be empty for multiple papers" in errors
    assert (
        "technical comparison must explicitly record common or differing assumptions"
        in errors
    )
    assert "missing technology relationship for papers: left, right" in errors


def test_comparison_requires_every_unordered_paper_pair():
    items = [
        _evidence(evidence_id=f"paper:{name}:evidence-1", document_id=name)
        for name in ("a", "b", "c")
    ]
    dossiers = [
        _dossier(item, observation_id=f"obs-{item.document_id}") for item in items
    ]
    comparison = TechnicalComparison(
        relationships=[
            TechnologyRelationship(
                left_paper_id="a",
                right_paper_id="b",
                relationship="orthogonal",
                rationale="서로 다른 계층이다.",
                evidence_ids=[items[0].evidence_id, items[1].evidence_id],
            )
        ],
        differing_assumptions=[
            DifferingAssumption(
                assumption_id="assumption-hardware",
                dimension="hardware",
                paper_assumptions=[
                    PaperAssumption(
                        paper_id=item.document_id,
                        statement=f"{item.document_id} 전용 하드웨어",
                        evidence_ids=[item.evidence_id],
                    )
                    for item in items
                ],
                implication="실험 환경이 다르다.",
            )
        ],
        matrix=[
            ComparisonCell(
                dimension="mechanism",
                paper_id=item.document_id,
                summary=f"{item.document_id} 메커니즘",
                evidence_ids=[item.evidence_id],
            )
            for item in items
        ],
    )

    errors = validate_comparison_contract(comparison, dossiers, items)

    assert "missing technology relationship for papers: a, c" in errors
    assert "missing technology relationship for papers: b, c" in errors
