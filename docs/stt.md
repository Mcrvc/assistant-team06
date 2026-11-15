# STT Service — Speech-to-Text via Whisper

Status: **implemented**
Scope: transcribe user microphone audio to text during an interview session.

Component: `voice/stt` · Branch: `tts&stt`

## 1. Why this exists

The interview page (`ui/interview.html`) lets candidates record spoken answers
instead of typing. Audio captured in the browser is sent to the backend, where
Whisper converts it to text and fills the `#answer` textarea in real time.

The STT layer is intentionally a thin wrapper around Whisper so the rest of the
app never imports a speech library directly. Swapping the model (e.g. upgrading
from `base` to `small`) must not change any caller.

## 2. Architecture

Browser (voice.js)
│
│ MediaRecorder chunks every 1 s
│ Blob sent every 4 s (pseudo-live) + on stop (final)
│
▼
POST /api/stt ← router.py
│ multipart/form-data: audio file (webm/wav/any ffmpeg-readable)
▼
stt.transcribe(bytes) ← stt.py
│ write to temp file → Whisper → delete temp file
▼
{“text”: “...”} → voice.js fills #answer + fires input event


## 3. Backend module

**File:** `src/assistant/voice/stt.py`

```python
def transcribe(audio_bytes: bytes, language: str | None = None) -> str
```

| Parameter     | Type            | Required | Default | Notes |
|---------------|-----------------|----------|---------|-------|
| `audio_bytes` | `bytes`         | yes      | —       | Raw audio in any format ffmpeg can read |
| `language`    | `str` or `None` | no       | `None`  | ISO-639-1 code e.g. `"en"`, `"vi"`. `None` = auto-detect |

**Returns:** transcribed text as a plain string. Empty string `""` when no
speech is detected (e.g. silence, noise-only).

**Model:** `openai-whisper` base model, CPU, FP32.
Loaded lazily on first call; subsequent calls reuse the in-memory model.
First call downloads ~139 MB from Hugging Face (cached to `~/.cache/whisper`).

**Temp file lifecycle:** audio bytes are written to a `.wav` temp file, passed
to Whisper, then deleted in a `finally` block regardless of success or failure.

## 4. API endpoint

**File:** `src/assistant/voice/router.py`

POST /api/stt
Content-Type: multipart/form-data
Field: audio — the recorded audio blob


Response `200 OK`:
```json
{ "text": "I would put a smartphone inside the time capsule..." }
```

Response `500` (Whisper crash or ffmpeg missing):
```json
{ "detail": "Internal Server Error" }
```

No authentication is required on this endpoint. It accepts any audio format
ffmpeg can decode (webm, wav, mp3, ogg, m4a).

## 5. Frontend integration

**File:** `ui/js/voice.js`

| Element          | ID                | Behaviour |
|------------------|-------------------|-----------|
| Mic toggle button | `#mic-toggle-btn` | Click to start/stop recording |
| Answer textarea  | `#answer`         | Filled with transcript on each STT response |
| Waveform bars    | `#voice-waveform` | `.active` class added while recording |
| Mic label        | `#mic-btn-label`  | Updates to "Recording…" / "Record Answer with Microphone" |
| Mic sub-label    | `#mic-btn-sub`    | Updates to "Click to stop" / "Click to start speech-to-text" |

**Pseudo-live transcript flow:**
1. `MediaRecorder` collects chunks every 1 s.
2. `setInterval` fires every 4 s → sends cumulative blob to `/api/stt` → replaces `#answer` value.
3. On stop → one final send with the complete recording.
4. Each successful write fires an `input` event on `#answer` so the character counter in `app.js` updates.

**Race condition guard:** a `pendingStt` flag prevents overlapping requests.
If a request is still in flight when the next interval fires, that tick is skipped.

## 6. Dependencies

| Package          | Version       | Purpose |
|------------------|---------------|---------|
| `openai-whisper` | `>=20240930`  | Transcription model |
| `ffmpeg`         | system (`apt`)| Audio decoding (required by Whisper) |
| `python-multipart` | `>=0.0.9`  | FastAPI file upload parsing |

Install:
```bash
sudo apt install -y ffmpeg
pip install -e ".[web,dev,voice]"
```

## 7. Known limitations

- **Latency:** first request is slow (~3–5 s) while the model loads. Subsequent
  requests are faster (~1–2 s for a 4 s clip on CPU).
- **Cumulative re-transcription:** the full recording is re-sent every 4 s. For
  long answers (>60 s) this increases cost and latency. A future improvement
  would transcribe only the latest chunk and append rather than replace.
- **No streaming:** Whisper is not natively streaming. True word-by-word live
  captions would require `whisper-streaming` or a chunked VAD approach.
- **CPU only:** `compute_type="int8"` on CPU. A GPU would reduce latency to
  under 0.5 s but is not available on Vercel.
