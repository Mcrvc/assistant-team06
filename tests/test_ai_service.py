"""Tests for the AI service framework (``assistant.ai``).

The provider layer is exercised with a stubbed HTTP layer, so these tests run
offline and never touch NVIDIA or TinyFish. They cover the contract in
``docs/ai-interface.md`` plus the parts added by the real implementation:
config resolution, retry policy, web search, webfetch, and the fallback chain.
"""
from __future__ import annotations

import json
import os
import urllib.error
from pathlib import Path

import pytest

from assistant import ai
from assistant.ai import (
    AiAnswer,
    AiConfigError,
    AiError,
    AiResponseError,
    AiTimeoutError,
    AiUnavailableError,
    ContextChunk,
    Message,
    answer,
    call_with_retry,
    complete,
    fetch_page,
    get_config,
    reset_config_cache,
    search_web,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, status: int, body, headers: dict | None = None):
        self.status = status
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def stub_http(monkeypatch, handler):
    """Route urllib.request.urlopen to ``handler``."""
    monkeypatch.setattr(ai.urllib.request, "urlopen", handler)


@pytest.fixture(autouse=True)
def clean_config():
    """Give every test a known config and restore the environment afterwards.

    ``ENV_CANDIDATES`` is pointed at a path that does not exist so the real,
    git-ignored ``.env`` in the repo can never leak live credentials or a live
    host into an offline test.
    """
    saved = dict(os.environ)
    os.environ.pop("NVIDIA_API_KEY", None)
    os.environ.pop("TINYFISH_API_KEY", None)
    os.environ["NVIDIA_API_KEY"] = "test-nvidia-key"
    os.environ["TINYFISH_API_KEY"] = "test-tinyfish-key"
    os.environ["AI_RETRY_DELAY_S"] = "0"  # keep the suite fast
    monkey = pytest.MonkeyPatch()
    monkey.setattr(ai, "ENV_CANDIDATES", (Path("/nonexistent/.env"),))
    reset_config_cache()
    yield
    monkey.undo()
    os.environ.clear()
    os.environ.update(saved)
    reset_config_cache()


def ok_completion(text="Answer.", model="test-model"):
    return FakeResponse(200, json.dumps({
        "model": model,
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }))


# --------------------------------------------------------------------------
# Contract from docs/ai-interface.md
# --------------------------------------------------------------------------
def test_answer_uses_llm_when_available(monkeypatch):
    stub_http(monkeypatch, lambda *a, **k: ok_completion("The office is in I.101."))
    result = answer("Where is the training office?")
    assert isinstance(result, AiAnswer)
    assert result.used_fallback is False
    assert result.text == "The office is in I.101."
    assert result.model == "test-model"
    assert result.usage is not None


def test_answer_falls_back_to_rules_on_failure(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("no network")
    stub_http(monkeypatch, boom)

    result = answer("hi")
    assert result.used_fallback is True
    assert "Hello" in result.text
    assert result.model == "stub-rules"
    assert result.error is not None


def test_answer_falls_back_to_safe_default_when_rules_fail(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("no network")
    stub_http(monkeypatch, boom)
    monkeypatch.setattr(ai, "reply", lambda *_: (_ for _ in ()).throw(OSError("no csv")))

    result = answer("where is the training office?")
    assert result.used_fallback is True
    assert "I don't know that yet" in result.text


def test_answer_rejects_bad_arguments():
    with pytest.raises(ValueError):
        answer("")
    with pytest.raises(ValueError):
        answer("   ")


def test_answer_without_key_reports_fallback(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    reset_config_cache()
    result = answer("hi")
    assert result.used_fallback is True
    assert "Hello" in result.text


def test_answer_grounds_on_context_chunks(monkeypatch):
    captured = {}

    def handler(request, *a, **k):
        captured["body"] = json.loads(request.data.decode())
        return ok_completion("Grounded.")
    stub_http(monkeypatch, handler)

    chunks = [ContextChunk(text="Training Office is in I.101.", source="data/offices.csv")]
    result = answer("Where is the Training Office?", context=chunks)
    assert result.used_fallback is False
    assert result.sources == ["data/offices.csv"]
    assert "I.101" in captured["body"]["messages"][-1]["content"]


def test_answer_includes_history(monkeypatch):
    captured = {}

    def handler(request, *a, **k):
        captured["body"] = json.loads(request.data.decode())
        return ok_completion("Followed up.")
    stub_http(monkeypatch, handler)

    answer("and on Saturday?", history=[
        Message(role="user", content="Where is the Library?"),
        Message(role="assistant", content="B.201."),
    ])
    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_value_objects_are_immutable():
    chunk = ContextChunk(text="t", source="s", score=1.0)
    with pytest.raises(Exception):
        chunk.text = "other"  # type: ignore[misc]


def test_error_hierarchy():
    for exc in (AiConfigError, AiTimeoutError, AiUnavailableError, AiResponseError):
        assert issubclass(exc, AiError)


# --------------------------------------------------------------------------
# Retry policy
# --------------------------------------------------------------------------
def test_retry_succeeds_on_second_attempt(monkeypatch):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise AiUnavailableError("blip")
        return "ok"
    monkeypatch.setattr(ai.time, "sleep", lambda *_: None)

    assert call_with_retry(flaky) == "ok"
    assert calls["n"] == 2


def test_retry_gives_up_after_two_retries(monkeypatch):
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise AiTimeoutError("slow")
    monkeypatch.setattr(ai.time, "sleep", lambda *_: None)

    with pytest.raises(AiTimeoutError):
        call_with_retry(always_fails)
    assert calls["n"] == 3  # first try + 2 retries


def test_retry_does_not_retry_config_errors():
    calls = {"n": 0}

    def bad_config():
        calls["n"] += 1
        raise AiConfigError("no key")
    with pytest.raises(AiConfigError):
        call_with_retry(bad_config)
    assert calls["n"] == 1


def test_retry_waits_between_attempts(monkeypatch):
    slept = []
    monkeypatch.delenv("AI_RETRY_DELAY_S", raising=False)  # want the default
    monkeypatch.setattr(ai.time, "sleep", lambda s: slept.append(s))

    def always_fails():
        raise AiUnavailableError("blip")
    with pytest.raises(AiUnavailableError):
        call_with_retry(always_fails)
    assert slept == [5.0, 5.0]


def test_retry_count_is_env_configurable(monkeypatch):
    monkeypatch.setenv("AI_RETRIES", "1")
    monkeypatch.setattr(ai.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise AiUnavailableError("blip")
    with pytest.raises(AiUnavailableError):
        call_with_retry(always_fails)
    assert calls["n"] == 2


# --------------------------------------------------------------------------
# Provider mapping
# --------------------------------------------------------------------------
def test_http_429_maps_to_unavailable(monkeypatch):
    def rate_limited(request, *a, **k):
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many", {},
                                     __import__("io").BytesIO(b'{"error":"slow down"}'))
    stub_http(monkeypatch, rate_limited)
    with pytest.raises(AiUnavailableError):
        complete([{"role": "user", "content": "hi"}])


def test_http_500_maps_to_unavailable(monkeypatch):
    def boom(request, *a, **k):
        raise urllib.error.HTTPError(request.full_url, 503, "down", {},
                                     __import__("io").BytesIO(b"oops"))
    stub_http(monkeypatch, boom)
    with pytest.raises(AiUnavailableError):
        complete([{"role": "user", "content": "hi"}])


def test_http_400_maps_to_response_error(monkeypatch):
    def boom(request, *a, **k):
        raise urllib.error.HTTPError(request.full_url, 400, "bad", {},
                                     __import__("io").BytesIO(b'{"error":"nope"}'))
    stub_http(monkeypatch, boom)
    with pytest.raises(AiResponseError):
        complete([{"role": "user", "content": "hi"}])


def test_empty_completion_raises(monkeypatch):
    stub_http(monkeypatch, lambda *a, **k: FakeResponse(200, json.dumps({
        "choices": [{"message": {"content": ""}, "finish_reason": "length"}]
    })))
    with pytest.raises(AiResponseError):
        complete([{"role": "user", "content": "hi"}])


def test_reasoning_model_disables_thinking(monkeypatch):
    captured = {}

    def handler(request, *a, **k):
        captured["body"] = json.loads(request.data.decode())
        return ok_completion("hi")
    stub_http(monkeypatch, handler)

    complete([{"role": "user", "content": "hi"}])
    assert captured["body"]["chat_template_kwargs"] == {"thinking": False}


def test_complete_requires_a_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    reset_config_cache()
    with pytest.raises(AiConfigError):
        complete([{"role": "user", "content": "hi"}])


# --------------------------------------------------------------------------
# Web search (TinyFish) and webfetch
# --------------------------------------------------------------------------
def test_search_web_returns_ranked_chunks(monkeypatch):
    def handler(request, *a, **k):
        assert request.headers["X-api-key"] == "test-tinyfish-key" or \
               request.headers.get("X-API-Key") == "test-tinyfish-key"
        return FakeResponse(200, json.dumps({"results": [
            {"title": "Go docs", "url": "https://go.dev/doc", "snippet": "Concurrency guide"},
            {"title": "Blog", "url": "https://blog.dev/x", "snippet": "Patterns"},
        ]}))
    stub_http(monkeypatch, handler)

    chunks = search_web("go concurrency", purpose="interview prep")
    assert len(chunks) == 2
    assert chunks[0].source == "https://go.dev/doc"
    assert chunks[0].score > chunks[1].score  # rank order preserved


def test_search_web_empty_results_is_not_an_error(monkeypatch):
    stub_http(monkeypatch, lambda *a, **k: FakeResponse(200, '{"results": []}'))
    assert search_web("nothing at all") == []


def test_search_web_requires_a_key(monkeypatch):
    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    reset_config_cache()
    with pytest.raises(AiConfigError):
        search_web("anything")


def test_search_web_rejects_empty_query():
    with pytest.raises(ValueError):
        search_web("   ")


def test_fetch_page_extracts_readable_text(monkeypatch):
    html = ("<html><head><title>x</title><style>p{color:red}</style></head>"
            "<body><h1>Heading</h1><p>Some readable paragraph text here.</p>"
            "<script>alert('no')</script></body></html>")
    stub_http(monkeypatch, lambda *a, **k: FakeResponse(200, html))

    chunk = fetch_page("https://example.com/page")
    assert chunk.source == "https://example.com/page"
    assert "readable paragraph text" in chunk.text
    assert "alert" not in chunk.text
    assert "color" not in chunk.text  # <style> dropped


def test_fetch_page_rejects_non_http(monkeypatch):
    with pytest.raises(AiResponseError):
        fetch_page("ftp://example.com")


def test_fetch_page_rejects_binary(monkeypatch):
    stub_http(monkeypatch, lambda *a, **k: FakeResponse(200, b"\x00\x01", {
        "Content-Type": "application/octet-stream"
    }))
    with pytest.raises(AiResponseError):
        fetch_page("https://example.com/file.bin")


def test_fetch_page_maps_http_error(monkeypatch):
    def boom(request, *a, **k):
        raise urllib.error.HTTPError(request.full_url, 404, "missing", {},
                                     __import__("io").BytesIO(b""))
    stub_http(monkeypatch, boom)
    with pytest.raises(AiUnavailableError):
        fetch_page("https://example.com/missing")


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
def test_environment_wins_over_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("NVIDIA_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setattr(ai, "ENV_CANDIDATES", (env_file,))
    monkeypatch.setenv("NVIDIA_API_KEY", "from-environment")
    reset_config_cache()

    assert get_config().nvidia_api_key == "from-environment"


def test_env_file_is_read_when_environment_is_empty(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("NVIDIA_API_KEY=from-file\n# comment\n\n", encoding="utf-8")
    monkeypatch.setattr(ai, "ENV_CANDIDATES", (env_file,))
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    reset_config_cache()

    assert get_config().nvidia_api_key == "from-file"


def test_placeholder_values_are_not_keys():
    for placeholder in ("fake_key", "faeke_key", "_insert_your_key_here",
                        "insert_key", "your_key", "changeme"):
        assert ai._is_real_value(placeholder) is False
    assert ai._is_real_value("sk-or-really-a-key") is True
