/* API Connection Helper for Render (`src/assistant/web.py`) + Vercel */
(() => {
  "use strict";

  // Live Render Web Service. Set window.YOURIN_API_URL before this file loads to override.
  const DEFAULT_API_URL = "https://assistant-team06.onrender.com";
  const OVERRIDE_API_URL = (window.YOURIN_API_URL || "").trim();

  function resolveBaseUrl() {
    if (OVERRIDE_API_URL) {
      return OVERRIDE_API_URL.replace(/\/+$/, "");
    }
    // Local development talks to the Python server serving the UI.
    if (window.location.protocol.startsWith("http") &&
        (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")) {
      return window.location.origin;
    }
    return DEFAULT_API_URL;
  }

  function notify(status, data) {
    try {
      if (window.YourinErrors && typeof window.YourinErrors.handleStatus === "function") {
        window.YourinErrors.handleStatus(status, data);
      }
    } catch (_) { /* never break the caller */ }
  }

  async function request(path, options = {}) {
    const base = resolveBaseUrl();
    if (!base) {
      return { status: 0, ok: false, data: null, networkError: true, fallback: true };
    }

    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    try {
      const response = await fetch(`${base}${path}`, { ...options, headers });
      let data = null;
      try { data = await response.json(); } catch (_) { data = null; }
      if (!response.ok) {
        notify(response.status, data);
      }
      return { status: response.status, ok: response.ok, data };
    } catch (_) {
      notify(0, null);
      return { status: 0, ok: false, data: null, networkError: true, fallback: true };
    }
  }

  // Backward-compatible helper: returns parsed JSON on success, null otherwise.
  async function requestJson(path, options = {}) {
    const result = await request(path, options);
    if (result.ok) return result.data;
    return null;
  }

  window.YourinAPI = {
    getBaseUrl: resolveBaseUrl,
    request,
    getHealth: () => request("/api/health"),
    getConfig: () => request("/api/config"),
    askAssistant: question =>
      request("/api/answer", {
        method: "POST",
        body: JSON.stringify({ question })
      })
  };
})();
