/**
 * voice.js — TTS (edge-tts/Magpie backend) + STT (Web Speech API, browser-native)
 *
 * TTS: POST /api/tts → audio blob → <Audio> play
 *      syncs .is-miming on #robot-stage and .active on #mime-audio-bars
 *
 * STT: SpeechRecognition (Chrome/Edge) → interim + final transcript → #answer
 *      replaces the setTimeout mock in app.js by overriding window.Voice
 *      app.js calls startRecording()/stopRecording() which voice.js re-wires
 *
 * Fallback: if SpeechRecognition is unavailable (Firefox), mic button still
 *           works via app.js's original mock — voice.js does not break it.
 */
(function () {
  "use strict";

  // ── DOM refs ─────────────────────────────────────────────────────────
  const stage      = document.getElementById("robot-stage");
  const questionEl = document.getElementById("question-text");
  const audioBars  = document.getElementById("mime-audio-bars");
  const replayBtn  = document.getElementById("robot-replay-btn");
  const micBtn     = document.getElementById("mic-toggle-btn");
  const micLabel   = document.getElementById("mic-btn-label");
  const micSub     = document.getElementById("mic-btn-sub");
  const waveform   = document.getElementById("voice-waveform");
  const answerBox  = document.getElementById("answer");

  // ── TTS state ────────────────────────────────────────────────────────
  let currentAudio = null;
  let isSpeaking   = false;

  // ── STT state ────────────────────────────────────────────────────────
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition || null;
  let recognition  = null;
  let isListening  = false;

  // ── TTS ──────────────────────────────────────────────────────────────
  async function speak(text) {
    if (!text || !text.trim()) return;
    stopSpeaking();
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, lang: "en" }),
      });
      if (!res.ok) throw new Error(`TTS HTTP ${res.status}`);
      const url = URL.createObjectURL(await res.blob());
      currentAudio = new Audio(url);
      currentAudio.onplay  = () => { isSpeaking = true;  startMiming(); };
      currentAudio.onended = () => { isSpeaking = false; stopMiming(); URL.revokeObjectURL(url); };
      currentAudio.onerror = () => { isSpeaking = false; stopMiming(); URL.revokeObjectURL(url); };
      await currentAudio.play();
    } catch (err) {
      console.warn("[voice] TTS failed:", err);
      stopMiming();
    }
  }

  function stopSpeaking() {
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    stopMiming();
    isSpeaking = false;
  }

  function startMiming() {
    stage?.classList.add("is-miming");
    audioBars?.classList.add("active");
  }

  function stopMiming() {
    stage?.classList.remove("is-miming");
    audioBars?.classList.remove("active");
  }

  // ── STT ──────────────────────────────────────────────────────────────
  function startListening() {
    if (!SpeechRecognition) {
      // Browser không hỗ trợ → để app.js mock chạy bình thường
      console.warn("[voice] SpeechRecognition not supported, using app.js fallback");
      return false;   // signal app.js to run its own logic
    }
    if (isListening) return true;

    // Stop TTS trước để robot không tự transcribe giọng mình
    stopSpeaking();

    recognition = new SpeechRecognition();
    recognition.lang           = "en-US";
    recognition.interimResults = true;
    recognition.continuous     = true;
    recognition.maxAlternatives = 1;

    let finalTranscript = "";

    recognition.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalTranscript += t + " ";
        else interim = t;
      }
      if (answerBox) {
        answerBox.value = (finalTranscript + interim).trim();
        answerBox.dispatchEvent(new Event("input", { bubbles: true }));
      }
    };

    recognition.onerror = (e) => {
      console.warn("[voice] STT error:", e.error);
      if (e.error === "not-allowed") {
        if (micSub) micSub.textContent = "Microphone access denied.";
      }
      stopListening();
    };

    recognition.onend = () => {
      // Browser auto-stops after silence — restart if still meant to be listening
      if (isListening) recognition.start();
    };

    recognition.start();
    isListening = true;
    return true;
  }

  function stopListening() {
    if (recognition) { recognition.stop(); recognition = null; }
    isListening = false;
  }

  // ── Override app.js mic wiring ────────────────────────────────────────
  // app.js attaches its own click listener to #mic-toggle-btn BEFORE voice.js
  // loads. We replace the behaviour by overriding window.Voice so app.js can
  // call Voice.startRecording / Voice.stopRecording if it checks for them,
  // AND we attach our own click listener that calls stopSpeaking first.
  if (micBtn) {
    micBtn.addEventListener("click", () => {
      if (isListening) {
        stopListening();
        // let app.js stopRecording() handle UI reset (it already has a listener)
      } else {
        const handled = startListening();
        if (!handled) return;   // SpeechRecognition unavailable, app.js takes over
        // Stop TTS when mic opens
        stopSpeaking();
      }
    });
  }

  // ── Replay button ─────────────────────────────────────────────────────
  replayBtn?.addEventListener("click", () => {
    const text = questionEl?.textContent?.trim();
    if (text) speak(text);
  });

  // ── Auto-speak on question change ─────────────────────────────────────
  if (questionEl) {
    new MutationObserver(() => {
      const text = questionEl.textContent?.trim();
      if (text) speak(text);
    }).observe(questionEl, { childList: true, subtree: true, characterData: true });
  }

  // Speak initial question after first user gesture (autoplay policy)
  document.addEventListener("click", function speakFirst() {
    document.removeEventListener("click", speakFirst);
    const text = questionEl?.textContent?.trim();
    if (text) speak(text);
  }, { once: true });

  // ── Public API ────────────────────────────────────────────────────────
  window.Voice = {
    speak,
    stopSpeaking,
    startListening,
    stopListening,
  };
})();
