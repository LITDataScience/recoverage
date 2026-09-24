import io
import json
import urllib.request

from recoverage.llm import OpenAICompatibleClient, client_from_env, enrich_gaps
from recoverage.models import Gap


def test_auto_without_key_is_offline(monkeypatch):
    monkeypatch.delenv("RECOVERAGE_LLM_API_KEY", raising=False)
    assert client_from_env(mode="auto") is None
    assert client_from_env(mode="off") is None


def test_force_on_without_key_errors(monkeypatch):
    monkeypatch.delenv("RECOVERAGE_LLM_API_KEY", raising=False)
    try:
        client_from_env(mode="on")
    except RuntimeError as exc:
        assert "RECOVERAGE_LLM_API_KEY" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_client_parses_chat_completion(monkeypatch):
    def fake_urlopen(request, timeout=0):
        assert request.full_url == "https://example.test/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer secret"
        body = json.dumps({"choices": [{"message": {"content": '{"gaps":[{"id":"G01","why":"deeper","suggestion":"call it"}]}'}}]}).encode()

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return body

        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatibleClient(api_key="secret", base_url="https://example.test/v1", model="test-model")
    gaps = [
        Gap("G01", "high", "untested-function", "charge never ran", "heuristic why", "payments.py", "charge", "add a test", False)
    ]
    enriched, name = enrich_gaps(gaps, client)
    assert name == "openai-compatible"
    assert enriched[0].llm_enriched is True
    assert enriched[0].why == "deeper"
    assert enriched[0].suggestion == "call it"


def test_llm_failure_keeps_heuristic(monkeypatch):
    def fake_urlopen(request, timeout=0):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatibleClient(api_key="secret", base_url="https://example.test/v1")
    gaps = [Gap("G01", "high", "untested-function", "title", "original", "a.py", "charge", "suggest", False)]
    enriched, name = enrich_gaps(gaps, client)
    assert name == "heuristic-fallback"
    assert enriched[0].why == "original"
    assert any(gap.kind == "llm-error" for gap in enriched)


import urllib.error  # noqa: E402
