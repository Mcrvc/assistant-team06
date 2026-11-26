/**
 * voice.js — Edge TTS (/api/tts, en-US-AnaNeural) with Web Speech API fallback
 * + STT (SpeechRecognition).
 *
 * Exposes window.Voice so app.js drives YORI's lip-sync (.is-miming),
 * #mime-audio-bars, #voice-waveform (.is-active), and #answer without
 * duplicating click listeners or running mock timers alongside real speech.
 */
(function () {
  "use strict";

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition || null;

  const DEFAULT_TTS_VOICE = "en-US-AnaNeural";
  const TTS_TIMEOUT_MS = 8000;

  function resolveTtsEndpoint(params) {
    const base =
      window.YourinAPI && typeof window.YourinAPI.getBaseUrl === "function"
        ? String(window.YourinAPI.getBaseUrl() || "").replace(/\/+$/, "")
        : "";
    return `${base}/api/tts?${params.toString()}`;
  }

  let currentUtterance = null;
  let currentAudio = null;
  let currentAudioUrl = null;
  let currentAbort = null;
  let speakToken = 0;
  let recognition = null;
  let isListening = false;

  function speechSynthesisSupported() {
    return Boolean(
      window.speechSynthesis && typeof window.SpeechSynthesisUtterance === "function"
    );
  }

  function audioTtsSupported() {
    return typeof window.Audio === "function" && typeof window.fetch === "function";
  }

  function ttsSupported() {
    return audioTtsSupported() || speechSynthesisSupported();
  }

  function sttSupported() {
    return Boolean(SpeechRecognition);
  }

  function cleanupAudio() {
    if (currentAbort) {
      try {
        currentAbort.abort();
      } catch (_) { /* Ignore abort errors. */ }
      currentAbort = null;
    }
    if (currentAudio) {
      try {
        currentAudio.onplay = null;
        currentAudio.onended = null;
        currentAudio.onerror = null;
        currentAudio.pause();
        currentAudio.removeAttribute("src");
      } catch (_) { /* Ignore audio cleanup errors. */ }
      currentAudio = null;
    }
    if (currentAudioUrl) {
      try {
        URL.revokeObjectURL(currentAudioUrl);
      } catch (_) { /* Ignore object URL errors. */ }
      currentAudioUrl = null;
    }
  }

  function stopSpeaking() {
    speakToken += 1;
    cleanupAudio();
    if (speechSynthesisSupported()) {
      try {
        window.speechSynthesis.cancel();
      } catch (_) { /* Ignore synthesis cancel errors. */ }
    }
    currentUtterance = null;
  }

  function speakWithSpeechSynthesis(clean, callbacks, token) {
    if (token !== speakToken || !speechSynthesisSupported()) {
      if (typeof callbacks.onEnd === "function") callbacks.onEnd();
      return false;
    }

    const utterance = new window.SpeechSynthesisUtterance(clean);
    utterance.lang = callbacks.lang || "en-US";
    utterance.rate = 1;
    currentUtterance = utterance;

    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      if (currentUtterance === utterance) currentUtterance = null;
      if (typeof callbacks.onEnd === "function") callbacks.onEnd();
    };

    utterance.onstart = () => {
      if (token !== speakToken || currentUtterance !== utterance) return;
      if (typeof callbacks.onStart === "function") callbacks.onStart();
    };
    utterance.onend = finish;
    utterance.onerror = finish;

    try {
      window.speechSynthesis.speak(utterance);
      return true;
    } catch (_) {
      finish();
      return false;
    }
  }

  function speak(text, callbacks = {}) {
    const clean = String(text || "").trim();
    if (!clean || !ttsSupported()) return false;

    stopSpeaking();
    const token = speakToken;

    if (!audioTtsSupported()) {
      return speakWithSpeechSynthesis(clean, callbacks, token);
    }

    const controller = typeof AbortController === "function" ? new AbortController() : null;
    currentAbort = controller;
    const timeoutId = controller
      ? setTimeout(() => controller.abort(), TTS_TIMEOUT_MS)
      : null;

    const params = new URLSearchParams({
      text: clean.slice(0, 2000),
      voice: callbacks.voice || DEFAULT_TTS_VOICE,
      rate: callbacks.rate || "+0%",
    });

    fetch(resolveTtsEndpoint(params), controller ? { signal: controller.signal } : {})
      .then((res) => {
        if (timeoutId) clearTimeout(timeoutId);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        if (token !== speakToken) return;
        currentAbort = null;
        const url = URL.createObjectURL(blob);
        const audio = new window.Audio(url);
        currentAudio = audio;
        currentAudioUrl = url;

        let finished = false;
        const finish = () => {
          if (finished) return;
          finished = true;
          if (currentAudio === audio) cleanupAudio();
          if (typeof callbacks.onEnd === "function") callbacks.onEnd();
        };

        audio.onplay = () => {
          if (token !== speakToken || currentAudio !== audio) return;
          if (typeof callbacks.onStart === "function") callbacks.onStart();
        };
        audio.onended = finish;
        audio.onerror = finish;

        return audio.play().catch((err) => {
          if (token !== speakToken) return;
          cleanupAudio();
          throw err;
        });
      })
      .catch(() => {
        if (timeoutId) clearTimeout(timeoutId);
        if (token !== speakToken) return;
        cleanupAudio();
        speakWithSpeechSynthesis(clean, callbacks, token);
      });

    return true;
  }

  function stopListening() {
    isListening = false;
    if (recognition) {
      const active = recognition;
      recognition = null;
      try {
        active.stop();
      } catch (_) { /* Ignore recognition stop errors. */ }
    }
  }

  function startListening(callbacks = {}) {
    if (!sttSupported()) return false;
    if (isListening) return true;

    stopSpeaking();

    const rec = new SpeechRecognition();
    rec.lang = callbacks.lang || "en-US";
    rec.interimResults = true;
    rec.continuous = true;
    rec.maxAlternatives = 1;

    const baseText = String(
      typeof callbacks.getText === "function" ? callbacks.getText() : ""
    ).trim();
    let finalTranscript = "";

    rec.onresult = (event) => {
      if (recognition !== rec) return;
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) {
          finalTranscript += transcript + " ";
        } else {
          interim += transcript;
        }
      }
      const spoken = (finalTranscript + interim).trim();
      const combined = baseText
        ? (spoken ? `${baseText} ${spoken}` : baseText)
        : spoken;
      if (typeof callbacks.onText === "function") callbacks.onText(combined);
    };

    rec.onerror = (event) => {
      if (recognition !== rec) return;
      if (event.error === "no-speech" && isListening) return;
      isListening = false;
      recognition = null;
      if (typeof callbacks.onError === "function") callbacks.onError(event.error);
    };

    rec.onend = () => {
      if (recognition !== rec) return;
      if (isListening) {
        try {
          rec.start();
          return;
        } catch (_) { /* Fall through to end state if restart fails. */ }
      }
      isListening = false;
      recognition = null;
      if (typeof callbacks.onEnd === "function") callbacks.onEnd();
    };

    try {
      recognition = rec;
      isListening = true;
      rec.start();
      return true;
    } catch (_) {
      isListening = false;
      recognition = null;
      return false;
    }
  }

  window.addEventListener("pagehide", () => {
    stopSpeaking();
    stopListening();
  });

  window.Voice = {
    ttsSupported,
    sttSupported,
    speak,
    stopSpeaking,
    startListening,
    stopListening,
  };
})();
