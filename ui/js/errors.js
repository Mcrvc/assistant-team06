/* Shared error notifications: toasts, banners, and HTTP status routing (400/401/500/503). */
(() => {
  "use strict";

  const TOAST_DURATION = 4500;
  const FALLBACK_BANNER_ID = "yourin-fallback-banner";

  let toastStack = null;
  let bannerEl = null;

  function ensureToastStack() {
    if (toastStack && document.body.contains(toastStack)) return toastStack;
    toastStack = document.createElement("div");
    toastStack.className = "yourin-toast-stack";
    toastStack.setAttribute("aria-live", "polite");
    toastStack.setAttribute("aria-atomic", "false");
    document.body.appendChild(toastStack);
    return toastStack;
  }

  function iconFor(type) {
    if (type === "success") return "✓";
    if (type === "warning") return "!";
    if (type === "info") return "i";
    return "×";
  }

  function showToast(message, options = {}) {
    if (!message) return null;
    const type = options.type || "error";
    const duration = typeof options.duration === "number" ? options.duration : TOAST_DURATION;
    const stack = ensureToastStack();

    const toast = document.createElement("div");
    toast.className = "yourin-toast toast notification yourin-toast--" + type;
    toast.setAttribute("role", "status");

    const icon = document.createElement("span");
    icon.className = "yourin-toast__icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = iconFor(type);

    const text = document.createElement("span");
    text.className = "yourin-toast__text";
    text.textContent = String(message);

    const close = document.createElement("button");
    close.type = "button";
    close.className = "yourin-toast__close";
    close.setAttribute("aria-label", "Dismiss notification");
    close.textContent = "×";
    close.addEventListener("click", () => dismissToast(toast));

    toast.append(icon, text, close);
    stack.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add("is-visible"));

    if (duration > 0) {
      toast._timer = setTimeout(() => dismissToast(toast), duration);
    }
    return toast;
  }

  function dismissToast(toast) {
    if (!toast || !toast.parentNode) return;
    if (toast._timer) clearTimeout(toast._timer);
    toast.classList.remove("is-visible");
    toast.classList.add("is-leaving");
    setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 220);
  }

  function showBanner(message, options = {}) {
    const type = options.type || "warning";
    const dismissible = options.dismissible !== false;
    if (bannerEl && bannerEl.parentNode) bannerEl.parentNode.removeChild(bannerEl);

    bannerEl = document.createElement("div");
    bannerEl.id = FALLBACK_BANNER_ID;
    bannerEl.className = "yourin-banner banner notification yourin-banner--" + type;
    bannerEl.setAttribute("role", "alert");

    const text = document.createElement("span");
    text.className = "yourin-banner__text";
    text.textContent = String(message);
    bannerEl.appendChild(text);

    if (options.actionLabel && typeof options.onAction === "function") {
      const action = document.createElement("button");
      action.type = "button";
      action.className = "yourin-banner__action";
      action.textContent = options.actionLabel;
      action.addEventListener("click", options.onAction);
      bannerEl.appendChild(action);
    }

    if (dismissible) {
      const close = document.createElement("button");
      close.type = "button";
      close.className = "yourin-banner__close";
      close.setAttribute("aria-label", "Dismiss banner");
      close.textContent = "×";
      close.addEventListener("click", () => {
        if (bannerEl && bannerEl.parentNode) bannerEl.parentNode.removeChild(bannerEl);
        bannerEl = null;
      });
      bannerEl.appendChild(close);
    }

    // Insert at top of body, before header if present
    const header = document.querySelector(".site-header");
    if (header && header.parentNode) {
      header.parentNode.insertBefore(bannerEl, header);
    } else {
      document.body.insertBefore(bannerEl, document.body.firstChild);
    }
    return bannerEl;
  }

  function hideBanner() {
    if (bannerEl && bannerEl.parentNode) bannerEl.parentNode.removeChild(bannerEl);
    bannerEl = null;
  }

  function messageFromPayload(payload) {
    if (!payload) return null;
    if (typeof payload === "string") return payload.trim() || null;
    if (Array.isArray(payload)) return validationMessage(payload);
    if (typeof payload !== "object") return String(payload);

    const error = payload.error;
    if (error) {
      if (typeof error === "string") return error.trim() || null;
      if (typeof error === "object") {
        return textValue(error.message) ||
          textValue(error.detail) ||
          validationMessage(error.details) ||
          textValue(error.code);
      }
    }

    return textValue(payload.message) ||
      textValue(payload.detail) ||
      validationMessage(payload.detail) ||
      validationMessage(payload.details) ||
      validationMessage(payload.errors) ||
      textValue(payload.msg);
  }

  function textValue(value) {
    return typeof value === "string" ? value.trim() || null : null;
  }

  function validationMessage(details) {
    if (!Array.isArray(details)) return null;

    const messages = details.map(item => {
      if (typeof item === "string") return item.trim() || null;
      if (!item || typeof item !== "object") return null;

      const location = Array.isArray(item.location)
        ? item.location
        : (Array.isArray(item.loc) ? item.loc : []);
      const field = location
        .filter(part => !["body", "query", "path"].includes(part))
        .join(".");
      const message = textValue(item.message) || textValue(item.msg) || textValue(item.type);

      if (!message) return null;
      return field ? `${field}: ${message}` : message;
    }).filter(Boolean);

    if (messages.length === 0) return null;
    if (messages.length <= 3) return messages.join("; ");
    return `${messages.slice(0, 3).join("; ")} (+${messages.length - 3} more)`;
  }

  function handleStatus(status, payload) {
    // 401: not authenticated -> redirect to sign-in (unless already there)
    if (status === 401) {
      showToast(messageFromPayload(payload) || "Your session has expired. Please sign in again.", { type: "warning" });
      try { sessionStorage.setItem("yourin:redirectAfterLogin", window.location.pathname + window.location.search); } catch (_) {}
      if (!/(^|\/)sign-in(\.html)?\/?$/.test(window.location.pathname)) {
        setTimeout(() => { window.location.href = "sign-in.html"; }, 900);
      }
      return "redirect";
    }
    // 400: bad input -> toast
    if (status === 400) {
      showToast(messageFromPayload(payload) || "Some of the information you entered is invalid. Please check and try again.", { type: "error" });
      return "toast";
    }
    // 403: forbidden -> toast (treat like permission)
    if (status === 403) {
      showToast(messageFromPayload(payload) || "You don't have permission to do that.", { type: "error" });
      return "toast";
    }
    // 500/503/network: fallback mode banner
    if (status === 500 || status === 503 || status === 0) {
      const msg = status === 0
        ? "We couldn't reach the server. Check your connection and try again."
        : (messageFromPayload(payload) || "The server or AI service is temporarily unavailable. Please try again.");
      showBanner(msg, {
        type: "warning",
        dismissible: true,
        actionLabel: "Retry",
        onAction: () => { hideBanner(); window.location.reload(); }
      });
      return "banner";
    }
    // other 4xx
    if (status >= 400 && status < 500) {
      showToast(messageFromPayload(payload) || ("Request failed (" + status + ")."), { type: "error" });
      return "toast";
    }
    // other 5xx
    if (status >= 500) {
      showBanner(messageFromPayload(payload) || ("Server error (" + status + "). Switching to fallback mode."), { type: "error" });
      return "banner";
    }
    return null;
  }

  // Expose globally
  window.YourinErrors = {
    showToast,
    showBanner,
    hideBanner,
    handleStatus,
    messageFromPayload
  };
  // Alias for convenience
  window.YourinToast = window.YourinErrors;
})();
