"""Offline tests for /api/tts Edge TTS endpoint."""

from __future__ import annotations

import sys
import types

from fastapi.testclient import TestClient

from assistant.interview_ai import MockInterviewAI
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewService
from assistant.tts import clear_tts_cache
from assistant.web import create_app


def _make_client(tmp_path) -> tuple[TestClient, SQLAlchemyInterviewRepository]:
    store = SQLAlchemyInterviewRepository.local(tmp_path / "tts.sqlite")
    service = InterviewService(store, MockInterviewAI())
    app = create_app(service=service, auth_resolver=lambda _req: "user-1")
    return TestClient(app), store


def test_tts_streams_and_caches_mp3(monkeypatch, tmp_path) -> None:
    clear_tts_cache()
    calls: list[tuple[str, str, str]] = []

    class FakeCommunicate:
        def __init__(self, text: str, voice: str, rate: str = "+0%") -> None:
            calls.append((text, voice, rate))

        async def stream(self):
            yield {"type": "WordBoundary", "text": "Hello"}
            yield {"type": "audio", "data": b"ID3"}
            yield {"type": "audio", "data": b"MP3DATA"}

    fake_module = types.SimpleNamespace(Communicate=FakeCommunicate)
    monkeypatch.setitem(sys.modules, "edge_tts", fake_module)

    client, store = _make_client(tmp_path)
    try:
        with client:
            first = client.get("/api/tts", params={"text": "Hello world"})
            assert first.status_code == 200
            assert first.headers["content-type"].startswith("audio/mpeg")
            assert first.headers["x-tts-cache"] == "MISS"
            assert first.content == b"ID3MP3DATA"
            assert calls == [("Hello world", "en-US-AnaNeural", "+0%")]

            second = client.get("/api/tts", params={"text": "Hello world"})
            assert second.status_code == 200
            assert second.headers["x-tts-cache"] == "HIT"
            assert second.content == b"ID3MP3DATA"
            assert len(calls) == 1
    finally:
        store.close()


def test_tts_rejects_invalid_params(tmp_path) -> None:
    clear_tts_cache()
    client, store = _make_client(tmp_path)
    try:
        with client:
            assert client.get("/api/tts", params={"text": "   "}).status_code == 400
            assert client.get("/api/tts", params={"text": "Hi", "voice": "bad-voice"}).status_code == 400
            assert client.get("/api/tts", params={"text": "Hi", "rate": "fast"}).status_code == 400
    finally:
        store.close()


def test_tts_returns_502_when_upstream_fails(monkeypatch, tmp_path) -> None:
    clear_tts_cache()

    class FailingCommunicate:
        def __init__(self, text: str, voice: str, rate: str = "+0%") -> None:
            pass

        async def stream(self):
            raise RuntimeError("upstream 403")
            yield  # pragma: no cover

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=FailingCommunicate))

    client, store = _make_client(tmp_path)
    try:
        with client:
            res = client.get("/api/tts", params={"text": "Hello"})
            assert res.status_code == 502
    finally:
        store.close()


def test_tts_returns_502_when_upstream_returns_empty_audio(monkeypatch, tmp_path) -> None:
    clear_tts_cache()

    class EmptyAudioCommunicate:
        def __init__(self, text: str, voice: str, rate: str = "+0%") -> None:
            pass

        async def stream(self):
            yield {"type": "WordBoundary", "text": "Hello"}

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=EmptyAudioCommunicate))

    client, store = _make_client(tmp_path)
    try:
        with client:
            res = client.get("/api/tts", params={"text": "Hello"})
            assert res.status_code == 502
    finally:
        store.close()


def test_tts_returns_503_when_edge_tts_missing(monkeypatch, tmp_path) -> None:
    clear_tts_cache()
    monkeypatch.setitem(sys.modules, "edge_tts", None)

    client, store = _make_client(tmp_path)
    try:
        with client:
            res = client.get("/api/tts", params={"text": "Hello"})
            assert res.status_code == 503
    finally:
        store.close()
