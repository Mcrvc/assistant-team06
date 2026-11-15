"""Unit + integration tests for voice STT and TTS (offline, no real API calls)."""
from __future__ import annotations

import io
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    return buf.getvalue()

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


# ── STT unit tests ────────────────────────────────────────────────────────────

class TestTranscribeUnit:

    def test_returns_string_on_success(self, monkeypatch):
        fake_model = MagicMock()
        fake_model.transcribe.return_value = {"text": "  Hello world  "}
        monkeypatch.setattr("assistant.voice.stt._model", fake_model)
        from assistant.voice.stt import transcribe
        assert transcribe(_make_wav_bytes()) == "Hello world"
        fake_model.transcribe.assert_called_once()

    def test_strips_whitespace(self, monkeypatch):
        fake_model = MagicMock()
        fake_model.transcribe.return_value = {"text": "\n  trailing spaces \t"}
        monkeypatch.setattr("assistant.voice.stt._model", fake_model)
        from assistant.voice.stt import transcribe
        assert transcribe(b"audio") == "trailing spaces"

    def test_returns_empty_string_for_silence(self, monkeypatch):
        fake_model = MagicMock()
        fake_model.transcribe.return_value = {"text": ""}
        monkeypatch.setattr("assistant.voice.stt._model", fake_model)
        from assistant.voice.stt import transcribe
        assert transcribe(_make_wav_bytes()) == ""

    def test_passes_language_when_given(self, monkeypatch):
        fake_model = MagicMock()
        fake_model.transcribe.return_value = {"text": "xin chào"}
        monkeypatch.setattr("assistant.voice.stt._model", fake_model)
        from assistant.voice.stt import transcribe
        result = transcribe(b"audio", language="vi")
        assert result == "xin chào"
        _, kwargs = fake_model.transcribe.call_args
        assert kwargs.get("language") == "vi"

    def test_no_language_arg_when_none(self, monkeypatch):
        fake_model = MagicMock()
        fake_model.transcribe.return_value = {"text": "hi"}
        monkeypatch.setattr("assistant.voice.stt._model", fake_model)
        from assistant.voice.stt import transcribe
        transcribe(b"audio", language=None)
        _, kwargs = fake_model.transcribe.call_args
        assert "language" not in kwargs

    def test_temp_file_deleted_on_success(self, monkeypatch):
        created = []
        fake_model = MagicMock()
        fake_model.transcribe.return_value = {"text": "ok"}
        monkeypatch.setattr("assistant.voice.stt._model", fake_model)
        import tempfile as _tempfile
        original_ntf = _tempfile.NamedTemporaryFile
        def tracking_ntf(*a, **kw):
            f = original_ntf(*a, **kw)
            created.append(f.name)
            return f
        monkeypatch.setattr("assistant.voice.stt.tempfile.NamedTemporaryFile", tracking_ntf)
        from assistant.voice.stt import transcribe
        transcribe(b"audio")
        for path in created:
            assert not Path(path).exists()

    def test_temp_file_deleted_on_model_error(self, monkeypatch):
        created = []
        fake_model = MagicMock()
        fake_model.transcribe.side_effect = RuntimeError("model crash")
        monkeypatch.setattr("assistant.voice.stt._model", fake_model)
        import tempfile as _tempfile
        original_ntf = _tempfile.NamedTemporaryFile
        def tracking_ntf(*a, **kw):
            f = original_ntf(*a, **kw)
            created.append(f.name)
            return f
        monkeypatch.setattr("assistant.voice.stt.tempfile.NamedTemporaryFile", tracking_ntf)
        from assistant.voice.stt import transcribe
        with pytest.raises(RuntimeError, match="model crash"):
            transcribe(b"audio")
        for path in created:
            assert not Path(path).exists()

    def test_model_loaded_lazily_and_cached(self, monkeypatch):
        load_calls = []
        def fake_load(name):
            load_calls.append(name)
            m = MagicMock()
            m.transcribe.return_value = {"text": ""}
            return m
        monkeypatch.setattr("assistant.voice.stt._model", None)
        monkeypatch.setattr("assistant.voice.stt.whisper.load_model", fake_load)
        from assistant.voice import stt
        stt.transcribe(b"a")
        stt.transcribe(b"b")
        assert len(load_calls) == 1
        assert load_calls[0] == "base"


# ── TTS unit tests ────────────────────────────────────────────────────────────

class TestSynthesizeUnit:

    def test_uses_edge_tts_when_no_magpie_credentials(self, monkeypatch):
        monkeypatch.setenv("MAGPIE_NVIDIA_API_KEY", "")
        monkeypatch.setenv("MAGPIE_FUNCTION_ID", "")
        fake_audio = _make_mp3_bytes()
        monkeypatch.setattr("assistant.voice.tts._edge_synthesize", lambda text, lang: fake_audio)
        from assistant.voice.tts import synthesize
        audio, mime = synthesize("Hello")
        assert mime == "audio/mpeg"
        assert audio == fake_audio

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
        fake_audio = _make_mp3_bytes()
        monkeypatch.setattr("assistant.voice.tts._edge_synthesize", lambda t, l: fake_audio)
        from assistant.voice.tts import synthesize
        audio, mime = synthesize("Hello")
        assert mime == "audio/mpeg"
        assert audio == fake_audio

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
        """_edge_synthesize passes correct voice name to edge_tts.Communicate."""
        # FIX: monkeypatch the module-level edge_tts import inside tts.py,
        # not the dotted path "assistant.voice.tts.edge_tts" which fails
        # because tts.py uses `import edge_tts` inside the async function.
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


# ── STT endpoint integration tests ───────────────────────────────────────────

class TestSttEndpoint:

    def test_returns_200_with_text_field(self, client, monkeypatch):
        monkeypatch.setattr("assistant.voice.stt.transcribe", lambda a, language=None: "test transcript")
        resp = client.post("/api/stt", files={"audio": ("clip.wav", _make_wav_bytes(), "audio/wav")})
        assert resp.status_code == 200
        assert resp.json() == {"text": "test transcript"}

    def test_returns_empty_string_for_silence(self, client, monkeypatch):
        monkeypatch.setattr("assistant.voice.stt.transcribe", lambda a, language=None: "")
        resp = client.post("/api/stt", files={"audio": ("silent.wav", _make_wav_bytes(), "audio/wav")})
        assert resp.status_code == 200
        assert resp.json()["text"] == ""

    def test_returns_500_when_transcribe_raises(self, client, monkeypatch):
        # FIX: router has no try/except around stt.transcribe so FastAPI
        # propagates the exception as 500. TestClient must have
        # raise_server_exceptions=False (set in fixture) to read the response.
        def crash(audio, language=None):
            raise RuntimeError("whisper exploded")
        monkeypatch.setattr("assistant.voice.stt.transcribe", crash)
        resp = client.post("/api/stt", files={"audio": ("clip.wav", b"bad data", "audio/wav")})
        assert resp.status_code == 500

    def test_accepts_webm_mimetype(self, client, monkeypatch):
        monkeypatch.setattr("assistant.voice.stt.transcribe", lambda a, language=None: "webm transcript")
        resp = client.post("/api/stt", files={"audio": ("clip.webm", b"fake webm", "audio/webm")})
        assert resp.status_code == 200
        assert resp.json()["text"] == "webm transcript"

    def test_missing_audio_field_returns_4xx(self, client):
        # FIX: web.py has a custom RequestValidationError handler that returns
        # 400 instead of FastAPI's default 422. Assert 4xx range instead.
        resp = client.post("/api/stt")
        assert 400 <= resp.status_code < 500

    def test_audio_bytes_forwarded_to_transcribe(self, client, monkeypatch):
        received = {}
        def capture(audio, language=None):
            received["audio"] = audio
            return "ok"
        monkeypatch.setattr("assistant.voice.stt.transcribe", capture)
        payload = b"my audio bytes"
        client.post("/api/stt", files={"audio": ("clip.wav", payload, "audio/wav")})
        assert received["audio"] == payload


# ── TTS endpoint integration tests ───────────────────────────────────────────

class TestTtsEndpoint:

    def test_returns_200_with_audio_wav(self, client, monkeypatch):
        fake_wav = _make_wav_response_bytes()
        monkeypatch.setattr("assistant.voice.tts.synthesize", lambda text, lang="en", **_: (fake_wav, "audio/wav"))
        resp = client.post("/api/tts", json={"text": "Hello"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert resp.content == fake_wav

    def test_returns_200_with_audio_mpeg_fallback(self, client, monkeypatch):
        fake_mp3 = _make_mp3_bytes()
        monkeypatch.setattr("assistant.voice.tts.synthesize", lambda text, lang="en", **_: (fake_mp3, "audio/mpeg"))
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
        # FIX: same as STT — custom handler in web.py returns 400, not 422.
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
