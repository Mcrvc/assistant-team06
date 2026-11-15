"""Unit + integration tests for TTS only.
STT is now handled by the browser Web Speech API — no backend endpoint.
"""
from __future__ import annotations

import io
import wave
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def _make_mp3_bytes() -> bytes:
    return b"\xff\xfb\x90\x00" + b"\x00" * 100

def _make_wav_response_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path):
    from assistant.interviews import InterviewService
    from assistant.interview_ai import MockInterviewAI
    from assistant.interview_store import SQLAlchemyInterviewRepository
    from assistant.user_api import InMemoryProfileStore
    from assistant.web import create_app
    app = create_app(
        service=InterviewService(
            SQLAlchemyInterviewRepository.local(tmp_path / "voice_test.sqlite"),
            MockInterviewAI(),
        ),
        auth_resolver=lambda _req: "test-user-001",
        profile_store=InMemoryProfileStore(),
    )
    return TestClient(app, raise_server_exceptions=False)


# ── TTS unit tests ────────────────────────────────────────────────────

class TestSynthesizeUnit:

    def test_uses_edge_tts_when_no_magpie_credentials(self, monkeypatch):
        monkeypatch.setenv("MAGPIE_NVIDIA_API_KEY", "")
        monkeypatch.setenv("MAGPIE_FUNCTION_ID", "")
        monkeypatch.setattr("assistant.voice.tts._edge_synthesize", lambda t, l: _make_mp3_bytes())
        from assistant.voice.tts import synthesize
        _, mime = synthesize("Hello")
        assert mime == "audio/mpeg"

    def test_uses_edge_tts_when_placeholder_key(self, monkeypatch):
        monkeypatch.setenv("MAGPIE_NVIDIA_API_KEY", "insert_your_key_here")
        monkeypatch.setenv("MAGPIE_FUNCTION_ID", "some-id")
        monkeypatch.setattr("assistant.voice.tts._edge_synthesize", lambda t, l: _make_mp3_bytes())
        from assistant.voice.tts import synthesize
        _, mime = synthesize("Hello")
        assert mime == "audio/mpeg"

    def test_uses_magpie_when_credentials_present(self, monkeypatch):
        monkeypatch.setenv("MAGPIE_NVIDIA_API_KEY", "nvapi-real-key")
        monkeypatch.setenv("MAGPIE_FUNCTION_ID", "real-func-id")
        fake_wav = _make_wav_response_bytes()
        monkeypatch.setattr("assistant.voice.tts._magpie_synthesize", lambda t, v, l: fake_wav)
        from assistant.voice.tts import synthesize
        audio, mime = synthesize("Hello")
        assert mime == "audio/wav"
        assert audio == fake_wav

    def test_falls_back_to_edge_tts_when_magpie_raises(self, monkeypatch):
        monkeypatch.setenv("MAGPIE_NVIDIA_API_KEY", "nvapi-real-key")
        monkeypatch.setenv("MAGPIE_FUNCTION_ID", "real-func-id")
        monkeypatch.setattr("assistant.voice.tts._magpie_synthesize",
                            lambda *_: (_ for _ in ()).throw(ConnectionError("gRPC down")))
        monkeypatch.setattr("assistant.voice.tts._edge_synthesize", lambda t, l: _make_mp3_bytes())
        from assistant.voice.tts import synthesize
        _, mime = synthesize("Hello")
        assert mime == "audio/mpeg"

    def test_synthesize_passes_lang_to_edge_tts(self, monkeypatch):
        monkeypatch.setenv("MAGPIE_NVIDIA_API_KEY", "")
        monkeypatch.setenv("MAGPIE_FUNCTION_ID", "")
        received = {}
        def fake_edge(text, lang):
            received["lang"] = lang
            return _make_mp3_bytes()
        monkeypatch.setattr("assistant.voice.tts._edge_synthesize", fake_edge)
        from assistant.voice.tts import synthesize
        synthesize("Xin chào", lang="vi")
        assert received["lang"] == "vi"

    def test_edge_synthesize_selects_correct_voice(self, monkeypatch):
        called_with = {}
        async def fake_stream(self):
            yield {"type": "audio", "data": b"\x00\x01"}
        class FakeCommunicate:
            def __init__(self, text, voice):
                called_with["voice"] = voice
            stream = fake_stream
        import edge_tts as _edge_tts_mod
        monkeypatch.setattr(_edge_tts_mod, "Communicate", FakeCommunicate)
        from assistant.voice.tts import _edge_synthesize
        _edge_synthesize("test", "vi")
        assert called_with["voice"] == "vi-VN-HoaiMyNeural"
        _edge_synthesize("test", "en")
        assert called_with["voice"] == "en-US-AriaNeural"

    def test_synthesize_returns_non_empty_bytes(self, monkeypatch):
        monkeypatch.setenv("MAGPIE_NVIDIA_API_KEY", "")
        monkeypatch.setenv("MAGPIE_FUNCTION_ID", "")
        monkeypatch.setattr("assistant.voice.tts._edge_synthesize", lambda t, l: _make_mp3_bytes())
        from assistant.voice.tts import synthesize
        audio, _ = synthesize("Hello world")
        assert len(audio) > 0


# ── TTS endpoint integration tests ───────────────────────────────────

class TestTtsEndpoint:

    def test_returns_200_with_audio_wav(self, client, monkeypatch):
        fake_wav = _make_wav_response_bytes()
        monkeypatch.setattr("assistant.voice.tts.synthesize",
                            lambda text, lang="en", **_: (fake_wav, "audio/wav"))
        resp = client.post("/api/tts", json={"text": "Hello"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert resp.content == fake_wav

    def test_returns_200_with_audio_mpeg_fallback(self, client, monkeypatch):
        monkeypatch.setattr("assistant.voice.tts.synthesize",
                            lambda text, lang="en", **_: (_make_mp3_bytes(), "audio/mpeg"))
        resp = client.post("/api/tts", json={"text": "Hello"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/mpeg"

    def test_forwards_lang_parameter(self, client, monkeypatch):
        received = {}
        def capture(text, lang="en", **_):
            received["lang"] = lang
            return _make_mp3_bytes(), "audio/mpeg"
        monkeypatch.setattr("assistant.voice.tts.synthesize", capture)
        client.post("/api/tts", json={"text": "Xin chào", "lang": "vi"})
        assert received["lang"] == "vi"

    def test_defaults_lang_to_en(self, client, monkeypatch):
        received = {}
        def capture(text, lang="en", **_):
            received["lang"] = lang
            return _make_mp3_bytes(), "audio/mpeg"
        monkeypatch.setattr("assistant.voice.tts.synthesize", capture)
        client.post("/api/tts", json={"text": "Hello"})
        assert received["lang"] == "en"

    def test_returns_502_when_synthesize_raises(self, client, monkeypatch):
        def crash(text, lang="en", **_):
            raise RuntimeError("edge-tts network error")
        monkeypatch.setattr("assistant.voice.tts.synthesize", crash)
        resp = client.post("/api/tts", json={"text": "Hello"})
        assert resp.status_code == 502
        assert "TTS error" in resp.json()["detail"]

    def test_missing_text_field_returns_4xx(self, client):
        resp = client.post("/api/tts", json={})
        assert 400 <= resp.status_code < 500

    def test_empty_text_does_not_crash_endpoint(self, client, monkeypatch):
        monkeypatch.setattr("assistant.voice.tts.synthesize",
                            lambda text, lang="en", **_: (_make_mp3_bytes(), "audio/mpeg"))
        resp = client.post("/api/tts", json={"text": ""})
        assert resp.status_code == 200

    def test_error_detail_contains_exception_message(self, client, monkeypatch):
        def crash(text, lang="en", **_):
            raise ValueError("specific failure reason")
        monkeypatch.setattr("assistant.voice.tts.synthesize", crash)
        resp = client.post("/api/tts", json={"text": "Hello"})
        assert "specific failure reason" in resp.json()["detail"]

    def test_stt_endpoint_no_longer_exists(self, client):
        """POST /api/stt must be gone — STT moved to browser Web Speech API."""
        resp = client.post("/api/stt",
                           files={"audio": ("clip.wav", b"data", "audio/wav")})
        assert resp.status_code == 404
