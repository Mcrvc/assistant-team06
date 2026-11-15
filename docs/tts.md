# TTS Service — Text-to-Speech via edge-tts / Magpie

Status: **implemented** (edge-tts active · Magpie ready, pending credentials)
Scope: synthesise interview questions as audio so YORI reads them aloud.

Component: `voice/tts` · Branch: `tts&stt`

## 1. Why this exists

The interview page shows each question in a speech bubble and plays it aloud
through the YORI robot avatar. TTS runs on the backend so the voice quality
is consistent across all browsers and the synthesis engine can be upgraded
(for example, from edge-tts to Magpie) without touching the frontend.

## 2. Architecture

Browser (voice.js)
│
│ POST /api/tts {“text”: “...”, “lang”: “en”}
│
▼
router.py → tts.synthesize(text, lang)
│
├─ MAGPIE_NVIDIA_API_KEY + MAGPIE_FUNCTION_ID present and non-placeholder?
│ YES → Magpie (NVIDIA Riva, gRPC) → WAV bytes
│ NO / fails → fallback ↓
│
└─ edge-tts (Microsoft, HTTPS) → MP3 bytes
│
▼
Response(audio, media_type="audio/wav" | “audio/mpeg”)
│
▼
Browser: new Audio(blobURL).play()
onplay → #robot-stage.classList.add(“is-miming”)
→ #mime-audio-bars.classList.add(“active”)
onended → remove both classes, revoke blob URL


## 3. Engine priority

| Priority | Engine | Protocol | Key needed | Vercel compatible |
|---|---|---|---|---|
| 1 (preferred) | Magpie (NVIDIA Riva) | gRPC | Yes (`MAGPIE_NVIDIA_API_KEY` + `MAGPIE_FUNCTION_ID`) | ❌ gRPC blocked |
| 2 (fallback) | edge-tts (Microsoft) | HTTPS | No | ✅ |

Magpie is selected automatically when both env vars are non-empty and not
placeholder values. Any exception from Magpie triggers an immediate fallback
to edge-tts with a console warning. On Vercel, edge-tts is always used.

## 4. Backend module

**File:** `src/assistant/voice/tts.py`

```python
def synthesize(
    text: str,
    lang: str = "en",
    magpie_voice: str = "Magpie-Multilingual.EN-US.Aria",
) -> tuple[bytes, str]
```

Returns `(audio_bytes, mime_type)` — `"audio/wav"` for Magpie, `"audio/mpeg"` for edge-tts.

**Voices:**

| Lang | Magpie | edge-tts |
|---|---|---|
| `en` | `Magpie-Multilingual.EN-US.Aria` | `en-US-AriaNeural` |
| `vi` | _(same multilingual voice)_ | `vi-VN-HoaiMyNeural` |

## 5. API endpoint

**File:** `src/assistant/voice/router.py`

POST /api/tts
Content-Type: application/json
Body: { “text”: “...”, “lang”: “en” }


| Status | Condition |
|---|---|
| `200` | Audio bytes returned, `Content-Type: audio/wav` or `audio/mpeg` |
| `400` | Missing or invalid request body (FastAPI validation) |
| `502` | Both Magpie and edge-tts failed |

No authentication required.

## 6. Frontend integration

**File:** `ui/js/voice.js`

| Trigger | Behaviour |
|---|---|
| Page load (after first user click) | Speaks the initial question |
| `MutationObserver` on `#question-text` | Speaks when question text changes |
| Click `#robot-replay-btn` | Re-speaks current question |
| New `speak()` while audio is playing | Stops previous audio first |
| Mic button activated | `stopSpeaking()` called to prevent self-transcription |

**UI sync:**

| Element | Class | When active |
|---|---|---|
| `#robot-stage` | `.is-miming` | `audio.onplay` → `audio.onended` |
| `#mime-audio-bars` | `.active` | same |

## 7. Environment variables

| Variable | Required for Magpie | Notes |
|---|---|---|
| `MAGPIE_NVIDIA_API_KEY` | Yes | Separate from team #312's `NVIDIA_API_KEY` (LLM only) |
| `MAGPIE_FUNCTION_ID` | Yes | From build.nvidia.com → Magpie TTS → "Try API" tab |

## 8. Dependencies

| Package | Version | Purpose |
|---|---|---|
| `edge-tts` | `>=6.1` | Fallback TTS, no credentials required |
| `nvidia-riva-client` | `>=2.14` | Magpie gRPC client |
| `python-dotenv` | `>=1.0` | Load `.env` at startup |

```bash
pip install -e ".[web,dev,voice]"
```

## 9. Known limitations

- **Magpie + Vercel:** Vercel blocks gRPC; Magpie always falls back to edge-tts on Vercel until a dedicated server is available.
- **Autoplay policy:** browsers block `audio.play()` before the first user gesture. The initial question speaks only after the user clicks anywhere on the page.
- **No audio caching:** each replay calls `/api/tts` again. A future improvement would cache the blob URL per question text in `sessionStorage` to avoid redundant requests.