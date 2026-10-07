"""No-transport regression cases for complete corpus window delivery."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest

from pipeline.report_quality import (JudgeContractError, _corpus_windows, _screen_corpus,
    _source_spans, _validate_corpus_window, _audit_payload, _normalize_provider_answer, _audit,
    _corpus_receipt_unchanged)


def original(text):
    return {"evidence_id": "e1", "doc_id": "d1", "excerpt": text,
        "technology_ids": ["SW-01"], "source_hash": sha256(text.encode()).hexdigest(),
        "page": None, "location": "collected body", "locator": {}, "method": "statement",
        "independence": "author", "technology_relevance": "indirect", "synthetic": False}


CLAIMS = [{"claim_id": "c1", "text": "A constrained claim", "kind": "author_report",
           "technology_ids": ["SW-01"], "citation_keys": ["WEB_A"], "core": True}]


def reading(data, index=None, relation="condition"):
    observation = [] if index is None else [{"claim_ids": ["c1"], "relation": relation,
        "span_indices": [index], "reason": "The original states a limiting condition."}]
    return {"coverage_complete": True, "observations": observation,
        "claim_dispositions": {"c1": {"verdict": "relevant" if observation else "no_relevant_statement_in_window",
            "observation_indices": [0] if observation else [], "reason": "Only this supplied window was inspected."}},
        "omission_reason": "No statement about the claim occurs in this window." if not observation else ""}


def test_windows_cover_unicode_tail_with_overlap_without_text_loss():
    source = original("가🙂x"*54321 + "END: contrary condition")
    windows = _corpus_windows(source)
    cursor = 0
    for window in windows:
        assert window["window"]["start"] <= cursor
        assert window["window"]["end"] > cursor
        assert window["window"]["original_excerpt_sha256"] == source["source_hash"]
        for span in window["quote_spans"]:
            assert span["text"] == source["excerpt"][span["start"]:span["end"]]
        cursor = window["window"]["end"]
    assert cursor == len(source["excerpt"])
    assert windows[-1]["quote_spans"][-1]["text"].endswith("contrary condition")


def test_all_claim_dispositions_and_bounds_are_required():
    data = {**_corpus_windows(original("a"*2000))[0], "claims": CLAIMS}
    invalid = reading(data, 1); invalid["claim_dispositions"] = {}
    with pytest.raises(JudgeContractError): _validate_corpus_window(invalid, data)
    invalid = reading(data, 99)
    with pytest.raises(JudgeContractError): _validate_corpus_window(invalid, data)
    invalid = reading(data, 1); invalid["claim_dispositions"]["c1"]["observation_indices"] = []
    with pytest.raises(JudgeContractError): _validate_corpus_window(invalid, data)


def test_last_contrary_window_is_preserved_and_bound_against_original():
    source = original("A"*161000 + "not independently demonstrated")
    calls = []
    def verified(phase, data, validate):
        calls.append(data)
        last = data["window"]["end"] == len(source["excerpt"])
        answer = reading(data, len(data["quote_spans"])-1 if last else None, "contradiction")
        return answer, validate(answer)
    with TemporaryDirectory() as tmp:
        projected, manifest = _screen_corpus([source], CLAIMS, verified, Path(tmp), 1, 100000)
        assert manifest["complete"]
        assert len(calls) == 3
        span = _source_spans(projected[0])[-1]
        assert span["text"] == source["excerpt"][span["start"]:span["end"]]
        assert span["original_span_index"] > 100
        assert span["span_index"] == 0
        observation = projected[0]["corpus_observations"][-1]["observations"][0]
        assert observation["span_indices"] == [0]
        assert observation["window_span_indices"] != observation["span_indices"]
        assert projected[0]["screened_quote_spans"][observation["span_indices"][0]]["text"].endswith("not independently demonstrated")
        data = {"claims": CLAIMS, "evidence": projected,
                "documents": {"d1": {"sha256": source["source_hash"], "citation_key": "WEB_A"}}}
        normalized = _normalize_provider_answer("audit", json.dumps({"checks": {"c1": {
            "verdict": "contradicted", "reason": "Opposing proposition: not demonstrated",
            "claim_reference": {"evidence_id": "e1", "span_index": 0},
            "technology_references": {"SW-01": {"evidence_id": "e1", "span_index": 0}},
            "references": [], "target": "report", "role": None, "criterion_ids": []}}}), data)
        assert _audit(normalized, CLAIMS, [source], data["documents"])[0]["verdict"] == "contradicted"
        assert source["excerpt"].endswith("not independently demonstrated")


def test_unrelated_source_keeps_inventory_and_specific_omissions():
    source = original("navigation data "*2000)
    def verified(phase, data, validate):
        answer = reading(data)
        return answer, validate(answer)
    with TemporaryDirectory() as tmp:
        projected, manifest = _screen_corpus([source], CLAIMS, verified, Path(tmp), 1, 100000)
        assert projected[0]["evidence_id"] == source["evidence_id"]
        assert projected[0]["corpus_observations"][0]["omission_reason"]
        assert projected[0]["screened_quote_spans"][0]["text"] == source["excerpt"][:800]
        assert manifest["sources"][0]["windows"][0]["claim_dispositions"]["c1"]["verdict"] == "no_relevant_statement_in_window"


def test_window_failure_and_final_limit_never_complete_partial_corpus():
    source = original("x"*161000)
    count = 0
    def verified(phase, data, validate):
        nonlocal count
        count += 1
        if count == 3: raise TimeoutError("final window incomplete")
        answer = reading(data, 0)
        return answer, validate(answer)
    with TemporaryDirectory() as tmp:
        with pytest.raises(TimeoutError): _screen_corpus([source], CLAIMS, verified, Path(tmp), 1, 100000)
        assert not (Path(tmp)/"quality.corpus-coverage-1.json").exists()
    def valid(phase, data, validate):
        answer = reading(data, 0)
        return answer, validate(answer)
    with TemporaryDirectory() as tmp:
        with pytest.raises(JudgeContractError): _screen_corpus([source], CLAIMS, valid, Path(tmp), 1, 10)


def test_corpus_request_identity_includes_immutable_artifacts_and_source_changes():
    requests = []
    def verified(phase, data, validate):
        requests.append(deepcopy(data))
        answer = reading(data)
        return answer, validate(answer)
    with TemporaryDirectory() as tmp:
        source = original("x"*9000)
        _screen_corpus([source], CLAIMS, verified, Path(tmp), 1, 100000, artifact_identity={"pdf": "a"})
        _screen_corpus([source], CLAIMS, verified, Path(tmp), 2, 100000, artifact_identity={"pdf": "b"})
        changed = original("x"*8999+"否")
        _screen_corpus([changed], CLAIMS, verified, Path(tmp), 3, 100000, artifact_identity={"pdf": "b"})
        assert requests[0] != requests[1] != requests[2]


def test_final_corpus_receipt_modified_or_removed_cannot_pass_hash_gate():
    with TemporaryDirectory() as tmp:
        path = Path(tmp)/"coverage.json"; path.write_text('{"complete":true}')
        result = {"corpus_coverage_path": str(path), "hashes": {"corpus_coverage": sha256(path.read_bytes()).hexdigest()}}
        assert _corpus_receipt_unchanged(result)
        path.write_text('{"complete":false}')
        assert not _corpus_receipt_unchanged(result)
        path.unlink()
        assert not _corpus_receipt_unchanged(result)
        assert not _corpus_receipt_unchanged({"hashes": {"corpus_coverage": "missing"}})
        assert _corpus_receipt_unchanged({"hashes": {}})


def test_evaluate_report_rejects_corpus_manifest_changed_during_final_rubric():
    """Only a coverage-file change distinguishes this run from its passing control."""
    from unittest.mock import patch
    from pipeline.tests.test_report_quality import ReportQualityTests, canonical, payload

    case = ReportQualityTests(methodName="runTest")
    case.setUp()
    review = canonical()
    review["evidence"]["SW-laboratory"]["excerpt"] += " original context" * 6000
    calls = []

    def screened(evidence, claims, verified, output, attempt, limit, **kwargs):
        projections, sources = [], []
        for source in evidence:
            text = source["excerpt"]
            span = {"span_index": 0, "original_span_index": 0, "start": 0,
                    "end": min(800, len(text)), "text": text[:800]}
            observation = {"claim_ids": [claim["claim_id"] for claim in claims],
                "relation": "support", "span_indices": [0], "window_span_indices": [0],
                "reason": "OFFLINE: original laboratory report is retained."}
            window = {"start": 0, "end": len(text), "original_chars": len(text),
                      "original_excerpt_sha256": sha256(text.encode()).hexdigest()}
            reading = {"coverage_complete": True, "source_id": source["evidence_id"],
                "window": window, "observations": [observation], "omission_reason": "",
                "claim_dispositions": {claim["claim_id"]: {"verdict": "relevant",
                    "observation_indices": [0], "reason": "OFFLINE source boundary."} for claim in claims}}
            projections.append({**source, "excerpt": "", "screened_quote_spans": [span],
                "projection_mode": "independent_complete_corpus_reading_exact_original_spans",
                "corpus_observations": [reading]})
            sources.append({"evidence_id": source["evidence_id"], "mode": "complete_window_reading",
                "original_excerpt_sha256": window["original_excerpt_sha256"],
                "original_chars": len(text), "windows": [reading], "selected_original_spans": [span]})
        manifest = {"complete": True, "canonical_evidence_ids": [s["evidence_id"] for s in evidence],
                    "sources": sources}
        (output / f"quality.corpus-coverage-{attempt}.json").write_text(json.dumps(manifest))
        calls.append(kwargs["artifact_identity"])
        return projections, manifest

    try:
        results = []
        for mutate in (False, True):
            def responder(instructions, prompt):
                answer = case.responder(instructions, prompt)
                if mutate and payload(prompt)["phase"] == "rubric":
                    receipt = case.output / "quality.corpus-coverage-1.json"
                    assert receipt.exists()
                    receipt.write_text('{"complete":false,"changed_after_screening":true}')
                return answer
            with patch("pipeline.tests.test_report_quality.canonical", return_value=review), \
                 patch("pipeline.report_quality._screen_corpus", side_effect=screened):
                results.append(case.evaluate(responder, max_evidence_chars=80000))
        control, modified = results
        assert control["route"] == "passed", control
        assert control["gates"]["H6"]["status"] == "pass"
        assert modified["route"] == "review_required", modified
        assert modified["gates"]["H6"]["status"] == "fail"
        assert modified["weighted_score"] == control["weighted_score"] == 80
        assert len(calls) == 2 and all({"tex", "pdf", "canonical_evidence"} <= set(identity) for identity in calls)
        assert modified["evidence_selection"] == "independent_complete_corpus_windows_exact_original_spans"
    finally:
        case.doCleanups()
