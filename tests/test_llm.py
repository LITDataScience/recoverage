import argparse
import json
import urllib.request

from recoverage.cli import _llm_mode, main
from recoverage.llm import OpenAICompatibleClient, client_from_env, enrich_gaps
from recoverage.models import Gap


def test_cli_stays_offline_when_a_key_is_set(monkeypatch):
    monkeypatch.setenv("RECOVERAGE_LLM_API_KEY", "secret")
    assert _llm_mode(argparse.Namespace(llm=False, no_llm=False)) == "off"
    assert _llm_mode(argparse.Namespace(llm=True, no_llm=False)) == "on"
    assert _llm_mode(argparse.Namespace(llm=False, no_llm=True)) == "off"
    assert main(["run", ".", "--llm", "--no-llm"]) == 2


def test_http_base_url_is_rejected_unless_loopback(monkeypatch):
    monkeypatch.setenv("RECOVERAGE_LLM_API_KEY", "secret")
    monkeypatch.setenv("RECOVERAGE_LLM_BASE_URL", "http://example.test/v1")
    try:
        client_from_env(mode="on")
    except RuntimeError as exc:
        assert "https" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
    monkeypatch.setenv("RECOVERAGE_LLM_BASE_URL", "http://127.0.0.1:9/v1")
    client = client_from_env(mode="on")
    assert client.base_url == "http://127.0.0.1:9/v1"


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


def test_auto_with_key_stays_offline(monkeypatch):
    monkeypatch.setenv("RECOVERAGE_LLM_API_KEY", "secret")
    assert client_from_env(mode="auto") is None


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

            def read(self, _n=-1):
                return body

        return _Response()

    class _Opener:
        def open(self, request, timeout=0):
            return fake_urlopen(request, timeout)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args, **kwargs: _Opener())
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
    class _Opener:
        def open(self, request, timeout=0):
            raise urllib.error.URLError("down")

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args, **kwargs: _Opener())
    client = OpenAICompatibleClient(api_key="secret", base_url="https://example.test/v1")
    gaps = [Gap("G01", "high", "untested-function", "title", "original", "a.py", "charge", "suggest", False)]
    enriched, name = enrich_gaps(gaps, client)
    assert name == "heuristic-fallback"
    assert enriched[0].why == "original"
    assert any(gap.kind == "llm-error" for gap in enriched)


import urllib.error  # noqa: E402
