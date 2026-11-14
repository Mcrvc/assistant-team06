/**
 * voice.js — TTS (edge-tts/Magpie) + STT (Whisper) integration
 * Depends on: #robot-stage, #question-text, #mime-audio-bars,
 *             #robot-replay-btn, #mic-toggle-btn, #mic-btn-label,
 *             #mic-btn-sub, #voice-waveform, #answer
 */
(function () {
    "use strict";

    // ── DOM refs ────────────────────────────────────────────────────────
    const stage = document.getElementById("robot-stage");
    const questionEl = document.getElementById("question-text");
    const audioBars = document.getElementById("mime-audio-bars");
    const replayBtn = document.getElementById("robot-replay-btn");
    const micBtn = document.getElementById("mic-toggle-btn");
    const micLabel = document.getElementById("mic-btn-label");
    const micSub = document.getElementById("mic-btn-sub");
    const waveform = document.getElementById("voice-waveform");
    const answerBox = document.getElementById("answer");

    // ── State ───────────────────────────────────────────────────────────
    let currentAudio = null;
    let mediaRecorder = null;
    let audioChunks = [];
    let transcribeTimer = null;
    let isListening = false;
    let isSpeaking = false;
    let stream = null;
    let pendingStt = false;

    // ── TTS ─────────────────────────────────────────────────────────────
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

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            currentAudio = new Audio(url);

            currentAudio.onplay = () => { isSpeaking = true; startMiming(); };
            currentAudio.onended = () => { isSpeaking = false; stopMiming(); URL.revokeObjectURL(url); };
            currentAudio.onerror = () => { isSpeaking = false; stopMiming(); URL.revokeObjectURL(url); };

            await currentAudio.play();
        } catch (err) {
            console.warn("[voice] TTS failed:", err);
            stopMiming();
        }
    }

    function stopSpeaking() {
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
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

    // ── STT ─────────────────────────────────────────────────────────────
    async function startListening() {
        if (isListening) return;

        // Stop TTS so robot doesn't transcribe itself
        stopSpeaking();

        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch {
            micSub.textContent = "Microphone access denied.";
            return;
        }

        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };
        mediaRecorder.start(1000);

        isListening = true;
        setMicState(true);

        // Pseudo-live: re-transcribe every 4 s while recording
        transcribeTimer = setInterval(() => sendChunks(false), 4000);
    }

    async function stopListening() {
        if (!isListening) return;
        clearInterval(transcribeTimer);
        isListening = false;

        mediaRecorder.onstop = () => sendChunks(true);
        mediaRecorder.stop();
        stream.getTracks().forEach((t) => t.stop());

        setMicState(false);
    }

    async function sendChunks(isFinal) {
        if (audioChunks.length === 0 || pendingStt) return;
        pendingStt = true;

        const blob = new Blob([...audioChunks], {
            type: mediaRecorder?.mimeType || "audio/webm",
        });
        const fd = new FormData();
        fd.append("audio", blob, "recording.webm");

        try {
            const res = await fetch("/api/stt", { method: "POST", body: fd });
            if (!res.ok) throw new Error(`STT HTTP ${res.status}`);
            const data = await res.json();
            if (data.text && data.text.trim()) {
                answerBox.value = data.text;
                // Fire input event so char-counter in app.js updates
                answerBox.dispatchEvent(new Event("input", { bubbles: true }));
            }
        } catch (err) {
            console.warn("[voice] STT failed:", err);
            if (isFinal) micSub.textContent = "Transcription failed. Please type manually.";
        } finally {
            pendingStt = false;
        }
    }

    function setMicState(on) {
        micBtn.classList.toggle("is-recording", on);
        waveform?.classList.toggle("active", on);
        micLabel.textContent = on ? "Recording…" : "Record Answer with Microphone";
        micSub.textContent = on ? "Click to stop" : "Click to start speech-to-text";
        micBtn.setAttribute("aria-label", on ? "Stop recording" : "Record answer with microphone");
    }

    // ── Wiring ──────────────────────────────────────────────────────────
    replayBtn?.addEventListener("click", () => {
        const text = questionEl?.textContent?.trim();
        if (text) speak(text);
    });

    micBtn?.addEventListener("click", () => {
        isListening ? stopListening() : startListening();
    });

    // Auto-speak when question text changes (app.js updates #question-text)
    const observer = new MutationObserver(() => {
        const text = questionEl?.textContent?.trim();
        if (text) speak(text);
    });
    if (questionEl) {
        observer.observe(questionEl, { childList: true, subtree: true, characterData: true });
    }

    // Speak the initial question on page load (after first user gesture guard)
    document.addEventListener("click", function speakFirst() {
        document.removeEventListener("click", speakFirst);
        const text = questionEl?.textContent?.trim();
        if (text) speak(text);
    }, { once: true });

    // Expose for app.js if needed
    window.Voice = { speak, stopSpeaking, startListening, stopListening };
})();
