# TTS Service — Text-to-Speech via edge-tts / Magpie

Status: **implemented** (edge-tts active · Magpie ready, pending credentials)
Scope: synthesise interview questions as audio so YORI reads them aloud.

Component: `voice/tts` · Branch: `tts&stt`

## 1. Why this exists

The interview page shows each question in a speech bubble and plays it aloud
through the YORI robot avatar. The TTS layer handles synthesis and returns audio
bytes so the frontend can play them through an `<audio>` element. YORI's mouth
animation and audio-bar visualiser are synchronised to the audio's `play` and
`ended` events.

## 2. Architecture

Browser (voice.js)
│
│ POST /api/tts {“text”: “...”, “lang”: “en”}
│
▼
router.py → tts.synthesize(text, lang)
│
├─ MAGPIE_NVIDIA_API_KEY + MAGPIE_FUNCTION_ID present?
│ YES → Magpie (NVIDIA Riva gRPC) → WAV bytes
│ NO / fails → fallback ↓
│
└─ edge-tts (Microsoft, HTTP) → MP3 bytes
│
▼
Response(audio, media_type="audio/wav" | “audio/mpeg”)
│
▼
Browser: new Audio(blobURL) → play()
onplay → #robot-stage.classList.add(“is-miming”)
→ #mime-audio-bars.classList.add(“active”)
onended → remove both classes


## 3. Engine priority

| Priority | Engine | Protocol | Key needed | Voice quality | Vercel compatible |
|----------|--------|----------|------------|---------------|-------------------|
| 1 (preferred) | Magpie (NVIDIA Riva) | gRPC | Yes (`MAGPIE_NVIDIA_API_KEY` + `MAGPIE_FUNCTION_ID`) | ⭐⭐⭐⭐⭐ | ❌ gRPC blocked |
| 2 (fallback) | edge-tts (Microsoft) | HTTPS | No | ⭐⭐⭐⭐ | ✅ |

Magpie is selected automatically when both env vars are non-empty and not
placeholder values. Any exception from Magpie (auth error, timeout, gRPC
unavailable) triggers an immediate fallback to edge-tts with a console warning.

## 4. Backend module

**File:** `src/assistant/voice/tts.py`

```python
def synthesize(
    text: str,
    lang: str = "en",
    magpie_voice: str = "Magpie-Multilingual.EN-US.Aria",
) -> tuple[bytes, str]
```

| Parameter      | Type  | Required | Default | Notes |
|----------------|-------|----------|---------|-------|
| `text`         | `str` | yes      | —       | Question text to synthesise |
| `lang`         | `str` | no       | `"en"`  | `"en"` or `"vi"` |
| `magpie_voice` | `str` | no       | `"Magpie-Multilingual.EN-US.Aria"` | Riva voice name |

**Returns:** `(audio_bytes, mime_type)` where mime is `"audio/wav"` for Magpie
or `"audio/mpeg"` for edge-tts.

**Voices used:**

| Lang | Magpie | edge-tts fallback |
|------|--------|-------------------|
| `en` | `Magpie-Multilingual.EN-US.Aria` | `en-US-AriaNeural` |
| `vi` | _(same voice, multilingual)_ | `vi-VN-HoaiMyNeural` |

## 5. API endpoint

**File:** `src/assistant/voice/router.py`

POST /api/tts
Content-Type: application/json
Body: { “text”: “...”, “lang”: “en” }


Response `200 OK`: raw audio bytes (`audio/wav` or `audio/mpeg`).

Response `502`: Magpie and edge-tts both failed.
```json
{ "detail": "TTS error: ..." }
```

No authentication required.

## 6. Frontend integration

**File:** `ui/js/voice.js`

| Trigger | Behaviour |
|---------|-----------|
| Page load (after first user click) | Speaks the initial question |
| `MutationObserver` on `#question-text` | Speaks automatically when question changes |
| Click `#robot-replay-btn` | Re-speaks current question |
| New `speak()` call while audio is playing | Stops previous audio before starting new |
| STT mic activated | `stopSpeaking()` called first to avoid self-transcription |

**UI sync:**

| Element | Class toggled | When |
|---------|--------------|------|
| `#robot-stage` | `.is-miming` | `audio.onplay` → `audio.onended` |
| `#mime-audio-bars` | `.active` | same |

## 7. Environment variables

| Variable | Required for Magpie | Notes |
|----------|--------------------|----|
| `MAGPIE_NVIDIA_API_KEY` | Yes | Separate from team #312's `NVIDIA_API_KEY` (LLM only) |
| `MAGPIE_FUNCTION_ID` | Yes | Function ID from build.nvidia.com → Magpie TTS → "Try API" tab |

edge-tts requires no credentials. It calls Microsoft's speech endpoint over
standard HTTPS and is free for reasonable usage.

## 8. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `edge-tts` | `>=6.1` | Fallback TTS, no key required |
| `nvidia-riva-client` | `>=2.14` | Magpie gRPC client |
| `python-dotenv` | `>=1.0` | Load `.env` at runtime |

Install:
```bash
pip install -e ".[web,dev,voice]"
```

## 9. Known limitations

- **Magpie + Vercel:** Vercel serverless functions do not support gRPC and have
  a 10 s timeout. Magpie will always fall back to edge-tts on Vercel deployments
  until a dedicated gRPC-capable server is available.
- **Autoplay policy:** browsers block `audio.play()` before the first user
  gesture. The initial question is therefore spoken only after the user first
  clicks anywhere on the page.
- **No audio caching:** each replay of the same question makes a new `/api/tts`
  request. A future improvement would cache the blob URL per question text in
  `sessionStorage`.
