/* Yourin application controller. Authentication uses Supabase; interview data will move to the API. */
(async () => {
  "use strict";

  const page = document.body.dataset.page;
  const PUBLIC_PAGES = ["sign-in", "sign-up"];

  function showStartupError(message) {
    const authError = (page === "sign-in" || page === "sign-up")
      ? document.querySelector("#auth-error")
      : null;

    if (authError) {
      authError.textContent = message;
      authError.hidden = false;
    } else {
      const main = document.querySelector("main") || document.body;
      main.textContent = "";
      const card = document.createElement("section");
      card.className = "panel";
      card.style.maxWidth = "680px";
      card.style.margin = "80px auto";
      card.style.padding = "32px";
      const heading = document.createElement("h1");
      heading.textContent = "Authentication unavailable";
      const copy = document.createElement("p");
      copy.textContent = message;
      const link = document.createElement("a");
      link.className = "btn";
      link.href = "sign-in.html";
      link.textContent = "Back to sign in";
      card.append(heading, copy, link);
      main.appendChild(card);
    }

    document.querySelectorAll('button[type="submit"]').forEach(button => {
      button.disabled = true;
    });
  }

  try {
    await window.YourinAPIReady;
  } catch (err) {
    console.error("Authentication initialization failed:", err);
    showStartupError(err?.message || "Authentication is not configured. Please contact the team.");
    return;
  }

  const api = window.YourinAPI;
  if (!api) {
    showStartupError("The authentication API could not be initialized.");
    return;
  }

  let authenticatedUser = null;
  try {
    authenticatedUser = await api.getCurrentUser();
  } catch (err) {
    console.error("Session verification failed:", err);
    showStartupError(err?.message || "Unable to verify your session. Please refresh the page.");
    return;
  }

  if (!PUBLIC_PAGES.includes(page) && !authenticatedUser) {
    try {
      sessionStorage.setItem("yourin:redirectAfterLogin", window.location.pathname + window.location.search);
    } catch (_) { /* Session storage may be unavailable. */ }
    window.location.replace("sign-in.html");
    return;
  }

  if (PUBLIC_PAGES.includes(page) && authenticatedUser) {
    window.location.replace("dashboard.html");
    return;
  }

  const DATA = window.POC_DATA;
  if (!DATA) {
    showStartupError("Application data is unavailable.");
    return;
  }

  const USER_ID = authenticatedUser?.id || "anonymous";
  const KEY = `yourin-poc-v2:${USER_ID}`;
  const PREFIX = `yourin-poc:${USER_ID}:`;
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const jobKeys = ["job-source", "job-title", "domain", "company", "position"];
  const manualJobKeys = ["job-title", "domain", "company", "position"];
  const strings = (value, length) => Array.isArray(value) && value.length === length && value.every(item => typeof item === "string");
  const identity = name => String(name || "").trim().toLocaleLowerCase();
  const go = url => { window.location.href = url; };
  const authenticatedUsername = authenticatedUser?.user_metadata?.username || "User";

  function newAccount(username) {
    return {
      username,
      cv: ["", "", "", ""],
      job: {},
      syncCV: true,
      activeId: null,
      feedback: [],
      cvMode: "text",
      cvPdf: null,
      interviews: [1, 2, 3, 4].map(n => ({
        id: "sample-" + n, name: "Interview " + n, date: "29/2/2026",
        finished: n !== 2, sample: true,
        answers: n === 2 ? ["", "", ""] : [...DATA.answers],
        cv: [...DATA.cv], job: {}
      }))
    };
  }
  // Ignore corrupt or incompatible stored state instead of breaking the page.
  function validState(value) {
    return value && value.version === 2 && Number.isFinite(value.updatedAt) &&
      typeof value.currentAccount === "string" && Array.isArray(value.accounts) &&
      value.accounts.length > 0 && value.accounts.every(account =>
        account && typeof account.username === "string" && account.username.trim() &&
        strings(account.cv, 4) && account.job && typeof account.job === "object" &&
        Array.isArray(account.feedback) && Array.isArray(account.interviews) &&
        account.interviews.every(interview =>
          interview && typeof interview.id === "string" && typeof interview.name === "string" &&
          typeof interview.date === "string" && strings(interview.answers, 3) &&
          (interview.cv === null || strings(interview.cv, 4))));
  }
  let state = {
    version: 2, updatedAt: 0, currentAccount: authenticatedUsername,
    accounts: [newAccount(authenticatedUsername)]
  };
  const candidates = [];
  try { candidates.push(JSON.parse(localStorage.getItem(KEY))); } catch (_) { /* Storage may be disabled. */ }
  try {
    if (window.name.startsWith(PREFIX)) candidates.push(JSON.parse(window.name.slice(PREFIX.length)));
  } catch (_) { /* Ignore unrelated window names. */ }
  for (const candidate of candidates) {
    if (validState(candidate) && candidate.updatedAt >= state.updatedAt) state = candidate;
  }
  let account = state.accounts.find(item => identity(item.username) === identity(authenticatedUsername));
  if (!account && state.accounts.length === 1) {
    // The Supabase user id is the storage key, so a username change must keep the same local data.
    account = state.accounts[0];
  }
  if (!account) {
    account = newAccount(authenticatedUsername);
    state.accounts.push(account);
  }
  account.username = authenticatedUsername;
  state.currentAccount = authenticatedUsername;
  if (!account.cvMode) account.cvMode = "text";

  function save() {
    state.updatedAt = Date.now();
    const serialized = JSON.stringify(state);
    try { localStorage.setItem(KEY, serialized); } catch (_) { /* Same-tab fallback below. */ }
    try { window.name = PREFIX + serialized; } catch (_) { /* Static navigation still works. */ }
  }
  function error(selector, message) {
    const element = $(selector);
    if (!element) return;
    element.textContent = message;
    element.hidden = false;
  }
  function activeInterview() {
    return account.interviews.find(item => item.id === account.activeId);
  }
  function reportInterview() {
    return activeInterview() || account.interviews.find(item => item.finished) || account.interviews[0];
  }
  function startInterview(customCV, customPdf, source) {
    const id = "interview-" + Date.now();
    let interviewCV = ["", "", "", ""];
    let interviewPdfItem = null;
    let mode = "text";

    if (customPdf) {
      interviewPdfItem = { ...customPdf };
      mode = "pdf";
    } else if (customCV && customCV.some(text => text && text.trim())) {
      interviewCV = [...customCV];
      mode = "text";
    } else if (source !== "none" && account.syncCV) {
      if (account.cvPdf || account.cvMode === "pdf") {
        interviewPdfItem = account.cvPdf ? { ...account.cvPdf } : null;
        mode = "pdf";
      } else {
        interviewCV = [...account.cv];
        mode = "text";
      }
    }

    const item = {
      id,
      name: "New Interview " + (account.interviews.length + 1),
      date: new Date().toLocaleDateString("en-GB"),
      finished: false,
      answers: ["", "", ""],
      cv: interviewCV,
      cvPdf: interviewPdfItem,
      cvMode: mode,
      job: { ...account.job }
    };
    account.interviews.unshift(item);
    account.activeId = id;
    save();
    return item;
  }
  function buildCvText(value) {
    const parts = Array.isArray(value) ? value : [value];
    return parts
      .map(part => typeof part === "string" ? part.trim() : "")
      .filter(Boolean)
      .join("\n\n")
      .slice(0, 40000) || null;
  }
  function addServerInterview(created, view, options = {}) {
    const details = Array.isArray(view && view.questions) && view.questions.length
      ? view.questions
      : (created && created.question ? [created.question] : []);
    const answers = Array.isArray(view && view.answers)
      ? view.answers.map(answer => (answer && typeof answer.text === "string" ? answer.text : ""))
      : ["", "", ""];
    while (answers.length < 3) answers.push("");
    answers.length = 3;

    const name = typeof view?.name === "string" && view.name.trim()
      ? view.name.trim()
      : (options.name || "New Interview");
    const item = {
      id: created.id,
      name: name.slice(0, 200),
      date: new Date().toLocaleDateString("en-GB"),
      finished: view?.status === "finalized",
      answers,
      cv: Array.isArray(options.cv) && options.cv.length === 4
        ? options.cv.map(part => typeof part === "string" ? part : "")
        : ["", "", "", ""],
      cvPdf: options.cvPdf || null,
      cvMode: options.cvMode || "text",
      job: options.job && typeof options.job === "object" ? { ...options.job } : { ...account.job },
      jobProfile: view?.job_profile || options.jobProfile || null,
      questions: details.map(question => (
        typeof question === "string" ? question : (question && typeof question.text === "string" ? question.text : "")
      )),
      questionDetails: details,
      totalQuestions: Number.isInteger(created.total_questions) && created.total_questions > 0
        ? created.total_questions
        : 3,
      revision: Number.isInteger(view?.revision) ? view.revision : (Number.isInteger(created.revision) ? created.revision : 0),
      status: view?.status || created.status || "in_progress",
      currentQuestion: Number.isInteger(view?.current_question)
        ? view.current_question
        : (Number.isInteger(created.current_question) ? created.current_question : 0),
      progress: view?.progress || null,
      report: view?.report || null,
      questionGeneration: view?.question_generation || created.question_generation || null,
      server: true
    };
    account.interviews.unshift(item);
    account.activeId = item.id;
    save();
    return item;
  }
  function saveJob() {
    account.job = Object.fromEntries(jobKeys.map(key => {
      const el = $("#" + key);
      return [key, el ? el.value.trim() : (account.job && account.job[key] ? account.job[key] : "")];
    }));
    const syncCvCheckbox = $("#sync-cv");
    account.syncCV = syncCvCheckbox ? syncCvCheckbox.checked : account.syncCV !== false;
    account.cvSource = account.syncCV ? "saved" : "none";
    save();
  }
  function saveCV() {
    const profCvRaw = $("#prof-cv-raw");
    if (profCvRaw) {
      account.cv = [profCvRaw.value.trim(), "", "", ""];
    } else {
      const cvInputs = $$("[data-cv]");
      if (cvInputs.length) {
        account.cv = cvInputs.map(input => input.value);
      }
    }
    save();
  }
  function saveAnswer() {
    const input = $("[data-answer]");
    if (!input) return;
    const interview = activeInterview() || startInterview();
    interview.answers[Number(input.dataset.answer)] = input.value;
    save();
  }

  $$("[data-username]").forEach(element => { element.textContent = account.username; });

  const navMap = {
    "dashboard": "dashboard",
    "storage": "storage",
    "system-feedback": "feedback",
    "profile": "profile"
  };
  const activeNav = navMap[page];
  if (activeNav) {
    const activeLink = $(`[data-nav="${activeNav}"]`);
    if (activeLink) activeLink.classList.add("is-active");
  }

  $$("[data-sign-out]").forEach(link => link.addEventListener("click", async event => {
    event.preventDefault();
    try {
      await api.signOut();
    } catch (err) {
      console.error("Sign out failed:", err);
    }
    try { sessionStorage.removeItem("yourin:redirectAfterLogin"); } catch (_) { /* Ignore. */ }
    window.location.replace("sign-in.html");
  }));

  // Toggle password visibility (show/hide)
  $$("[data-toggle-password]").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.togglePassword;
      const input = $("#" + targetId);
      if (!input) return;
      const isPassword = input.type === "password";
      input.type = isPassword ? "text" : "password";
      btn.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
      btn.setAttribute("aria-pressed", isPassword ? "true" : "false");
      btn.setAttribute("title", isPassword ? "Hide password" : "Show password");
      const eyeShow = btn.querySelector(".eye-show");
      const eyeHide = btn.querySelector(".eye-hide");
      if (eyeShow && eyeHide) {
        eyeShow.classList.toggle("is-hidden", isPassword);
        eyeHide.classList.toggle("is-hidden", !isPassword);
      }
    });
  });

  const authForms = $$("#auth-form, #sign-in-form, #sign-up-form, .auth-form");
  authForms.forEach(authForm => {
    authForm.addEventListener("submit", async event => {
      event.preventDefault();

      const authError = $("#auth-error");
      if (authError) {
        authError.hidden = true;
        authError.textContent = "";
      }

      const username = ($("#username")?.value || "").trim();
      const password = $("#password")?.value || "";
      const confirmPassword = $("#confirm-password")?.value || "";

      if (!username || !password) {
        return error("#auth-error", "Enter your username and password.");
      }
      if (page === "sign-up" && password !== confirmPassword) {
        return error("#auth-error", "Passwords do not match.");
      }

      const submitButton = authForm.querySelector('[type="submit"]');
      if (submitButton) submitButton.disabled = true;

      try {
        if (page === "sign-up") {
          const result = await api.signUp(username, password, confirmPassword);
          if (result.requiresEmailConfirmation) {
            error("#auth-error", "Account created, but Supabase requires email confirmation. Ask the team to disable confirmation for @yourin.app accounts.");
            return;
          }
        } else {
          await api.signIn(username, password);
        }

        let target = "dashboard.html";
        try {
          const saved = sessionStorage.getItem("yourin:redirectAfterLogin");
          sessionStorage.removeItem("yourin:redirectAfterLogin");
          if (saved && saved.startsWith("/") && !saved.startsWith("//") &&
              !saved.includes("sign-in.html") && !saved.includes("sign-up.html")) {
            target = saved;
          }
        } catch (_) { /* Session storage may be unavailable. */ }

        window.location.replace(target);
      } catch (err) {
        error("#auth-error", err?.message || "Authentication failed. Please try again.");
      } finally {
        if (submitButton) submitButton.disabled = false;
      }
    });
  });

  $$("[data-new-interview]").forEach(link => link.addEventListener("click", () => {
    account.activeId = null;
    account.job = {};
    save();
  }));

  if (page === "profile") {
    const usernameInput = $("#profile-username");
    const passwordInput = $("#account-password");
    const verifyPasswordInput = $("#verify-password");
    const unlockBtn = $("#unlock-password-btn");
    const passwordUnlockBox = $("#password-unlock-box");
    const profileStatus = $("#profile-status");
    const profileError = $("#profile-error");
    const profileForm = $("#profile-form");

    let isPasswordUnlocked = false;

    function clearProfileError() {
      if (profileError) {
        profileError.hidden = true;
        profileError.textContent = "";
      }
    }

    if (usernameInput) {
      usernameInput.value = authenticatedUsername;
      usernameInput.readOnly = true;
    }
    if (passwordInput) {
      passwordInput.value = "";
      passwordInput.placeholder = "Enter a new password";
      passwordInput.readOnly = true;
      passwordInput.type = "password";
    }

    async function unlockProfile() {
      if (!verifyPasswordInput || !unlockBtn) return;

      const entered = verifyPasswordInput.value;
      clearProfileError();
      if (profileStatus) profileStatus.textContent = "";

      if (!entered) {
        error("#profile-error", "Enter your current password to unlock.");
        verifyPasswordInput.focus();
        return;
      }

      unlockBtn.disabled = true;
      try {
        await api.unlockEditing(entered);
        isPasswordUnlocked = true;
        if (usernameInput) usernameInput.readOnly = false;
        if (passwordInput) passwordInput.readOnly = false;
        if (passwordUnlockBox) passwordUnlockBox.hidden = true;
        if (profileStatus) profileStatus.textContent = "Editing unlocked. Update your username or set a new password.";
        if (passwordInput) passwordInput.focus();
      } catch (err) {
        error("#profile-error", err?.message || "Password verification failed.");
        verifyPasswordInput.focus();
      } finally {
        unlockBtn.disabled = false;
      }
    }

    if (unlockBtn) unlockBtn.addEventListener("click", unlockProfile);

    if (profileForm) {
      profileForm.addEventListener("submit", async event => {
        event.preventDefault();
        clearProfileError();
        if (profileStatus) profileStatus.textContent = "";

        if (!isPasswordUnlocked) {
          return error("#profile-error", "Verify your current password before saving changes.");
        }

        const newUsername = usernameInput ? usernameInput.value.trim().toLowerCase() : "";
        const newPassword = passwordInput ? passwordInput.value : "";

        if (!/^[a-z0-9_]{3,60}$/.test(newUsername)) {
          return error("#profile-error", "Username must contain 3-60 characters: lowercase letters, numbers, or underscores.");
        }
        if (newPassword && (newPassword.length < 8 || newPassword.length > 128)) {
          return error("#profile-error", "A new password must contain 8-128 characters.");
        }

        const saveButton = $("#save-profile");
        if (saveButton) saveButton.disabled = true;

        try {
          await api.updateAccount({ username: newUsername, password: newPassword || undefined });
          authenticatedUser = await api.getCurrentUser();

          account.username = newUsername;
          state.currentAccount = newUsername;
          save();

          $$("[data-username]").forEach(element => { element.textContent = newUsername; });

          if (usernameInput) usernameInput.readOnly = true;
          if (passwordInput) {
            passwordInput.value = "";
            passwordInput.readOnly = true;
            passwordInput.type = "password";
            passwordInput.placeholder = "Enter a new password";
          }
          if (verifyPasswordInput) verifyPasswordInput.value = "";
          if (passwordUnlockBox) passwordUnlockBox.hidden = false;
          isPasswordUnlocked = false;

          if (profileStatus) profileStatus.textContent = "Account information saved.";
        } catch (err) {
          error("#profile-error", err?.message || "Unable to save account changes.");
        } finally {
          if (saveButton) saveButton.disabled = false;
        }
      });
    }

    // CV Section Management
    const cvStatus = $("#cv-status");
    const pdfStatus = $("#pdf-status");
    const pdfError = $("#pdf-error");

    const cvDropzone = $("#cv-pdf-dropzone");
    const cvFileInput = $("#cv-pdf-file-input");
    const cvPdfCard = $("#cv-pdf-card");
    const pdfFileName = $("#pdf-file-name");
    const pdfFileSize = $("#pdf-file-size");
    const pdfFileDate = $("#pdf-file-date");
    const profCvRawInput = $("#prof-cv-raw");

    // Helper to clear raw CV text when user chooses PDF input
    function clearCvSections() {
      if (profCvRawInput) profCvRawInput.value = "";
      account.cv = ["", "", "", ""];
      account.cvMode = "pdf";
      save();
      if (cvStatus) cvStatus.textContent = "";
    }

    // Helper to clear PDF when user types in raw CV text
    function clearPdfFile() {
      if (account.cvPdf) {
        account.cvPdf = null;
        account.cvMode = "text";
        if (cvFileInput) cvFileInput.value = "";
        renderPdfState();
        if (pdfStatus) pdfStatus.textContent = "";
        save();
      }
    }

    // Clear legacy sample text from DATA.cv so profile starts blank by default
    if (Array.isArray(account.cv) && DATA.cv && JSON.stringify(account.cv) === JSON.stringify(DATA.cv)) {
      account.cv = ["", "", "", ""];
      save();
    }

    // Populate Raw CV Textarea (cleared if account has active PDF CV)
    const isPdfActive = Boolean(account.cvPdf || account.cvMode === "pdf");
    if (profCvRawInput) {
      profCvRawInput.value = isPdfActive ? "" : account.cv.filter(s => typeof s === "string" && s.trim()).join("\n\n");
      profCvRawInput.addEventListener("input", () => {
        clearPdfFile();
        saveCV();
        cvStatus.textContent = "Changes saved.";
      });
    }

    $("#save-cv-btn").addEventListener("click", () => {
      clearPdfFile();
      saveCV();
      cvStatus.textContent = "CV saved successfully.";
    });

    // Render PDF Card State
    function renderPdfState() {
      if (account.cvPdf) {
        cvDropzone.classList.add("is-hidden");
        cvPdfCard.classList.remove("is-hidden");
        pdfFileName.textContent = account.cvPdf.name;
        pdfFileSize.textContent = account.cvPdf.size;
        pdfFileDate.textContent = "Uploaded " + (account.cvPdf.date || "recently");
      } else {
        cvDropzone.classList.remove("is-hidden");
        cvPdfCard.classList.add("is-hidden");
      }
    }

    renderPdfState();

    // PDF Upload handling
    function handlePdfFile(file) {
      pdfError.hidden = true;
      if (!file) return;
      if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
        error("#pdf-error", "Please upload a valid PDF file (.pdf).");
        return;
      }
      clearCvSections();
      const sizeStr = file.size > 1024 * 1024
        ? (file.size / (1024 * 1024)).toFixed(1) + " MB"
        : Math.round(file.size / 1024) + " KB";

      account.cvPdf = {
        name: file.name,
        size: sizeStr,
        date: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
      };
      account.cvMode = "pdf";
      save();
      renderPdfState();
      pdfStatus.textContent = `PDF "${file.name}" saved! Raw text cleared.`;
    }

    $("#browse-pdf-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      clearCvSections();
      cvFileInput.click();
    });
    cvDropzone.addEventListener("click", () => {
      clearCvSections();
      cvFileInput.click();
    });
    cvFileInput.addEventListener("change", () => {
      if (cvFileInput.files && cvFileInput.files[0]) {
        handlePdfFile(cvFileInput.files[0]);
      }
    });

    // Drag and Drop
    ["dragenter", "dragover"].forEach(eventName => {
      cvDropzone.addEventListener(eventName, e => {
        e.preventDefault();
        e.stopPropagation();
        cvDropzone.classList.add("drag-over");
      });
    });
    ["dragleave", "drop"].forEach(eventName => {
      cvDropzone.addEventListener(eventName, e => {
        e.preventDefault();
        e.stopPropagation();
        cvDropzone.classList.remove("drag-over");
      });
    });
    cvDropzone.addEventListener("drop", e => {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        handlePdfFile(e.dataTransfer.files[0]);
      }
    });

    // Replace and Remove PDF
    $("#replace-pdf-btn").addEventListener("click", () => {
      clearCvSections();
      cvFileInput.click();
    });
    $("#remove-pdf-btn").addEventListener("click", () => {
      account.cvPdf = null;
      account.cvMode = "text";
      save();
      renderPdfState();
      pdfStatus.textContent = "PDF removed.";
    });
  }

  if (page === "job-profile") {
    // Migrate legacy job-url to job-source if needed
    if (!account.job["job-source"] && typeof account.job["job-url"] === "string" && account.job["job-url"].trim()) {
      account.job["job-source"] = account.job["job-url"].trim();
    }

    jobKeys.forEach(key => {
      const input = $("#" + key);
      if (!input) return;
      input.value = typeof account.job[key] === "string" ? account.job[key] : "";
      input.addEventListener("input", () => {
        const jobError = $("#job-error");
        if (jobError) jobError.hidden = true;
        saveJob();
      });
    });

    // 1. Job Profile Mode Switching (Paste vs Manual) anchored in .panel-header
    const jobPasteMode = $("#job-paste-mode");
    const jobManualMode = $("#job-manual-mode");
    const jobModeSwitchBtn = $("#job-mode-switch-btn");
    const jobModeHint = $("#job-mode-hint");
    let jobInputMode = "paste";

    function setJobMode(mode) {
      jobInputMode = mode;
      const jobError = $("#job-error");
      if (jobError) jobError.hidden = true;
      if (mode === "manual") {
        jobPasteMode.classList.add("is-hidden");
        jobManualMode.classList.remove("is-hidden");
        if (jobModeHint) jobModeHint.textContent = "Have a job description, HTML, or link?";
        if (jobModeSwitchBtn) jobModeSwitchBtn.textContent = "Paste job description instead";
      } else {
        jobManualMode.classList.add("is-hidden");
        jobPasteMode.classList.remove("is-hidden");
        if (jobModeHint) jobModeHint.textContent = "Don't have a job description or link?";
        if (jobModeSwitchBtn) jobModeSwitchBtn.textContent = "Enter 4 fields manually";
      }
    }

    if (jobModeSwitchBtn) {
      jobModeSwitchBtn.addEventListener("click", () => {
        setJobMode(jobInputMode === "paste" ? "manual" : "paste");
      });
    }

    // Always start in paste/link description mode by default
    setJobMode("paste");

    // 2. CV Section Extend Toggle ("Use CV for this interview?")
    const cvSectionToggle = $("#cv-section-toggle");
    const cvSectionBody = $("#cv-section-body");
    let isCvOpen = false;

    function setCvSectionOpen(open) {
      isCvOpen = open;
      if (open) {
        cvSectionBody.classList.remove("is-hidden");
        cvSectionBody.setAttribute("aria-hidden", "false");
        cvSectionToggle.setAttribute("aria-expanded", "true");
        cvSectionToggle.classList.add("is-open");
      } else {
        cvSectionBody.classList.add("is-hidden");
        cvSectionBody.setAttribute("aria-hidden", "true");
        cvSectionToggle.setAttribute("aria-expanded", "false");
        cvSectionToggle.classList.remove("is-open");
      }
    }

    if (cvSectionToggle) {
      cvSectionToggle.addEventListener("click", () => {
        setCvSectionOpen(!isCvOpen);
      });
    }

    // 3. CV Mode Switching inside CV Section (Saved vs Custom)
    const cvSavedMode = $("#cv-saved-mode");
    const cvCustomMode = $("#cv-custom-mode");
    const switchToCustomCvBtn = $("#switch-to-custom-cv");
    const switchToSavedCvBtn = $("#switch-to-saved-cv");
    const syncCvCheckbox = $("#sync-cv");
    const jobCvRawInput = $("#job-cv-raw");
    let cvInputMode = "saved";

    if (syncCvCheckbox) {
      syncCvCheckbox.checked = account.syncCV !== false;
      syncCvCheckbox.addEventListener("change", saveJob);
    }

    function setCvMode(mode) {
      cvInputMode = mode;
      const jobError = $("#job-error");
      if (jobError) jobError.hidden = true;
      if (mode === "custom") {
        cvSavedMode.classList.add("is-hidden");
        cvCustomMode.classList.remove("is-hidden");
      } else {
        cvCustomMode.classList.add("is-hidden");
        cvSavedMode.classList.remove("is-hidden");
      }
    }

    if (switchToCustomCvBtn) {
      switchToCustomCvBtn.addEventListener("click", () => setCvMode("custom"));
    }
    if (switchToSavedCvBtn) {
      switchToSavedCvBtn.addEventListener("click", () => setCvMode("saved"));
    }

    // 4. Custom PDF Upload handling for this interview (Old style dropzone + card)
    let interviewPdf = null;
    const interviewPdfDropzone = $("#interview-pdf-dropzone");
    const interviewPdfInput = $("#interview-pdf-input");
    const interviewPdfCard = $("#interview-pdf-card");
    const interviewPdfName = $("#interview-pdf-name");
    const interviewPdfSize = $("#interview-pdf-size");
    const interviewPdfStatus = $("#interview-pdf-status");

    function clearCustomInterviewPdf() {
      if (interviewPdf) {
        interviewPdf = null;
        if (interviewPdfInput) interviewPdfInput.value = "";
        if (interviewPdfCard) interviewPdfCard.classList.add("is-hidden");
        if (interviewPdfDropzone) interviewPdfDropzone.classList.remove("is-hidden");
        if (interviewPdfStatus) interviewPdfStatus.textContent = "";
      }
    }

    if (jobCvRawInput) {
      jobCvRawInput.addEventListener("input", () => {
        clearCustomInterviewPdf();
      });
    }

    function handleInterviewPdf(file) {
      if (!file) return;
      if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
        if (interviewPdfStatus) interviewPdfStatus.textContent = "Please upload a valid PDF file (.pdf).";
        return;
      }
      if (jobCvRawInput) {
        jobCvRawInput.value = "";
      }
      const sizeStr = file.size > 1024 * 1024
        ? (file.size / (1024 * 1024)).toFixed(1) + " MB"
        : Math.round(file.size / 1024) + " KB";

      interviewPdf = { name: file.name, size: sizeStr };
      if (interviewPdfDropzone) interviewPdfDropzone.classList.add("is-hidden");
      if (interviewPdfCard) interviewPdfCard.classList.remove("is-hidden");
      if (interviewPdfName) interviewPdfName.textContent = file.name;
      if (interviewPdfSize) interviewPdfSize.textContent = sizeStr;
      if (interviewPdfStatus) interviewPdfStatus.textContent = `Attached "${file.name}" to this interview.`;
    }

    if (interviewPdfDropzone) {
      interviewPdfDropzone.addEventListener("click", () => {
        if (interviewPdfInput) interviewPdfInput.click();
      });
      interviewPdfDropzone.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (interviewPdfInput) interviewPdfInput.click();
        }
      });
      ["dragenter", "dragover"].forEach(eventName => {
        interviewPdfDropzone.addEventListener(eventName, e => {
          e.preventDefault();
          e.stopPropagation();
          interviewPdfDropzone.classList.add("drag-over");
        });
      });
      ["dragleave", "drop"].forEach(eventName => {
        interviewPdfDropzone.addEventListener(eventName, e => {
          e.preventDefault();
          e.stopPropagation();
          interviewPdfDropzone.classList.remove("drag-over");
        });
      });
      interviewPdfDropzone.addEventListener("drop", e => {
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleInterviewPdf(e.dataTransfer.files[0]);
        }
      });
    }

    const interviewBrowseBtn = $("#interview-browse-pdf-btn");
    if (interviewBrowseBtn) {
      interviewBrowseBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (interviewPdfInput) interviewPdfInput.click();
      });
    }

    if (interviewPdfInput) {
      interviewPdfInput.addEventListener("change", () => {
        if (interviewPdfInput.files && interviewPdfInput.files[0]) {
          handleInterviewPdf(interviewPdfInput.files[0]);
        }
      });
    }

    const interviewReplaceBtn = $("#interview-replace-pdf-btn");
    if (interviewReplaceBtn) {
      interviewReplaceBtn.addEventListener("click", () => {
        if (interviewPdfInput) interviewPdfInput.click();
      });
    }

    const interviewRemoveBtn = $("#interview-remove-pdf-btn");
    if (interviewRemoveBtn) {
      interviewRemoveBtn.addEventListener("click", () => {
        clearCustomInterviewPdf();
        if (jobCvRawInput) {
          jobCvRawInput.value = "";
          jobCvRawInput.focus();
        }
      });
    }

    $("#job-form").addEventListener("submit", async event => {
      event.preventDefault();
      const jobError = $("#job-error");
      if (jobError) jobError.hidden = true;
      saveJob();

      if (jobInputMode === "paste") {
        if (!account.job["job-source"]) {
          return error("#job-error", "Paste a job description, HTML, or job link, or click 'Enter 4 fields manually'.");
        }
      } else {
        if (manualJobKeys.some(key => !account.job[key])) {
          return error("#job-error", "Enter a value for each of the 4 job profile fields.");
        }
      }

      let cvText = null;
      let cvLocal = ["", "", "", ""];
      let cvPdf = null;
      let cvMode = "text";

      if (isCvOpen) {
        if (cvInputMode === "custom") {
          if (interviewPdf) {
            // The backend accepts CV text. PDF extraction is not part of this checkout yet.
            cvPdf = { ...interviewPdf };
            cvMode = "pdf";
          } else {
            const rawText = jobCvRawInput ? jobCvRawInput.value.trim() : "";
            if (!rawText) {
              return error("#job-error", "Paste your CV text or upload a PDF resume, or switch back to saved CV.");
            }
            cvLocal = [rawText, "", "", ""];
            cvText = buildCvText(rawText);
            cvMode = "text";
          }
        } else if (syncCvCheckbox && syncCvCheckbox.checked) {
          if (account.cvPdf || account.cvMode === "pdf") {
            cvPdf = account.cvPdf ? { ...account.cvPdf } : null;
            cvMode = "pdf";
          } else {
            cvLocal = [...account.cv];
            cvText = buildCvText(account.cv);
            cvMode = "text";
          }
        }
      }

      const jobTitle = (account.job["job-title"] || "").trim();
      const jobProfile = {
        title: jobTitle.slice(0, 200),
        domain: (account.job.domain || "").trim().slice(0, 200),
        company: (account.job.company || "").trim().slice(0, 200),
        level: (account.job.position || "").trim().slice(0, 200),
        description: (jobInputMode === "paste" ? (account.job["job-source"] || "").trim() : "").slice(0, 20000)
      };
      const payload = {
        job_profile: jobProfile,
        cv: cvText,
        name: (jobTitle || "New Interview " + (account.interviews.length + 1)).slice(0, 200)
      };

      const submitButton = $("#job-form button[type='submit']");
      const originalButtonText = submitButton ? submitButton.textContent : "";
      let loading = null;
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Creating interview...";
      }
      if (window.YourinUI?.loading?.show) {
        loading = window.YourinUI.loading.show({
          title: "Creating your interview",
          eyebrow: "Please wait",
          detail: "Reading the role and writing your first questions.",
          steps: [
            "Reading the job profile...",
            "Finding role-specific themes...",
            "Writing three interview questions...",
            "Preparing your interview..."
          ],
          coldStartAfter: 5000
        });
      }

      try {
        const result = await api.request("/api/interviews", {
          method: "POST",
          body: JSON.stringify(payload),
          loading: false
        });
        if (!result.ok || !result.data || !result.data.id) {
          const message = window.YourinErrors?.messageFromPayload?.(result.data) ||
            "Unable to create the interview. Please try again.";
          error("#job-error", message);
          return;
        }

        const created = result.data;
        const viewResult = await api.request(`/api/interviews/${encodeURIComponent(created.id)}`, {
          loading: false
        });
        if (viewResult.status === 401) return;
        const view = viewResult.ok ? viewResult.data : null;
        if (!view) {
          window.YourinErrors?.showToast?.(
            "Interview created, but the full question list could not be loaded. Reopen it from Your Interview.",
            { type: "warning" }
          );
        }

        addServerInterview(created, view, {
          name: payload.name,
          cv: cvLocal,
          cvPdf,
          cvMode,
          job: { ...account.job },
          jobProfile
        });
        go("interview.html");
      } catch (err) {
        console.error("Interview creation failed:", err);
        error("#job-error", "Unable to create the interview. Please try again.");
      } finally {
        if (loading) loading.hide();
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = originalButtonText;
        }
      }
    });
    $$("[data-save-job]").forEach(link => link.addEventListener("click", saveJob));
  }

  if (page === "interview" || page === "interview-1" || page === "interview-2" || page === "interview-3" || $("#interview-step-track")) {
    const interview = activeInterview() || startInterview();

    function isServerInterview() {
      return Boolean(interview && interview.server === true && interview.id);
    }

    function applyServerView(target, view) {
      if (!target || !view) return;
      if (typeof view.name === "string" && view.name.trim()) target.name = view.name.trim();
      if (typeof view.status === "string") target.status = view.status;
      if (Number.isInteger(view.revision)) target.revision = view.revision;
      if (Number.isInteger(view.current_question)) target.currentQuestion = view.current_question;
      if (Array.isArray(view.questions)) {
        target.questionDetails = view.questions;
        target.questions = view.questions.map(question => (
          typeof question === "string" ? question : (question && typeof question.text === "string" ? question.text : "")
        ));
        target.totalQuestions = view.questions.length || target.totalQuestions || 3;
      }
      target.report = view.report || target.report || null;
      const answers = Array.isArray(view.answers) ? view.answers : [];
      const texts = [];
      const statuses = [];
      const grades = [];
      const errors = [];
      for (let i = 0; i < 3; i++) {
        const answer = answers[i] || {};
        texts.push(typeof answer.text === "string" ? answer.text : "");
        statuses.push(typeof answer.grading_status === "string" ? answer.grading_status : "unanswered");
        grades.push(answer.grade || null);
        errors.push(answer.error_code || null);
      }
      target.answers = texts;
      target.answerStatuses = statuses;
      target.answerGrades = grades;
      target.answerErrors = errors;
      target.submittedTexts = texts.slice();
      save();
    }

    async function refreshServerInterview() {
      if (!isServerInterview()) return null;
      const result = await api.request(`/api/interviews/${encodeURIComponent(interview.id)}`, {
        loading: false,
        notify: false
      });
      if (result.ok && result.data) applyServerView(interview, result.data);
      else if (result.status === 409) {
        // keep local state; backend may have moved
      }
      return result;
    }

    async function submitCurrentAnswer(index) {
      if (!isServerInterview()) return true;
      const text = String(interview.answers[index] || "");
      if (!text.trim()) return true;
      const status = Array.isArray(interview.answerStatuses) ? interview.answerStatuses[index] : "";
      const submitted = Array.isArray(interview.submittedTexts) ? String(interview.submittedTexts[index] || "") : "";
      if ((status === "graded" || status === "pending") && text === submitted) {
        return true;
      }
      try {
        const result = await api.request(`/api/interviews/${encodeURIComponent(interview.id)}/answers/${index}`, {
          method: "POST",
          body: JSON.stringify({ revision: interview.revision, text }),
          loading: false
        });
        if (!result.ok || !result.data) {
          if (result.status === 409) await refreshServerInterview();
          if (window.YourinErrors && typeof window.YourinErrors.handleStatus === "function") {
            window.YourinErrors.handleStatus(result.status, result.data);
          }
          return false;
        }
        applyServerView(interview, result.data);
        startGradingPoll();
        updateAnswerStatusUI();
        return true;
      } catch (err) {
        console.error("Submit answer failed:", err);
        return false;
      }
    }

    async function saveProgressToServer(targetStep) {
      if (!isServerInterview()) return;
      try {
        const result = await api.request(`/api/interviews/${encodeURIComponent(interview.id)}/progress`, {
          method: "POST",
          body: JSON.stringify({
            revision: interview.revision,
            current_question: Math.max(0, Math.min(2, targetStep)),
            status: "in_progress",
            answers: interview.answers
          }),
          loading: false,
          notify: false
        });
        if (result.ok && result.data) applyServerView(interview, result.data);
        else if (result.status === 409) await refreshServerInterview();
      } catch (_) { /* network errors are surfaced by the shared layer */ }
    }

    let gradingPoll = null;
    function startGradingPoll() {
      if (!isServerInterview() || gradingPoll) return;
      gradingPoll = window.setInterval(async () => {
        const hasPending = Array.isArray(interview.answerStatuses) && interview.answerStatuses.some(status => status === "pending");
        if (!hasPending) {
          window.clearInterval(gradingPoll);
          gradingPoll = null;
          return;
        }
        await refreshServerInterview();
        updateAnswerStatusUI();
      }, 3000);
    }

    function updateAnswerStatusUI() {
      const status = Array.isArray(interview.answerStatuses) ? (interview.answerStatuses[currentStep] || "") : "";
      let element = document.getElementById("answer-status");
      if (!element) {
        element = document.createElement("span");
        element.id = "answer-status";
        element.style.marginLeft = "0.75rem";
        element.style.fontSize = "0.85rem";
        const badge = document.getElementById("question-badge");
        if (badge && badge.parentNode) badge.parentNode.insertBefore(element, badge.nextSibling);
      }
      const grade = Array.isArray(interview.answerGrades) ? interview.answerGrades[currentStep] : null;
      if (status === "graded" && grade && typeof grade.score === "number") {
        element.textContent = `Graded: ${grade.score}/10`;
      } else if (status === "pending") {
        element.textContent = "Grading...";
      } else if (status === "rejected") {
        const code = Array.isArray(interview.answerErrors) ? interview.answerErrors[currentStep] : null;
        element.textContent = code ? `Rejected (${code})` : "Rejected - resubmit";
      } else if (status === "draft") {
        element.textContent = "Draft";
      } else {
        element.textContent = "";
      }
    }

    if (isServerInterview()) {
      if (!Array.isArray(interview.answerStatuses)) interview.answerStatuses = ["unanswered", "unanswered", "unanswered"];
      if (!Array.isArray(interview.answerGrades)) interview.answerGrades = [null, null, null];
      if (!Array.isArray(interview.answerErrors)) interview.answerErrors = [null, null, null];
      if (!Array.isArray(interview.submittedTexts)) interview.submittedTexts = ["", "", ""];
      try {
        const initial = await api.request(`/api/interviews/${encodeURIComponent(interview.id)}`, { loading: false, notify: false });
        if (initial.ok && initial.data) applyServerView(interview, initial.data);
      } catch (_) {}
      if (Array.isArray(interview.answerStatuses) && interview.answerStatuses.some(status => status === "pending")) {
        startGradingPoll();
      }
    }

    const fallbackQuestions = DATA.questions || [
      "Imagine you're tasked with curating a time capsule that defines the year 2026 for an alien civilization. What are three objects you put inside?",
      "To be, or not to be, that is the question: whether 'tis nobler in the mind to suffer the slings and arrows of outrageous fortune, or to take arms against a sea of troubles, and by opposing end them.",
      "Wat een wartaa. Het is echt niet alsof ik bezorgd om je was ofzo. Mijn colonne verplaatste zich puur toevallig langs deze strategische route, dus haal je maar niks in je hoofd, begrepen?"
    ];
    const storedQuestions = Array.isArray(interview.questions)
      ? interview.questions.filter(question => typeof question === "string")
      : [];
    const usesStoredQuestions = interview.server === true || storedQuestions.length > 0;
    const questions = usesStoredQuestions ? storedQuestions : fallbackQuestions;
    const totalQuestions = usesStoredQuestions
      ? (Number.isInteger(interview.totalQuestions) && interview.totalQuestions > 0
        ? interview.totalQuestions
        : Math.max(3, questions.length))
      : questions.length;

    let currentStep = 0;
    try {
      const params = new URLSearchParams(window.location.search);
      const qParam = parseInt(params.get("q"), 10);
      if (!isNaN(qParam) && qParam >= 1 && qParam <= Math.max(1, questions.length)) {
        currentStep = qParam - 1;
      }
    } catch (_) {}

    const answerSlots = 3;
    while (interview.answers.length < answerSlots) {
      interview.answers.push("");
    }
    interview.answers.length = answerSlots;
    if (!Array.isArray(interview.answerStatuses)) interview.answerStatuses = ["unanswered", "unanswered", "unanswered"];
    if (!Array.isArray(interview.answerGrades)) interview.answerGrades = [null, null, null];
    if (!Array.isArray(interview.answerErrors)) interview.answerErrors = [null, null, null];
    if (!Array.isArray(interview.submittedTexts)) interview.submittedTexts = ["", "", ""];
    while (interview.answerStatuses.length < answerSlots) interview.answerStatuses.push("unanswered");
    while (interview.answerGrades.length < answerSlots) interview.answerGrades.push(null);
    while (interview.answerErrors.length < answerSlots) interview.answerErrors.push(null);
    while (interview.submittedTexts.length < answerSlots) interview.submittedTexts.push("");
    interview.answerStatuses.length = answerSlots;
    interview.answerGrades.length = answerSlots;
    interview.answerErrors.length = answerSlots;
    interview.submittedTexts.length = answerSlots;
    const questionTitle = $("#question-title");
    const questionBadge = $("#question-badge");
    const questionText = $("#question-text");
    const answerInput = $("#answer");
    const charCountEl = $("#answer-char-count");
    const prevBtn = $("#prev-question-btn");
    const nextBtn = $("#next-question-btn");
    const micToggleBtn = $("#mic-toggle-btn");
    const micLabel = $("#mic-btn-label");
    const micSub = $("#mic-btn-sub");
    const voiceWaveform = $("#voice-waveform");
    const exitModal = $("#interview-exit-modal");
    const exitModalName = $("#saved-name");
    const exitModalConfirmBtn = $("#exit-modal-confirm-btn");

    const robotStage = $("#robot-stage");
    const robotReplayBtn = $("#robot-replay-btn");
    let mimeTimer = null;
    let typingGazeTimer = null;

    let isRecording = false;
    let recordingTimer = null;

    function setRobotGaze(x, y) {
      if (!robotStage) return;
      robotStage.style.setProperty("--eye-x", `${x}px`);
      robotStage.style.setProperty("--eye-y", `${y}px`);
    }

    function resetRobotGaze() {
      if (!robotStage) return;
      setRobotGaze(0, 0);
      robotStage.classList.remove("is-watching", "is-typing");
    }

    function updateGazeOnTyping() {
      if (!robotStage || !answerInput) return;
      if (robotStage.classList.contains("is-miming")) return;

      robotStage.classList.remove("is-idle");
      robotStage.classList.add("is-watching", "is-typing");

      const text = answerInput.value;
      const cursorPos = answerInput.selectionStart ?? text.length;
      const totalLen = Math.max(1, text.length);
      const ratio = Math.max(0, Math.min(1, cursorPos / totalLen));
      const eyeX = (ratio - 0.5) * 6.4;
      setRobotGaze(eyeX.toFixed(1), 3.5);

      if (typingGazeTimer) clearTimeout(typingGazeTimer);
      typingGazeTimer = setTimeout(() => {
        if (!robotStage.classList.contains("is-miming") && !isRecording) {
          robotStage.classList.remove("is-typing");
          setRobotGaze(0, 2);
        }
      }, 1600);
    }

    function startRobotMime(customDuration) {
      if (!robotStage) return;
      if (mimeTimer) clearTimeout(mimeTimer);
      if (typingGazeTimer) clearTimeout(typingGazeTimer);
      resetRobotGaze();
      robotStage.classList.remove("is-idle", "is-listening", "is-watching", "is-typing");
      robotStage.classList.add("is-miming");

      const qText = questions[currentStep] || "";
      const duration = customDuration || Math.max(3000, Math.min(5500, qText.length * 40));

      mimeTimer = setTimeout(() => {
        stopRobotMime();
      }, duration);
    }

    function stopRobotMime() {
      if (mimeTimer) clearTimeout(mimeTimer);
      if (!robotStage) return;
      robotStage.classList.remove("is-miming");
      if (!isRecording) {
        robotStage.classList.add("is-idle");
      }
    }

    if (robotReplayBtn) {
      robotReplayBtn.addEventListener("click", () => {
        startRobotMime();
      });
    }

    function updateCharCount() {
      if (!charCountEl || !answerInput) return;
      const count = answerInput.value.length;
      charCountEl.textContent = `${count} character${count === 1 ? "" : "s"}`;
    }

    function renderStep(index) {
      currentStep = Math.max(0, Math.min(index, totalQuestions - 1));

      if (questionTitle) questionTitle.textContent = `Question ${currentStep + 1}`;
      if (questionBadge) questionBadge.textContent = `${currentStep + 1} of ${totalQuestions}`;
      updateAnswerStatusUI();
      if (questionText) {
        const text = questions[currentStep];
        questionText.textContent = typeof text === "string" && text.trim()
          ? text
          : "This question is not available yet. Please reopen the interview from Your Interview.";
      }
      if (answerInput) {
        answerInput.dataset.answer = currentStep;
        answerInput.value = interview.answers[currentStep] || "";
        updateCharCount();
      }

      if (prevBtn) {
        if (currentStep === 0) {
          prevBtn.classList.add("is-hidden");
        } else {
          prevBtn.classList.remove("is-hidden");
        }
      }

      if (nextBtn) {
        const hasCurrent = typeof questions[currentStep] === "string" && questions[currentStep].trim();
        const hasNext = typeof questions[currentStep + 1] === "string" && questions[currentStep + 1].trim();
        nextBtn.disabled = !hasCurrent || (currentStep < totalQuestions - 1 && !hasNext);
        if (currentStep === totalQuestions - 1) {
          nextBtn.textContent = "Finalize Interview";
        } else {
          nextBtn.textContent = "Next Question →";
        }
      }

      if (isRecording) {
        stopRecording();
      }

      startRobotMime();
    }

    if (answerInput) {
      answerInput.addEventListener("input", () => {
        interview.answers[currentStep] = answerInput.value;
        save();
        updateCharCount();
        updateGazeOnTyping();
      });

      answerInput.addEventListener("focus", () => {
        if (!robotStage.classList.contains("is-miming") && !isRecording) {
          robotStage.classList.add("is-watching");
          setRobotGaze(0, 3);
        }
      });

      answerInput.addEventListener("blur", () => {
        if (!isRecording) {
          resetRobotGaze();
          if (!robotStage.classList.contains("is-miming")) {
            robotStage.classList.add("is-idle");
          }
        }
      });

      answerInput.addEventListener("keyup", updateGazeOnTyping);
      answerInput.addEventListener("click", updateGazeOnTyping);
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", async () => {
        if (currentStep > 0) {
          if (answerInput) interview.answers[currentStep] = answerInput.value;
          save();
          if (isServerInterview()) {
            await submitCurrentAnswer(currentStep);
            await saveProgressToServer(currentStep - 1);
          }
          renderStep(currentStep - 1);
          updateAnswerStatusUI();
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", async () => {
        if (answerInput) interview.answers[currentStep] = answerInput.value;
        save();

        if (isServerInterview()) {
          await submitCurrentAnswer(currentStep);
        }

        if (currentStep < totalQuestions - 1) {
          if (isServerInterview()) await saveProgressToServer(currentStep + 1);
          renderStep(currentStep + 1);
          updateAnswerStatusUI();
        } else {
          if (isServerInterview()) {
            await submitCurrentAnswer(currentStep);
            await saveProgressToServer(currentStep);
          }
          interview.finished = true;
          save();
          go("done-interview.html");
        }
      });
    }

    // Trigger Save & Exit whenever the user attempts to exit the interview screen
    function triggerSaveAndExit(targetHref) {
      if (answerInput) interview.answers[currentStep] = answerInput.value;
      save();
      if (isServerInterview()) {
        saveProgressToServer(currentStep).catch(() => {});
      }

      if (exitModal) {
        if (exitModalName) exitModalName.textContent = interview.name;
        if (exitModalConfirmBtn) {
          const destination = targetHref || "dashboard.html";
          exitModalConfirmBtn.href = destination;
          exitModalConfirmBtn.textContent = "Proceed";
        }
        exitModal.classList.remove("is-hidden");
        $(".site-header").inert = true;
        const mainPanel = $(".interview-panel");
        if (mainPanel) mainPanel.inert = true;
        const footer = $(".site-footer");
        if (footer) footer.inert = true;
        if (exitModalConfirmBtn) exitModalConfirmBtn.focus();
      } else {
        go("interview-interrupt.html");
      }
    }

    $$(".site-header a").forEach(link => {
      link.addEventListener("click", e => {
        e.preventDefault();
        triggerSaveAndExit(link.getAttribute("href") || "dashboard.html");
      });
    });

    try {
      history.pushState({ interview: true }, "");
      window.addEventListener("popstate", () => {
        triggerSaveAndExit("dashboard.html");
      });
    } catch (_) {}

    function startRecording() {
      isRecording = true;
      if (robotStage) {
        if (mimeTimer) clearTimeout(mimeTimer);
        if (typingGazeTimer) clearTimeout(typingGazeTimer);
        robotStage.classList.remove("is-miming", "is-idle", "is-watching", "is-typing");
        robotStage.classList.add("is-listening");
        setRobotGaze(0, 3.5);
      }
      if (micToggleBtn) micToggleBtn.classList.add("is-recording");
      if (micLabel) micLabel.textContent = "Recording... (Click to stop)";
      if (micSub) micSub.textContent = "Listening to your voice...";
      if (voiceWaveform) voiceWaveform.classList.add("is-active");

      recordingTimer = setTimeout(() => {
        if (isRecording && answerInput) {
          const sampleSpoken = [
            " In my perspective, this role requires strong adaptability and rapid problem-solving.",
            " Furthermore, I prioritize clear communication and delivering reliable results under pressure.",
            " My previous background gives me a distinct advantage in tackling complex technical challenges."
          ];
          const addition = sampleSpoken[currentStep] || " I believe this approach creates the strongest foundation for success.";
          answerInput.value = (answerInput.value.trim() ? answerInput.value.trim() + " " : "") + addition.trim();
          interview.answers[currentStep] = answerInput.value;
          save();
          updateCharCount();
        }
      }, 2400);
    }

    function stopRecording() {
      isRecording = false;
      if (recordingTimer) clearTimeout(recordingTimer);
      if (robotStage) {
        robotStage.classList.remove("is-listening");
        resetRobotGaze();
        robotStage.classList.add("is-idle");
      }
      if (micToggleBtn) micToggleBtn.classList.remove("is-recording");
      if (micLabel) micLabel.textContent = "Record Answer with Microphone";
      if (micSub) micSub.textContent = "Click to start speech-to-text";
      if (voiceWaveform) voiceWaveform.classList.remove("is-active");
    }

    if (micToggleBtn) {
      micToggleBtn.addEventListener("click", () => {
        if (isRecording) {
          stopRecording();
        } else {
          startRecording();
        }
      });
    }

    $$("[data-save-answer]").forEach(link => link.addEventListener("click", () => {
      if (answerInput) interview.answers[currentStep] = answerInput.value;
      save();
      if (isServerInterview()) saveProgressToServer(currentStep).catch(() => {});
    }));

    window.addEventListener("pagehide", () => {
      if (gradingPoll) window.clearInterval(gradingPoll);
    }, { once: true });

    renderStep(currentStep);
    updateAnswerStatusUI();
    if (isServerInterview() && Array.isArray(interview.answerStatuses) && interview.answerStatuses.some(status => status === "pending")) {
      startGradingPoll();
    }
  }

  if (page === "interview-interrupt") {
    const interview = activeInterview();
    if (interview) $("#saved-name").textContent = interview.name;
    $(".site-header").inert = true;
    $(".site-footer").inert = true;
    const home = $(".saved-dialog a");
    home.focus();
    // The source uses a dedicated frame for this dialog.
    $(".saved-dialog").addEventListener("keydown", event => {
      if (event.key === "Tab") { event.preventDefault(); home.focus(); }
    });
  }

  if (page === "done-interview") {
    $("#done-form").addEventListener("submit", event => {
      event.preventDefault();
      const interview = activeInterview() || startInterview();
      const name = $("#interview-name").value.trim();
      if (name) interview.name = name;
      interview.finished = true;
      save();
      go("report.html");
    });
  }

  if (page === "storage") {
    const listContainer = $("#interview-list");
    const emptyContainer = $("#storage-empty");
    const gridHead = $(".storage-grid-head");

    function renderInterviews() {
      listContainer.replaceChildren();
      const total = account.interviews ? account.interviews.length : 0;

      if (total === 0) {
        if (gridHead) gridHead.classList.add("is-hidden");
        if (emptyContainer) emptyContainer.classList.remove("is-hidden");
        return;
      }

      if (gridHead) gridHead.classList.remove("is-hidden");
      if (emptyContainer) emptyContainer.classList.add("is-hidden");

      account.interviews.forEach((interview, index) => {
        const row = document.createElement("div");
        row.className = "storage-row-card";

        // Col 1: Name (inline editable)
        const colName = document.createElement("div");
        colName.className = "col-name-wrap";

        const title = document.createElement("span");
        title.className = "session-title";
        title.textContent = interview.name;
        title.title = "Click to rename";

        const editBtn = document.createElement("button");
        editBtn.type = "button";
        editBtn.className = "btn-session-rename";
        editBtn.title = "Edit interview name";
        editBtn.setAttribute("aria-label", `Edit name for ${interview.name}`);
        editBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>`;

        function openRenameEditor() {
          colName.replaceChildren();
          const editor = document.createElement("div");
          editor.className = "session-rename-editor";

          const input = document.createElement("input");
          input.type = "text";
          input.className = "session-rename-input";
          input.value = interview.name;
          input.maxLength = 80;
          input.setAttribute("aria-label", "Interview name");

          const saveBtn = document.createElement("button");
          saveBtn.type = "button";
          saveBtn.className = "btn-rename-confirm";
          saveBtn.title = "Save name";
          saveBtn.setAttribute("aria-label", "Save interview name");
          saveBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>`;

          const cancelBtn = document.createElement("button");
          cancelBtn.type = "button";
          cancelBtn.className = "btn-rename-cancel";
          cancelBtn.title = "Cancel";
          cancelBtn.setAttribute("aria-label", "Cancel editing name");
          cancelBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;

          let closed = false;
          function commitRename() {
            if (closed) return;
            closed = true;
            const newName = input.value.trim();
            if (newName) {
              interview.name = newName;
              save();
            }
            renderInterviews();
          }

          function cancelRename() {
            if (closed) return;
            closed = true;
            renderInterviews();
          }

          saveBtn.addEventListener("mousedown", e => e.preventDefault());
          saveBtn.addEventListener("click", commitRename);

          cancelBtn.addEventListener("mousedown", e => e.preventDefault());
          cancelBtn.addEventListener("click", cancelRename);

          input.addEventListener("keydown", e => {
            if (e.key === "Enter") {
              e.preventDefault();
              commitRename();
            } else if (e.key === "Escape") {
              e.preventDefault();
              cancelRename();
            }
          });

          input.addEventListener("blur", commitRename);

          editor.append(input, saveBtn, cancelBtn);
          colName.append(editor);
          input.focus();
          input.select();
        }

        title.addEventListener("click", openRenameEditor);
        editBtn.addEventListener("click", openRenameEditor);

        colName.append(title, editBtn);

        // Col 2: Date
        const colDate = document.createElement("div");
        colDate.className = "col-date-text";
        colDate.textContent = interview.date;

        // Col 3: Status
        const colStatus = document.createElement("div");
        colStatus.className = "col-status-wrap";

        const status = document.createElement("span");
        status.className = "status" + (interview.finished ? "" : " unfinished");
        status.textContent = interview.finished ? "Finished" : "Unfinished";
        colStatus.append(status);

        // Col 4: Actions (View report / Continue + Delete)
        const colActions = document.createElement("div");
        colActions.className = "col-actions-group";

        const actionLink = document.createElement("a");
        actionLink.className = "btn btn-secondary btn-session-action";
        actionLink.href = interview.finished ? "report.html" : "interview.html";
        actionLink.textContent = interview.finished ? "View report" : "Continue";
        actionLink.addEventListener("click", () => {
          account.activeId = interview.id;
          save();
        });

        const deleteBtn = document.createElement("button");
        deleteBtn.className = "btn-session-delete";
        deleteBtn.type = "button";
        deleteBtn.textContent = "Delete";
        deleteBtn.title = "Delete this interview";
        deleteBtn.addEventListener("click", () => {
          account.interviews.splice(index, 1);
          if (account.activeId === interview.id) account.activeId = null;
          save();
          renderInterviews();
        });

        colActions.append(actionLink, deleteBtn);

        row.append(colName, colDate, colStatus, colActions);
        listContainer.append(row);
      });
    }

    renderInterviews();
  }

  if (page === "report") {
    const interview = reportInterview();
    if (interview) {
      if ($("#report-name")) $("#report-name").textContent = interview.name;
      if ($("#report-date") && interview.date) $("#report-date").textContent = interview.date;

      $$("[data-report-answer]").forEach((element, index) => {
        element.textContent = interview.answers[index] || "No answer provided.";
      });

      // Retake interview button: creates a fresh interview with the same CV and Job profile
      const retakeBtn = $("#retake-interview-btn");
      if (retakeBtn) {
        retakeBtn.addEventListener("click", event => {
          event.preventDefault();
          const newInt = startInterview(
            interview.cv,
            interview.cvPdf,
            interview.cvMode === "pdf" ? "saved" : (interview.cv && interview.cv.some(s => s && s.trim()) ? "custom" : "none")
          );
          if (interview.job) newInt.job = { ...interview.job };
          save();
          go("interview.html");
        });
      }
    }
  }
  if (page === "system-feedback") {
    const inputs = [0, 1, 2, 3].map(i => $("#feedback-" + i));
    inputs.forEach((input, index) => {
      input.value = typeof account.feedback[index] === "string" ? account.feedback[index] : "";
      input.addEventListener("input", () => { account.feedback = inputs.map(item => item.value); save(); });
    });
    $("#feedback-form").addEventListener("submit", event => {
      event.preventDefault();
      account.feedback = inputs.map(input => input.value);
      save();
      go("thank-you.html");
    });
  }
  if (page === "dashboard") {
    const cards = $$(".reveal-on-scroll");
    if (cards.length > 0) {
      document.body.classList.add("js-scroll-ready");
      if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver((entries, obs) => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              obs.unobserve(entry.target);
            }
          });
        }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
        cards.forEach(card => observer.observe(card));
      } else {
        const checkScroll = () => {
          const triggerBottom = window.innerHeight * 0.92;
          cards.forEach(card => {
            if (card.getBoundingClientRect().top < triggerBottom) {
              card.classList.add("is-visible");
            }
          });
        };
        window.addEventListener("scroll", checkScroll, { passive: true });
        checkScroll();
      }
    }
  }

  // Preserve state between separate file:// documents in the same tab.
  window.addEventListener("pagehide", save);
})().catch(error => {
  console.error("Application initialization failed:", error);
  const main = document.querySelector("main") || document.body;
  main.textContent = "Unable to start the application. Please refresh the page.";
});
