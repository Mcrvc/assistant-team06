/* Shared waiting states: overlay + spinner, rotated status steps, Render cold start. */
(() => {
  "use strict";

  const COLD_START_AFTER = 5000;
  const COLD_START_TEXT = "Free Render instances sleep when idle. This can take up to a minute — your work is not lost.";

  const DEMOS = {
    questions: {
      title: "Creating your interview",
      detail: "Researching the role and writing your questions.",
      steps: [
        "Researching the role and company…",
        "Reading your CV for relevant experience…",
        "Writing three targeted questions…",
        "Preparing what you'll be assessed on…"
      ],
      stepInterval: 2000,
      hideAfter: 8000
    },
    report: {
      title: "Grading your answers",
      detail: "Comparing each answer with the criteria for this role.",
      steps: [
        "Reading your answers against the role criteria…",
        "Checking every score against your own words…",
        "Writing feedback and a recommendation…",
        "Building your final report…"
      ],
      stepInterval: 2000,
      hideAfter: 8000
    },
    "cold-start": {
      title: "Waking up the server",
      detail: "The backend is starting after a period of inactivity.",
      coldStartAfter: 0,
      hideAfter: 12000
    },
    loading: {
      title: "Loading…",
      detail: "Fetching your data from the server.",
      hideAfter: 8000
    }
  };

  let overlay = null;
  let els = null;
  let current = null;
  let restoreFocus = null;

  function build() {
    overlay = document.createElement("div");
    overlay.className = "loading-overlay";
    overlay.hidden = true;
    overlay.innerHTML = [
      '<div class="loading-card" role="alertdialog" aria-modal="true" aria-labelledby="loading-title" aria-describedby="loading-detail" tabindex="-1">',
      '  <div class="loading-visual" aria-hidden="true">',
      '    <span class="loading-ring"></span>',
      '    <img class="loading-logo" src="assets/logo.svg" alt="">',
      '  </div>',
      '  <p class="loading-eyebrow" data-loading-eyebrow>Please wait</p>',
      '  <h2 class="loading-title" id="loading-title" data-loading-title>Working…</h2>',
      '  <p class="loading-detail" id="loading-detail" data-loading-detail></p>',
      '  <div class="loading-bar" aria-hidden="true"><span></span></div>',
      '  <p class="loading-cold" data-loading-cold hidden>',
      '    <strong>Waking up the demo server…</strong>',
      '    <span data-loading-cold-text></span>',
      '    <span class="loading-elapsed" data-loading-elapsed>0s</span>',
      '  </p>',
      '  <button class="btn btn-quiet btn-sm loading-cancel" type="button" data-loading-cancel hidden>Cancel</button>',
      '</div>'
    ].join("");
    document.body.appendChild(overlay);

    els = {
      card: overlay.querySelector(".loading-card"),
      eyebrow: overlay.querySelector("[data-loading-eyebrow]"),
      title: overlay.querySelector("[data-loading-title]"),
      detail: overlay.querySelector("[data-loading-detail]"),
      cold: overlay.querySelector("[data-loading-cold]"),
      coldText: overlay.querySelector("[data-loading-cold-text]"),
      elapsed: overlay.querySelector("[data-loading-elapsed]"),
      cancel: overlay.querySelector("[data-loading-cancel]")
    };

    overlay.addEventListener("keydown", onKeydown);
    els.cancel.addEventListener("click", () => {
      if (!current) return;
      if (typeof current.options.onCancel === "function") current.options.onCancel();
      hide();
    });
  }

  function setDetail(text) {
    if (!text || !els) return;
    els.detail.classList.remove("is-swapping");
    void els.detail.offsetWidth;
    els.detail.textContent = text;
    els.detail.classList.add("is-swapping");
  }

  function markColdStart() {
    if (!current || overlay.hidden) return;
    if (current.stepTimer) {
      clearInterval(current.stepTimer);
      current.stepTimer = null;
    }
    overlay.classList.add("is-cold-start");
    els.cold.hidden = false;
    els.coldText.textContent = current.options.coldStartText;

    const started = current.startedAt;
    current.elapsedTimer = setInterval(() => {
      els.elapsed.textContent = Math.round((Date.now() - started) / 1000) + "s";
    }, 500);
  }

  function clearTimers() {
    if (!current) return;
    ["stepTimer", "coldTimer", "elapsedTimer", "hideTimer"].forEach(key => {
      if (current[key]) {
        clearTimeout(current[key]);
        clearInterval(current[key]);
        current[key] = null;
      }
    });
  }

  function show(options = {}) {
    if (!overlay) build();
    if (current) hide();

    const opts = Object.assign({
      title: "Working…",
      eyebrow: "Please wait",
      detail: "",
      steps: null,
      stepInterval: 1800,
      coldStartAfter: COLD_START_AFTER,
      coldStartText: COLD_START_TEXT,
      cancelLabel: "Cancel",
      onCancel: null,
      hideAfter: 0
    }, options);

    current = { options: opts, stepIndex: 0, startedAt: Date.now() };

    overlay.hidden = false;
    overlay.classList.remove("is-cold-start");
    els.title.textContent = opts.title;
    els.eyebrow.textContent = opts.eyebrow;
    els.detail.textContent = opts.detail || (opts.steps && opts.steps[0]) || "";
    els.cold.hidden = true;
    els.coldText.textContent = opts.coldStartText;
    els.elapsed.textContent = "0s";
    els.cancel.hidden = !opts.onCancel;
    if (opts.onCancel) els.cancel.textContent = opts.cancelLabel;

    restoreFocus = document.activeElement;
    document.body.classList.add("has-loading");
    const main = document.querySelector("main");
    if (main) main.setAttribute("aria-busy", "true");
    requestAnimationFrame(() => els.card.focus({ preventScroll: true }));

    if (opts.steps && opts.steps.length > 1) {
      current.stepTimer = setInterval(() => {
        if (!current) return;
        current.stepIndex = (current.stepIndex + 1) % opts.steps.length;
        setDetail(opts.steps[current.stepIndex]);
      }, opts.stepInterval);
    }

    if (typeof opts.coldStartAfter === "number" && opts.coldStartAfter >= 0) {
      current.coldTimer = setTimeout(markColdStart, opts.coldStartAfter);
    }

    if (opts.hideAfter > 0) {
      current.hideTimer = setTimeout(hide, opts.hideAfter);
    }

    return { update, hide };
  }

  function update(patch = {}) {
    if (!current) return;
    if (patch.title) els.title.textContent = patch.title;
    if (patch.eyebrow) els.eyebrow.textContent = patch.eyebrow;
    if (patch.detail) setDetail(patch.detail);
  }

  function hide() {
    if (!overlay || overlay.hidden) return;
    clearTimers();
    overlay.hidden = true;
    overlay.classList.remove("is-cold-start");
    document.body.classList.remove("has-loading");
    const main = document.querySelector("main");
    if (main) main.removeAttribute("aria-busy");
    if (restoreFocus && typeof restoreFocus.focus === "function") {
      try { restoreFocus.focus({ preventScroll: true }); } catch (_) { restoreFocus.focus(); }
    }
    restoreFocus = null;
    current = null;
  }

  function isVisible() {
    return Boolean(overlay && !overlay.hidden);
  }

  function onKeydown(event) {
    if (!current) return;
    if (event.key === "Escape" && typeof current.options.onCancel === "function") {
      event.preventDefault();
      current.options.onCancel();
      hide();
      return;
    }
    if (event.key !== "Tab") return;

    const focusables = [...overlay.querySelectorAll('button:not([hidden]), a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])')];
    if (focusables.length === 0) {
      event.preventDefault();
      els.card.focus();
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function initDemo() {
    let demo = null;
    try { demo = new URLSearchParams(window.location.search).get("demo"); } catch (_) { /* Older browsers. */ }
    if (!demo || !DEMOS[demo]) return;
    show(DEMOS[demo]);
  }

  window.YourinUI = window.YourinUI || {};
  window.YourinUI.loading = { show, hide, update, isVisible };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDemo, { once: true });
  } else {
    initDemo();
  }
})();
