"""Transport selection must preserve API behavior and never silently fall back."""
import pytest

from pipeline import governance
from pipeline.codex_provider import CodexChatModel, CodexClient, CodexProviderError


@pytest.fixture(autouse=True)
def reset_ledger(monkeypatch):
    monkeypatch.setattr(governance, "_ledger", None)
    monkeypatch.delenv("KV_MODEL_PROVIDER", raising=False)


def test_api_is_default_and_custom_factory_keeps_configuration():
    captured = {}
    def factory(**kwargs):
        captured.update(kwargs)
        return "api-model"
    assert governance.model_provider() == "openai_api"
    assert governance.chat_model(api_factory=factory, api_key="test-only", model="api-model",
                                 base_url="https://example.invalid/v1", timeout=60) == "api-model"
    assert captured["api_key"] == "test-only"
    assert captured["base_url"] == "https://example.invalid/v1"
    assert captured["timeout"] == 60


def test_codex_factory_uses_saved_login_without_api_key(monkeypatch):
    monkeypatch.setenv("KV_MODEL_PROVIDER", "codex_cli_chatgpt")
    client = governance.openai_client(api_key=None, timeout=120)
    assert isinstance(client, CodexClient)
    assert client.timeout == 300
    model = governance.chat_model(model="gpt-6-astra", api_key=None, base_url=None, timeout=60)
    assert isinstance(model, CodexChatModel)
    assert model.model == "gpt-6-astra"
    assert model.client.timeout == 300


def test_codex_rejects_configured_api_endpoint_instead_of_falling_back(monkeypatch):
    monkeypatch.setenv("KV_MODEL_PROVIDER", "codex_cli_chatgpt")
    with pytest.raises(CodexProviderError, match="unsupported_chat_options"):
        governance.chat_model(model="gpt-6-astra", base_url="https://example.invalid/v1")


def test_unknown_transport_is_rejected(monkeypatch):
    monkeypatch.setenv("KV_MODEL_PROVIDER", "unsupported")
    with pytest.raises(ValueError, match="Unknown KV_MODEL_PROVIDER"):
        governance.openai_client()


@pytest.mark.parametrize("request_timeout, expected", [(None, 300), (600, 600)])
def test_report_timeout_keeps_api_default_and_closes_long_request_client(monkeypatch, request_timeout, expected):
    from pathlib import Path
    from types import SimpleNamespace
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "report" / "src"))
    from report_agent.generator import ReportAgent
    captured = {}
    def factory(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text="complete report")),
                               close=lambda: captured.update(closed=True))
    monkeypatch.setattr(governance, "openai_client", factory)
    options = {} if request_timeout is None else {"request_timeout": request_timeout}
    assert ReportAgent(**options)._openai_response("instructions", "data") == "complete report"
    assert captured == {"timeout": expected, "max_retries": 0, "closed": True}
