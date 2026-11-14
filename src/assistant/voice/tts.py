from __future__ import annotations
import asyncio
import io
import os
import wave
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()
SAMPLE_RATE = 44100

# ── Magpie (NVIDIA Riva) ──────────────────────────────────────────────
@lru_cache
def _magpie_service():
    import riva.client
    api_key  = os.environ["MAGPIE_NVIDIA_API_KEY"]
    func_id  = os.environ["MAGPIE_FUNCTION_ID"]
    auth = riva.client.Auth(
        use_ssl=True,
        uri="grpc.nvcf.nvidia.com:443",
        metadata_args=[
            ["function-id", func_id],
            ["authorization", f"Bearer {api_key}"],
        ],
    )
    return riva.client.SpeechSynthesisService(auth)

def _magpie_synthesize(text: str, voice: str, lang: str) -> bytes:
    import riva.client
    svc  = _magpie_service()
    resp = svc.synthesize(
        text,
        voice_name=voice,
        language_code=lang,
        sample_rate_hz=SAMPLE_RATE,
        encoding=riva.client.AudioEncoding.LINEAR_PCM,
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(resp.audio)
    return buf.getvalue()

# ── Edge TTS fallback ─────────────────────────────────────────────────
async def _edge_synthesize_async(text: str, voice: str) -> bytes:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()

def _edge_synthesize(text: str, lang: str) -> bytes:
    voice = "vi-VN-HoaiMyNeural" if lang == "vi" else "en-US-AriaNeural"
    return asyncio.run(_edge_synthesize_async(text, voice))

# ── Public API ────────────────────────────────────────────────────────
def synthesize(
    text: str,
    lang: str = "en",
    magpie_voice: str = "Magpie-Multilingual.EN-US.Aria",
) -> tuple[bytes, str]:
    """
    Returns (audio_bytes, mime_type).
    Tries Magpie first; falls back to edge-tts if credentials are missing or call fails.
    """
    api_key = os.environ.get("MAGPIE_NVIDIA_API_KEY", "")
    func_id = os.environ.get("MAGPIE_FUNCTION_ID", "")

    if api_key and api_key not in ("insert_your_key_here", "") \
            and func_id and func_id not in ("", ):
        try:
            audio = _magpie_synthesize(text, magpie_voice, lang)
            return audio, "audio/wav"
        except Exception as e:
            print(f"[tts] Magpie failed ({e}), falling back to edge-tts")

    audio = _edge_synthesize(text, lang)
    return audio, "audio/mpeg"
