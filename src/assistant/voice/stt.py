from __future__ import annotations
import os
import tempfile
import whisper

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model

def transcribe(audio_bytes: bytes, language: str | None = None) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_bytes)
        path = f.name
    try:
        opts = {"language": language} if language else {}
        result = _get_model().transcribe(path, **opts)
        return result["text"].strip()
    finally:
        os.remove(path)
