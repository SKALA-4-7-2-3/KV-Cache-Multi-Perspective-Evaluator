"""Transport compression must preserve every independent corpus judgment."""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from pipeline.report_quality import (JudgeContractError, _corpus_schema,
    _corpus_windows, _corpus_wire_schema, _normalize_provider_answer,
    _provider, _provider_prompt, _validate_corpus_window)


def request(count=482):
    text = "Exact original condition. " * 80 + "Contrary tail remains unchanged."
    source = {"evidence_id": "original-1", "excerpt": text,
              "source_hash": sha256(text.encode()).hexdigest()}
    return {**_corpus_windows(source)[0], "claims": [
        {"claim_id": f"immutable-claim-{index}", "text": f"Full claim {index}",
         "technology_ids": ["SW-01"], "citation_keys": ["SOURCE_A"]}
        for index in range(count)]}


def wire(count=482):
    return {"codec_version": "corpus-groups-v1", "coverage_complete": True,
        "reason_pool": ["  Exact observed limiting condition.  ",
                        "Only this supplied original window has no relevant statement.",
                        "The claim is relevant to observation zero, with its qualification."],
        "observations": [
            {"claim_indices": [1, 0], "relation": "condition", "span_indices": [0, 1], "reason_index": 0},
            {"claim_indices": [], "relation": "context", "span_indices": [2], "reason_index": 0}],
        "disposition_groups": [
            {"claim_indices": list(range(2, count)), "verdict": "no_relevant_statement_in_window",
             "observation_indices": [], "reason_index": 1},
            {"claim_indices": [1, 0], "verdict": "relevant", "observation_indices": [0], "reason_index": 2}],
        "omission_reason": ""}


def decode(answer, data):
    return _normalize_provider_answer("corpus", json.dumps(answer), data)


def test_482_claim_expansion_is_exact_and_original_span_binding_is_unchanged():
    data, answer = request(), wire()
    original = deepcopy(data)
    normalized = decode(answer, data)
    assert list(normalized["claim_dispositions"]) == [claim["claim_id"] for claim in data["claims"]]
    assert len(normalized["claim_dispositions"]) == 482
    assert normalized["observations"][0] == {"claim_ids": ["immutable-claim-1", "immutable-claim-0"],
        "relation": "condition", "span_indices": [0, 1], "reason": answer["reason_pool"][0]}
    assert normalized["observations"][1]["claim_ids"] == []
    assert normalized["claim_dispositions"]["immutable-claim-481"]["reason"] == answer["reason_pool"][1]
    bound = _validate_corpus_window(normalized, data)
    assert bound["observations"][0]["supporting_quotes"] == data["quote_spans"][:2]
    assert bound["observations"][1]["supporting_quotes"] == [data["quote_spans"][2]]
    assert data == original
    assert set(normalized) == set(_corpus_schema(data)["properties"])
    assert decode(normalized, data) == normalized  # Verified legacy responses remain compatible.


@pytest.mark.parametrize("mutation", [
    lambda a: a["disposition_groups"][0]["claim_indices"].pop(),
    lambda a: a["disposition_groups"][0]["claim_indices"].append(2),
    lambda a: a["disposition_groups"][0]["claim_indices"].append(0),
    lambda a: a["disposition_groups"][0]["claim_indices"].append(-1),
    lambda a: a["disposition_groups"][0]["claim_indices"].append(482),
    lambda a: a["disposition_groups"][0]["claim_indices"].append(True),
    lambda a: a["disposition_groups"][1].update(reason_index=3),
    lambda a: a["disposition_groups"][1].update(reason_index=True),
    lambda a: a.update(reason_pool=[]),
    lambda a: a["reason_pool"].__setitem__(0, "  "),
    lambda a: a["observations"][0]["claim_indices"].append(0),
    lambda a: a["observations"][0]["claim_indices"].append(482),
    lambda a: a["observations"][0]["claim_indices"].append(False),
    lambda a: a["observations"][0]["span_indices"].append(99),
    lambda a: a["observations"][0]["span_indices"].append(True),
    lambda a: a["disposition_groups"][1].update(observation_indices=[1]),
    lambda a: a["disposition_groups"][1].update(observation_indices=[0, 0]),
    lambda a: a["disposition_groups"][1].update(observation_indices=[True]),
    lambda a: a["disposition_groups"][1].update(verdict="no_relevant_statement_in_window"),
    lambda a: a.update(codec_version="corpus-groups-v2"),
    lambda a: a.update(invented="field"),
    lambda a: a.pop("codec_version"),
])
def test_malformed_or_incomplete_wire_never_becomes_a_judgment(mutation):
    answer = wire()
    mutation(answer)
    with pytest.raises(JudgeContractError):
        decode(answer, request())


def test_unique_json_keys_and_exact_distinct_reasons_are_preserved():
    data, answer = request(), wire()
    answer["reason_pool"].append("A different claim-specific reason.")
    answer["disposition_groups"][0]["claim_indices"].remove(2)
    answer["disposition_groups"].insert(0, {"claim_indices": [2],
        "verdict": "no_relevant_statement_in_window", "observation_indices": [], "reason_index": 3})
    normalized = decode(answer, data)
    assert normalized["claim_dispositions"]["immutable-claim-2"]["reason"] != normalized["claim_dispositions"]["immutable-claim-3"]["reason"]
    raw = json.dumps(answer)
    duplicate = raw.replace('"coverage_complete": true', '"coverage_complete": true, "coverage_complete": true')
    with pytest.raises(JudgeContractError):
        _normalize_provider_answer("corpus", duplicate, data)


def test_provider_sends_full_original_data_and_wire_schema_with_same_output_reservation(monkeypatch):
    import pipeline.governance as governance
    data, answer, calls = request(), wire(), []
    @contextmanager
    def client(**settings):
        def create(**kwargs):
            calls.append((settings, kwargs))
            return SimpleNamespace(status="completed", output_text=json.dumps(answer))
        yield SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(governance, "openai_client", client)
    normalized = _provider("transport-only-test", phase="corpus", data=data)("instructions", "ignored")
    settings, kwargs = calls[0]
    assert settings == {"timeout": 300, "max_retries": 0}
    assert kwargs["max_output_tokens"] == 16384
    assert kwargs["text"]["format"]["schema"] == _corpus_wire_schema(data)
    assert len(normalized["claim_dispositions"]) == 482
    prompt = kwargs["input"]
    for claim in data["claims"]:
        assert claim["claim_id"] in prompt and claim["text"] in prompt
    for span in data["quote_spans"]:
        assert span["text"] in prompt
    assert "corpus-groups-v1" in prompt
    assert "exactly once" in prompt
    assert prompt == _provider_prompt("corpus", data)
    assert len(json.dumps(_corpus_wire_schema(data))) < len(json.dumps(_corpus_schema(data))) / 10
