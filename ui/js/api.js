/* API Connection Helper for Render (`src/assistant/web.py`) + Vercel */
(() => {
  "use strict";

  // Set your live Render Web Service URL here once deployed (e.g. "https://assistant-team06.onrender.com")
  const RENDER_API_URL = "https://assistant-team06.onrender.com";

  function resolveBaseUrl() {
    if (RENDER_API_URL.trim()) {
      return RENDER_API_URL.trim().replace(/\/+$/, "");
    }
    if (window.location.protocol.startsWith("http") &&
        (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")) {
      return window.location.origin;
    }
    return "";
  }

  async function requestJson(path, options = {}) {
    const base = resolveBaseUrl();
    if (!base) return null;
    try {
      const response = await fetch(`${base}${path}`, {
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options
      });
      return await response.json();
    } catch (_) {
      return null;
    }
  }

  window.YourinAPI = {
    getBaseUrl: resolveBaseUrl,
    getHealth: () => requestJson("/api/health"),
    getConfig: () => requestJson("/api/config"),
    askAssistant: question =>
      requestJson("/api/answer", {
        method: "POST",
        body: JSON.stringify({ question })
      })
  };
})();
