"""Local Edge TTS synthesis helper with in-memory LRU cache."""

from __future__ import annotations

import hashlib
import logging
import re
from collections import OrderedDict
from typing import AsyncIterator

from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

logger = logging.getLogger(__name__)

DEFAULT_TTS_VOICE = "en-US-AnaNeural"
ALLOWED_VOICES = frozenset({
    "en-US-AnaNeural",
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
})
_RATE_RE = re.compile(r"^[+-]\d{1,2}%$")
_MAX_CACHE_ITEMS = 64
_audio_cache: OrderedDict[str, bytes] = OrderedDict()


def _cache_key(text: str, voice: str, rate: str) -> str:
    return hashlib.sha256(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()


def clear_tts_cache() -> None:
    """Clear the in-memory TTS audio cache (used by tests)."""
    _audio_cache.clear()


async def synthesize_tts_response(
    text: str,
    *,
    voice: str = DEFAULT_TTS_VOICE,
    rate: str = "+0%",
) -> Response:
    """Synthesize speech via edge-tts and return an MP3 Response or StreamingResponse."""
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="text must not be empty")
    if voice not in ALLOWED_VOICES:
        raise HTTPException(status_code=400, detail="unsupported voice")
    if not _RATE_RE.match(rate):
        raise HTTPException(status_code=400, detail="invalid rate format")

    key = _cache_key(clean_text, voice, rate)
    if key in _audio_cache:
        _audio_cache.move_to_end(key)
        return Response(
            content=_audio_cache[key],
            media_type="audio/mpeg",
            headers={"X-TTS-Cache": "HIT"},
        )

    try:
        import edge_tts
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="edge-tts is not installed") from exc

    async def stream_chunks() -> AsyncIterator[bytes]:
        communicate = edge_tts.Communicate(text=clean_text, voice=voice, rate=rate)
        chunks: list[bytes] = []
        async for message in communicate.stream():
            if message.get("type") == "audio":
                data: bytes = message["data"]
                chunks.append(data)
                yield data
        if chunks:
            _audio_cache[key] = b"".join(chunks)
            _audio_cache.move_to_end(key)
            while len(_audio_cache) > _MAX_CACHE_ITEMS:
                _audio_cache.popitem(last=False)

    try:
        generator = stream_chunks()
        first_chunk = await anext(generator, None)
    except Exception as exc:
        logger.warning("Edge TTS synthesis failed: %s", exc)
        raise HTTPException(status_code=502, detail="Edge TTS synthesis failed") from exc

    if not first_chunk:
        raise HTTPException(status_code=502, detail="Edge TTS returned empty audio")

    async def body() -> AsyncIterator[bytes]:
        yield first_chunk
        async for chunk in generator:
            yield chunk

    return StreamingResponse(
        body(),
        media_type="audio/mpeg",
        headers={"X-TTS-Cache": "MISS"},
    )
