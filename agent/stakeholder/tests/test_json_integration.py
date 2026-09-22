"""End-to-end checks of real paper fixtures, CLI and parent-State boundaries."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from stakeholder_agent import AgentConfig, make_stakeholder_node, run_stakeholder, to_state_update
from stakeholder_agent.cli import main
from stakeholder_agent.demo import DemoModel, DemoWeb
from stakeholder_agent.json_output import StakeholderOutput
from stakeholder_agent.providers import SearchHit, SourcePage

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def payload():
    return {
        "schema_version": "1.0", "run_id": "integration-test", "role": "stakeholders",
        "paper_analyses": [json.loads((ROOT / f"examples/papers/{name}.json").read_text())
                           for name in ("rdkv", "photonic-cxl")],
        "request": json.loads((ROOT / "examples/request.json").read_text()),
        "config": {"as_of": "2026-09-22"}, "round": 0,
        "budget": {"llm": 5, "search": 6, "fetch": 10},
        "usage": {"llm": 0, "search": 0, "fetch": 0},
    }


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not make network requests")
    monkeypatch.setattr("httpx.Client.request", blocked)
    monkeypatch.setattr("httpx.Client.stream", blocked)


def test_real_paper_pair_is_preserved_and_returns_valid_json(payload):
    before = deepcopy(payload)
    output = run_stakeholder(payload, mode="fixture")
    StakeholderOutput.model_validate_json(json.dumps(output))
    assert payload == before
    original = {e["evidence_id"]: e for p in payload["paper_analyses"] for e in p["evidence_registry"]}
    assert len(original) == len(output["evidence"]) == 25
    for eid, record in original.items():
        assert output["evidence"][eid]["excerpt"] == record["snippet"]
        assert output["evidence"][eid]["upstream"] == record
    assert output["mode"] == "fixture"
    assert output["result"]["details"]["runtime"]["model"] == "fixture:DemoModel"
    assert output["status"] == "partial"
    assert output["execution_status"] == "completed"
    assert output["evidence_status"] == "limited"
    assert output["usage"]["used"]["llm"] == 3
    assert output["new_evidence"] == {}
    claims = [c for t in output["result"]["by_technology"].values() for c in t["claims"]]
    assert claims and all(c["kind"] == "paper_report" for c in claims)
    assert {r["evidence_id"] for r in output["references"]} == {e for c in claims for e in c["evidence_ids"]}


def test_api_accepts_reversed_two_papers_and_separate_context(payload):
    request = payload["request"]
    request["additional_context"] = "고객 SLA와 요금 관점을 추가로 확인해줘."
    output = run_stakeholder(list(reversed(payload["paper_analyses"])), request=request,
                             as_of="2026-09-22", run_id="separate", mode="fixture")
    assert output["run_id"] == "separate"
    assert output["result"]["details"]["request"]["additional_context"] == request["additional_context"]
    selected = output["result"]["details"]["selected_stakeholders"]
    assert len(selected) == 1 and selected[0]["id"] == "operator"
    assert "운영 조직" in selected[0]["name"]
    assert set(output["result"]["by_technology"]) == {"SW-01", "HW-01"}


def test_missing_request_returns_json_without_calling_providers(payload):
    class NeverModel:
        def generate(self, **kwargs):
            raise AssertionError("Invalid input must not call a model")
    result = run_stakeholder(payload["paper_analyses"], model=NeverModel(), web=DemoWeb())
    assert result["status"] == result["execution_status"] == "failed"
    assert result["usage"]["used"] == {"llm": 0, "search": 0, "fetch": 0}
    assert result["errors"]
    StakeholderOutput.model_validate(result)


def test_large_separate_request_is_rejected_before_model(payload):
    request = deepcopy(payload["request"])
    request["additional_context"] = "x" * 100_000
    output = run_stakeholder(payload["paper_analyses"], request=request, mode="fixture")
    assert output["status"] == "failed"
    assert output["usage"]["used"]["llm"] == 0


def test_parent_state_delta_does_not_mutate_other_roles(payload):
    state = {"paper_analyses": payload["paper_analyses"], "request": payload["request"],
             "run_id": "parent-run", "config": {"as_of": "2026-09-22", "budgets": {
                 "stakeholders": payload["budget"]}},
             "usage": {"stakeholders": payload["usage"], "market": {"llm": 4}},
             "assessments": {"market": {"untouched": True}}, "review": {"round": 1}}
    before = deepcopy(state)
    delta = make_stakeholder_node(mode="fixture")(state)
    assert state == before
    assert set(delta) == {"assessments", "evidence", "usage", "errors"}
    assert set(delta["assessments"]) == {"stakeholders"}
    assert delta["assessments"]["stakeholders"]["round"] == 1
    assert set(delta["usage"]) == {"stakeholders"}
    assert delta["evidence"] == {}  # upstream registry belongs to the parent
    assert delta["usage"]["stakeholders"]["llm"] == 3


def test_cumulative_usage_is_not_reset_by_upper_round(payload):
    first = run_stakeholder(payload, mode="fixture")
    payload["usage"] = first["usage"]["used"]
    payload["round"] = 1
    second = run_stakeholder(payload, mode="fixture")
    assert second["round"] == 1
    assert second["usage"]["used"]["llm"] == 5
    assert second["usage"]["delta"]["llm"] == 2
    assert second["usage"]["remaining"]["llm"] == 0
    assert second["execution_status"] == "failed"  # cannot complete semantic review
    assert not any(t["claims"] for t in second["result"]["by_technology"].values())


def test_web_evidence_ids_do_not_collide_across_upper_rounds(payload):
    class Web:
        def search(self, query, max_results=3):
            return [SearchHit(url="https://example.org/rdkv", title="RDKV Photonic-CXL test")]
        def fetch(self, url):
            return SourcePage(url=url, title="RDKV Photonic-CXL test",
                              text="RDKV and Photonic-CXL need deployment validation in real serving.")
    first = run_stakeholder(payload, model=DemoModel(), web=Web(), mode="fixture")
    payload["round"] = 1
    second = run_stakeholder(payload, model=DemoModel(), web=Web(), mode="fixture")
    assert first["new_evidence"] and second["new_evidence"]
    assert not set(first["new_evidence"]) & set(second["new_evidence"])
    assert to_state_update(second)["evidence"] == second["new_evidence"]


def test_json_cli_with_actual_input_pair(tmp_path, capsys):
    output = tmp_path / "subdir" / "output.json"
    assert main(["--papers", str(ROOT / "examples/papers/rdkv.json"),
                 str(ROOT / "examples/papers/photonic-cxl.json"),
                 "--request", str(ROOT / "examples/request.json"), "--as-of", "2026-09-22",
                 "--demo", "--output", str(output)]) == 0
    assert capsys.readouterr().out == ""
    assert json.loads(output.read_text())["mode"] == "fixture"


def test_cli_duplicate_keys_rejected_without_execution(tmp_path, capsys):
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":"2.0", "schema_version":"1.0"}')
    assert main(["--input", str(path), "--demo"]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "InputError" in captured.err


def test_cli_failure_is_json_for_structurally_invalid_input(tmp_path, capsys):
    path = tmp_path / "missing.json"
    path.write_text('{}')
    assert main(["--input", str(path), "--demo"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_config_model_in_envelope_reaches_provider_configuration(payload, monkeypatch):
    models = []
    from stakeholder_agent import providers
    class Provider(DemoModel):
        def __init__(self, *, model, **kwargs):
            models.append(model)
    monkeypatch.setattr(providers, "OpenAIModel", Provider)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-never-sent")
    payload["config"]["model"] = "configured-model"
    result = run_stakeholder(payload, web=DemoWeb())
    assert models == ["configured-model"]
    assert result["result"]["details"]["runtime"]["model"] == "configured-model"
    assert "test-only-never-sent" not in json.dumps(result)


def test_input_config_cannot_override_explicit_call_configuration(payload, monkeypatch):
    payload["config"]["model"] = "envelope-model"
    output = run_stakeholder(payload, config=AgentConfig(model="caller-model"), mode="fixture")
    assert output["result"]["details"]["runtime"]["model"] == "fixture:DemoModel"


def test_invalid_request_keeps_parent_accounting_and_identity(payload):
    del payload["request"]["original_request"]
    previous = {"llm": 4, "search": 6, "fetch": 5}
    payload.update(usage=previous, round=1)
    output = run_stakeholder(payload, mode="fixture")
    assert output["status"] == "failed"
    assert output["run_id"] == "integration-test"
    assert output["round"] == 1
    assert output["usage"]["used"] == previous
    assert output["usage"]["delta"] == {"llm": 0, "search": 0, "fetch": 0}
    state = {"paper_analyses": payload["paper_analyses"], "request": payload["request"],
             "run_id": payload["run_id"], "config": payload["config"],
             "usage": {"stakeholders": previous}, "review": {"round": 1}}
    delta = make_stakeholder_node(mode="fixture")(state)
    assert delta["usage"]["stakeholders"] == previous
    assert delta["assessments"]["stakeholders"]["round"] == 1
    assert all(error["round"] == 1 for error in delta["errors"].values())


def test_fatal_model_authentication_error_skips_web_search(payload):
    from stakeholder_agent.providers import ProviderError
    class AuthModel:
        def generate(self, **kwargs):
            raise ProviderError("모델 API 인증 오류", fatal=True)
    class NeverWeb:
        def search(self, *args, **kwargs):
            raise AssertionError("No paid searches after fatal model authentication failure")
    output = run_stakeholder(payload, model=AuthModel(), web=NeverWeb())
    assert output["status"] == "failed"
    assert output["usage"]["used"] == {"llm": 1, "search": 0, "fetch": 0}
    assert "research" not in output["result"]["details"]["runtime"]["trace"]
    assert "인증" in output["errors"][0]["message"]


def test_cli_invalid_runtime_config_does_not_traceback(tmp_path, payload, capsys):
    payload["config"]["model_timeout"] = "not-a-number"
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload))
    assert main(["--input", str(path), "--demo"]) == 2
    assert "ValidationError" in capsys.readouterr().err
