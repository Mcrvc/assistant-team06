# STT Service — Speech-to-Text via Web Speech API

Status: **implemented**
Scope: transcribe candidate speech to text during an interview session.

Component: `voice/stt` · Branch: `tts&stt`

## 1. Why Web Speech API (not Whisper)

The original plan used `openai-whisper` on the backend (`POST /api/stt`).
After review, the team decided to move STT entirely to the browser for three reasons:

- **No backend latency:** transcription happens locally in the browser, results appear in real time word by word.
- **Vercel compatibility:** Vercel serverless functions have a 10 s timeout and no persistent process; running Whisper there is impractical.
- **Consistency with existing frontend:** `app.js` already owned the mic button state (`isRecording`, `startRecording`, `stopRecording`). A backend STT layer duplicated that logic and caused event-listener conflicts on `#mic-toggle-btn`.

`openai-whisper`, `stt.py`, and `POST /api/stt` have been removed. The backend has no STT endpoint.

## 2. Architecture

Browser (voice.js)
│
│ User clicks #mic-toggle-btn
│
▼
SpeechRecognition (window.SpeechRecognition / webkitSpeechRecognition)
│ continuous = true, interimResults = true
│ lang = “en-US”
│
│ onresult → interim + final transcript
▼
#answer textarea ← updated in real time
app.js input event fired → char counter updates


No network request is made. Everything runs inside the browser process.

## 3. Frontend implementation

**File:** `ui/js/voice.js`

```javascript
function startListening()  // starts SpeechRecognition, returns false if unsupported
function stopListening()   // stops recognition, exposed via window.Voice
```

| Element | ID | Behaviour |
|---|---|---|
| Mic toggle button | `#mic-toggle-btn` | Click to start / stop |
| Answer textarea | `#answer` | Filled with transcript in real time |
| Waveform bars | `#voice-waveform` | `.active` while recording (handled by `app.js`) |
| Mic label | `#mic-btn-label` | `app.js` updates to "Recording… / Record Answer" |

**Real-time transcript flow:**
1. `onresult` fires on every word recognised.
2. Final segments are concatenated into `finalTranscript`; interim segments shown immediately.
3. `#answer.value` = `finalTranscript + interim` on every event.
4. An `input` event is dispatched so `app.js` char counter stays in sync.
5. If the browser auto-stops after silence, `recognition.onend` restarts it while `isListening` is still `true`.

**Relationship with `app.js`:**
`app.js` owns the mic button UI state (`is-recording` class, label text, waveform class, `isRecording` flag). `voice.js` owns the `SpeechRecognition` lifecycle. Both attach to `#mic-toggle-btn`; `voice.js` loads after `app.js` (`defer` ordering in `interview.html`) and calls `stopSpeaking()` before starting recognition so YORI's voice is not transcribed.

## 4. Browser support

| Browser | Support |
|---|---|
| Chrome / Edge | ✅ Full (`window.SpeechRecognition` or `webkitSpeechRecognition`) |
| Safari | ⚠️ Partial (requires HTTPS, no `continuous` mode) |
| Firefox | ❌ Not supported |

**Fallback:** when `SpeechRecognition` is unavailable, `startListening()` returns `false` and logs a warning. `app.js`'s original mock (`setTimeout` sample text) continues to handle the button click uninterrupted.

## 5. Known limitations

- **No offline support:** Web Speech API in Chrome sends audio to Google's servers; not suitable for air-gapped deployments.
- **Language:** hardcoded to `"en-US"`. Vietnamese (`vi-VN`) can be added by passing `lang` based on the interview's configured language.
- **Safari continuous mode:** Safari stops recognition after a short pause; the `onend` restart loop partially compensates but behaviour is inconsistent.
- **Self-transcription:** `voice.js` calls `stopSpeaking()` before opening the mic; without this, YORI's TTS audio would be picked up by the microphone.