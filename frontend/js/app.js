/* Yourin - Supabase Authentication and Application Logic */
(async () => {
  "use strict";

  const page = document.body.dataset.page;
  const PUBLIC_PAGES = ["sign-in", "sign-up"];

  // Load a script only when it is not already available.
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Unable to load ${src}`));
      document.head.appendChild(script);
    });
  }

  // Initialize Supabase and the authentication API.
  try {
    if (!window.supabase?.createClient) {
      await loadScript(
        "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"
      );
    }

    if (!window.YourinConfigPromise) {
      await loadScript("js/config.js");
    }

    if (!window.YourinAPIReady) {
      await loadScript("js/api.js");
    }

    // Wait until Supabase configuration and authentication
    // functions have finished initializing.
    await window.YourinAPIReady;

    if (!window.YourinAPI) {
      throw new Error(
        "Authentication API initialization was unsuccessful."
      );
    }

  } catch (err) {
    console.error("Authentication initialization failed:", err);

    document.body.textContent =
      "Unable to initialize authentication. Please refresh the page.";

    return;
  }

  // Verify the current authentication session.
  let authenticatedUser = null;

  try {
    authenticatedUser =
      await window.YourinAPI.getCurrentUser();

  } catch (err) {
    console.error("Session verification failed:", err);

    if (!PUBLIC_PAGES.includes(page)) {
      document.body.textContent =
        "Unable to verify your session. Please refresh the page.";

      return;
    }
  }

  // Protect application pages.
  if (!PUBLIC_PAGES.includes(page) && !authenticatedUser) {
    window.location.replace("sign-in.html");
    return;
  }

  // Redirect authenticated users away from authentication pages.
  if (PUBLIC_PAGES.includes(page) && authenticatedUser) {
    window.location.replace("dashboard.html");
    return;
  }

  const DATA = window.POC_DATA;

  if (!DATA) {
    console.error("Application data is unavailable.");
    document.body.textContent =
      "Unable to load application data. Please refresh the page.";
    return;
  }

  // Keep local application data isolated by authenticated user.
  const USER_ID = authenticatedUser?.id || "unauthenticated";
  const KEY = `yourin-poc-v2:${USER_ID}`;
  const PREFIX = `yourin-poc:${USER_ID}:`;

  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];

  const jobKeys = [
    "job-source",
    "job-title",
    "domain",
    "company",
    "position"
  ];

  const manualJobKeys = [
    "job-title",
    "domain",
    "company",
    "position"
  ];

  const strings = (value, length) =>
    Array.isArray(value) &&
    value.length === length &&
    value.every(item => typeof item === "string");

  const identity = name => String(name || "").trim().toLowerCase();
  const go = url => {
    window.location.href = url;
  };

  // Create a local application account.
  // Authentication credentials are never stored here.
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
        id: "sample-" + n,
        name: "Interview " + n,
        date: "29/2/2026",
        finished: n !== 2,
        sample: true,
        answers: n === 2 ? ["", "", ""] : [...DATA.answers],
        cv: [...DATA.cv],
        job: {}
      }))
    };
  }

  // Validate stored application data.
  function validState(value) {
    return (
      value &&
      value.version === 2 &&
      Number.isFinite(value.updatedAt) &&
      typeof value.currentAccount === "string" &&
      Array.isArray(value.accounts) &&
      value.accounts.length > 0 &&
      value.accounts.every(account =>
        account &&
        typeof account.username === "string" &&
        account.username.trim() &&
        strings(account.cv, 4) &&
        account.job &&
        typeof account.job === "object" &&
        Array.isArray(account.feedback) &&
        Array.isArray(account.interviews) &&
        account.interviews.every(interview =>
          interview &&
          typeof interview.id === "string" &&
          typeof interview.name === "string" &&
          typeof interview.date === "string" &&
          strings(interview.answers, 3) &&
          (interview.cv === null || strings(interview.cv, 4))
        )
      )
    );
  }

  const authenticatedUsername =
    authenticatedUser?.user_metadata?.username || "User";

  // Initialize the current user's local application state.
  let state = {
    version: 2,
    updatedAt: 0,
    currentAccount: authenticatedUsername,
    accounts: [newAccount(authenticatedUsername)]
  };

  const candidates = [];

  try {
    candidates.push(JSON.parse(localStorage.getItem(KEY)));
  } catch (_) {
    // Local storage may be unavailable.
  }

  try {
    if (window.name.startsWith(PREFIX)) {
      candidates.push(JSON.parse(window.name.slice(PREFIX.length)));
    }
  } catch (_) {
    // Ignore unrelated or invalid window names.
  }

  for (const candidate of candidates) {
    if (
      validState(candidate) &&
      candidate.updatedAt >= state.updatedAt
    ) {
      state = candidate;
    }
  }

  let account = state.accounts.find(
    item => identity(item.username) === identity(authenticatedUsername)
  );

  if (!account) {
    account = newAccount(authenticatedUsername);
    state.accounts.push(account);
  }

  account.username = authenticatedUsername;
  state.currentAccount = authenticatedUsername;

  if (!account.cvMode) {
    account.cvMode = "text";
  }

  // Save local application data.
  function save() {
    state.updatedAt = Date.now();

    const serialized = JSON.stringify(state);

    try {
      localStorage.setItem(KEY, serialized);
    } catch (_) {
      // Use the same-tab fallback below.
    }

    try {
      window.name = PREFIX + serialized;
    } catch (_) {
      // Static navigation remains available.
    }
  }

  function error(selector, message) {
    const element = $(selector);

    if (!element) return;

    element.textContent = message;
    element.hidden = false;
  }

  function activeInterview() {
    return account.interviews.find(
      item => item.id === account.activeId
    );
  }

  function reportInterview() {
    return (
      activeInterview() ||
      account.interviews.find(item => item.finished) ||
      account.interviews[0]
    );
  }

  function startInterview(customCV, customPdf, source) {
    const id = "interview-" + Date.now();

    let interviewCV = ["", "", "", ""];
    let interviewPdfItem = null;
    let mode = "text";

    if (customPdf) {
      interviewPdfItem = { ...customPdf };
      mode = "pdf";
    } else if (
      customCV &&
      customCV.some(text => text && text.trim())
    ) {
      interviewCV = [...customCV];
      mode = "text";
    } else if (source !== "none" && account.syncCV) {
      if (account.cvPdf || account.cvMode === "pdf") {
        interviewPdfItem = account.cvPdf
          ? { ...account.cvPdf }
          : null;

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

  function saveJob() {
    account.job = Object.fromEntries(
      jobKeys.map(key => {
        const element = $("#" + key);

        return [
          key,
          element
            ? element.value.trim()
            : (account.job?.[key] || "")
        ];
      })
    );

    const syncCvCheckbox = $("#sync-cv");

    account.syncCV = syncCvCheckbox
      ? syncCvCheckbox.checked
      : account.syncCV !== false;

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

  // Display the authenticated username.
  $$("[data-username]").forEach(element => {
    element.textContent = account.username;
  });

  // Highlight the active navigation item.
  const navMap = {
    dashboard: "dashboard",
    storage: "storage",
    "system-feedback": "feedback",
    profile: "profile"
  };

  const activeNav = navMap[page];

  if (activeNav) {
    const activeLink = $(`[data-nav="${activeNav}"]`);

    if (activeLink) {
      activeLink.classList.add("is-active");
    }
  }

  // Sign out through Supabase.
  $$("[data-sign-out]").forEach(link => {
    link.addEventListener("click", async event => {
      event.preventDefault();

      try {
        await window.YourinAPI.signOut();
        window.location.replace("sign-in.html");
      } catch (err) {
        console.error("Sign out failed:", err);
        alert(err.message || "Unable to sign out.");
      }
    });
  });

  // Toggle password visibility.
  $$("[data-toggle-password]").forEach(button => {
    button.addEventListener("click", () => {
      const targetId = button.dataset.togglePassword;
      const input = $("#" + targetId);

      if (!input) return;

      const isPassword = input.type === "password";

      input.type = isPassword ? "text" : "password";

      button.setAttribute(
        "aria-label",
        isPassword ? "Hide password" : "Show password"
      );

      button.setAttribute(
        "aria-pressed",
        isPassword ? "true" : "false"
      );

      button.setAttribute(
        "title",
        isPassword ? "Hide password" : "Show password"
      );

      const eyeShow = button.querySelector(".eye-show");
      const eyeHide = button.querySelector(".eye-hide");

      if (eyeShow && eyeHide) {
        eyeShow.classList.toggle("is-hidden", isPassword);
        eyeHide.classList.toggle("is-hidden", !isPassword);
      }
    });
  });

  // Authentication forms.
  const authForms = $$("#auth-form, #sign-in-form, #sign-up-form");

  authForms.forEach(authForm => {
    authForm.addEventListener("submit", async event => {
      event.preventDefault();

      const submitButton = authForm.querySelector('[type="submit"]');

      const username = $("#username")?.value.trim() || "";
      const password = $("#password")?.value || "";
      const confirmPassword = $("#confirm-password")?.value || "";

      const authError = $("#auth-error");

      if (authError) {
        authError.hidden = true;
        authError.textContent = "";
      }

      if (!username || !password) {
        error(
          "#auth-error",
          "Please enter your username and password."
        );
        return;
      }

      if (submitButton) {
        submitButton.disabled = true;
      }

      try {
        let result;

        if (page === "sign-up") {
          result = await window.YourinAPI.signUp(
            username,
            password,
            confirmPassword
          );

          if (result.requiresEmailConfirmation) {
            error(
              "#auth-error",
              "Your account was created, but email confirmation is required. Please check your Supabase Auth configuration."
            );
            return;
          }
        } else {
          result = await window.YourinAPI.signIn(
            username,
            password
          );
        }

        if (!result.user) {
          throw new Error(
            "Authentication succeeded, but no user was returned."
          );
        }

        window.location.replace("dashboard.html");
      } catch (err) {
        error(
          "#auth-error",
          err.message || "Authentication failed. Please try again."
        );
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
        }
      }
    });
  });

  // Reset the active interview when starting a new interview.
  $$("[data-new-interview]").forEach(link => {
    link.addEventListener("click", () => {
      account.activeId = null;
      account.job = {};
      save();
    });
  });

  // ============================================================
  // PROFILE PAGE: ACCOUNT CREDENTIAL MANAGEMENT
  // ============================================================

  if (page === "profile") {
    const usernameInput = $("#profile-username");
    const passwordInput = $("#account-password");
    const passwordUnlockBox = $("#password-unlock-box");
    const profileForm = $("#profile-form");
    const unlockBtn = $("#unlock-password-btn");
    const verifyPasswordInput = $("#verify-password");
    const profileStatus = $("#profile-status");

    let isPasswordUnlocked = false;

    if (
      usernameInput &&
      passwordInput &&
      passwordUnlockBox &&
      profileForm &&
      unlockBtn &&
      verifyPasswordInput
    ) {
      usernameInput.value =
        authenticatedUser.user_metadata?.username || "";

      usernameInput.readOnly = true;

      passwordInput.value = "";
      passwordInput.placeholder = "Enter a new password";
      passwordInput.readOnly = true;
      passwordInput.type = "password";

      // Verify the current password before enabling account editing.
      async function unlockProfile() {
        const currentPassword = verifyPasswordInput.value;

        const profileError = $("#profile-error");

        if (profileError) {
          profileError.hidden = true;
          profileError.textContent = "";
        }

        if (profileStatus) {
          profileStatus.textContent = "";
        }

        if (!currentPassword) {
          error("#profile-error", "Enter your current password.");
          verifyPasswordInput.focus();
          return;
        }

        unlockBtn.disabled = true;

        try {
          await window.YourinAPI.unlockEditing(currentPassword);

          isPasswordUnlocked = true;

          usernameInput.readOnly = false;
          passwordInput.readOnly = false;

          passwordUnlockBox.innerHTML = `
            <p class="unlock-hint">
              Editing unlocked. You can now update your username or password.
            </p>
          `;

          if (profileStatus) {
            profileStatus.textContent = "Account editing unlocked.";
          }
        } catch (err) {
          error(
            "#profile-error",
            err.message || "Password verification failed."
          );
        } finally {
          unlockBtn.disabled = false;
        }
      }

      unlockBtn.addEventListener("click", unlockProfile);

      // Save account changes through Supabase Auth.
      profileForm.addEventListener("submit", async event => {
        event.preventDefault();

        const profileError = $("#profile-error");

        if (profileError) {
          profileError.hidden = true;
          profileError.textContent = "";
        }

        if (profileStatus) {
          profileStatus.textContent = "";
        }

        if (!isPasswordUnlocked) {
          error(
            "#profile-error",
            "Verify your current password before saving changes."
          );
          return;
        }

        const newUsername = usernameInput.value.trim().toLowerCase();
        const newPassword = passwordInput.value;

        if (!/^[a-z0-9_]{3,60}$/.test(newUsername)) {
          error(
            "#profile-error",
            "Username must contain 3–60 characters and use only lowercase letters, numbers, or underscores."
          );
          return;
        }

        if (
          newPassword &&
          (newPassword.length < 8 || newPassword.length > 128)
        ) {
          error(
            "#profile-error",
            "A new password must contain 8–128 characters."
          );
          return;
        }

        const saveButton = $("#save-profile");

        if (saveButton) {
          saveButton.disabled = true;
        }

        try {
          // This method must be implemented in api.js.
          await window.YourinAPI.updateAccount({
            username: newUsername,
            password: newPassword || undefined
          });

          authenticatedUser =
            await window.YourinAPI.getCurrentUser();

          account.username = newUsername;
          state.currentAccount = newUsername;

          save();

          $$("[data-username]").forEach(element => {
            element.textContent = newUsername;
          });

          // Reset the password fields.
          passwordInput.value = "";
          passwordInput.readOnly = true;
          passwordInput.type = "password";
          passwordInput.placeholder = "Enter a new password";

          usernameInput.readOnly = true;

          isPasswordUnlocked = false;

          // Restore the verification controls.
          passwordUnlockBox.innerHTML = `
            <label for="verify-password" class="unlock-label">
              Verify your current password to edit account details
            </label>

            <div class="unlock-input-group">
              <input
                id="verify-password"
                type="password"
                placeholder="Enter current password"
                autocomplete="current-password"
              >

              <button
                class="btn btn-secondary"
                id="unlock-password-btn"
                type="button"
              >
                Unlock
              </button>
            </div>
          `;

          // Reconnect the newly created controls.
          const newVerifyInput = $("#verify-password");
          const newUnlockButton = $("#unlock-password-btn");

          if (newVerifyInput && newUnlockButton) {
            newUnlockButton.addEventListener(
              "click",
              async () => {
                const enteredPassword = newVerifyInput.value;

                if (!enteredPassword) {
                  error(
                    "#profile-error",
                    "Enter your current password."
                  );
                  return;
                }

                newUnlockButton.disabled = true;

                try {
                  await window.YourinAPI.unlockEditing(
                    enteredPassword
                  );

                  isPasswordUnlocked = true;

                  usernameInput.readOnly = false;
                  passwordInput.readOnly = false;

                  passwordUnlockBox.innerHTML = `
                    <p class="unlock-hint">
                      Editing unlocked. You can now update your username or password.
                    </p>
                  `;

                  if (profileStatus) {
                    profileStatus.textContent =
                      "Account editing unlocked.";
                  }
                } catch (err) {
                  error(
                    "#profile-error",
                    err.message || "Password verification failed."
                  );
                } finally {
                  newUnlockButton.disabled = false;
                }
              }
            );
          }

          if (profileStatus) {
            profileStatus.textContent =
              "Account information updated successfully.";
          }
        } catch (err) {
          error(
            "#profile-error",
            err.message || "Unable to update account information."
          );
        } finally {
          if (saveButton) {
            saveButton.disabled = false;
          }
        }
      });
    }

    // ==========================================================
    // CV SECTION MANAGEMENT
    // Preserve your existing CV management implementation here.
    // ==========================================================

    // The existing CV management code from your original
    // profile-page implementation should remain unchanged.
  }

  // ============================================================
  // JOB PROFILE PAGE
  // ============================================================

  if (page === "job-profile") {
    // Migrate legacy job-url to job-source if necessary.
    if (
      !account.job["job-source"] &&
      typeof account.job["job-url"] === "string" &&
      account.job["job-url"].trim()
    ) {
      account.job["job-source"] =
        account.job["job-url"].trim();
    }

    jobKeys.forEach(key => {
      const input = $("#" + key);

      if (!input) return;

      input.value =
        typeof account.job[key] === "string"
          ? account.job[key]
          : "";

      input.addEventListener("input", () => {
        const jobError = $("#job-error");

        if (jobError) {
          jobError.hidden = true;
        }

        saveJob();
      });
    });

    // Job profile mode switching.
    const jobPasteMode = $("#job-paste-mode");
    const jobManualMode = $("#job-manual-mode");
    const jobModeSwitchBtn = $("#job-mode-switch-btn");
    const jobModeHint = $("#job-mode-hint");

    let jobInputMode = "paste";

    function setJobMode(mode) {
      jobInputMode = mode;

      const jobError = $("#job-error");

      if (jobError) {
        jobError.hidden = true;
      }

      if (mode === "manual") {
        jobPasteMode?.classList.add("is-hidden");
        jobManualMode?.classList.remove("is-hidden");

        if (jobModeHint) {
          jobModeHint.textContent =
            "Have a job description, HTML, or link?";
        }

        if (jobModeSwitchBtn) {
          jobModeSwitchBtn.textContent =
            "Paste job description instead";
        }
      } else {
        jobManualMode?.classList.add("is-hidden");
        jobPasteMode?.classList.remove("is-hidden");

        if (jobModeHint) {
          jobModeHint.textContent =
            "Don't have a job description or link?";
        }

        if (jobModeSwitchBtn) {
          jobModeSwitchBtn.textContent =
            "Enter 4 fields manually";
        }
      }
    }

    if (jobModeSwitchBtn) {
      jobModeSwitchBtn.addEventListener("click", () => {
        setJobMode(
          jobInputMode === "paste" ? "manual" : "paste"
        );
      });
    }

    setJobMode("paste");

    // CV section toggle.
    const cvSectionToggle = $("#cv-section-toggle");
    const cvSectionBody = $("#cv-section-body");

    let isCvOpen = false;

    function setCvSectionOpen(open) {
      isCvOpen = open;

      if (!cvSectionBody || !cvSectionToggle) return;

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

    // CV mode switching.
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

      if (jobError) {
        jobError.hidden = true;
      }

      if (mode === "custom") {
        cvSavedMode?.classList.add("is-hidden");
        cvCustomMode?.classList.remove("is-hidden");
      } else {
        cvCustomMode?.classList.add("is-hidden");
        cvSavedMode?.classList.remove("is-hidden");
      }
    }

    if (switchToCustomCvBtn) {
      switchToCustomCvBtn.addEventListener(
        "click",
        () => setCvMode("custom")
      );
    }

    if (switchToSavedCvBtn) {
      switchToSavedCvBtn.addEventListener(
        "click",
        () => setCvMode("saved")
      );
    }

    // Custom PDF upload handling.
    let interviewPdf = null;

    const interviewPdfDropzone = $("#interview-pdf-dropzone");
    const interviewPdfInput = $("#interview-pdf-input");
    const interviewPdfCard = $("#interview-pdf-card");
    const interviewPdfName = $("#interview-pdf-name");
    const interviewPdfSize = $("#interview-pdf-size");
    const interviewPdfStatus = $("#interview-pdf-status");

    function clearCustomInterviewPdf() {
      if (!interviewPdf) return;

      interviewPdf = null;

      if (interviewPdfInput) {
        interviewPdfInput.value = "";
      }

      interviewPdfCard?.classList.add("is-hidden");
      interviewPdfDropzone?.classList.remove("is-hidden");

      if (interviewPdfStatus) {
        interviewPdfStatus.textContent = "";
      }
    }

    if (jobCvRawInput) {
      jobCvRawInput.addEventListener(
        "input",
        clearCustomInterviewPdf
      );
    }

    function handleInterviewPdf(file) {
      if (!file) return;

      if (
        !file.name.toLowerCase().endsWith(".pdf") &&
        file.type !== "application/pdf"
      ) {
        if (interviewPdfStatus) {
          interviewPdfStatus.textContent =
            "Please upload a valid PDF file (.pdf).";
        }

        return;
      }

      if (jobCvRawInput) {
        jobCvRawInput.value = "";
      }

      const sizeStr =
        file.size > 1024 * 1024
          ? (file.size / (1024 * 1024)).toFixed(1) + " MB"
          : Math.round(file.size / 1024) + " KB";

      interviewPdf = {
        name: file.name,
        size: sizeStr
      };

      interviewPdfDropzone?.classList.add("is-hidden");
      interviewPdfCard?.classList.remove("is-hidden");

      if (interviewPdfName) {
        interviewPdfName.textContent = file.name;
      }

      if (interviewPdfSize) {
        interviewPdfSize.textContent = sizeStr;
      }

      if (interviewPdfStatus) {
        interviewPdfStatus.textContent =
          `Attached "${file.name}" to this interview.`;
      }
    }

    if (interviewPdfDropzone) {
      interviewPdfDropzone.addEventListener("click", () => {
        interviewPdfInput?.click();
      });

      interviewPdfDropzone.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          interviewPdfInput?.click();
        }
      });

      ["dragenter", "dragover"].forEach(eventName => {
        interviewPdfDropzone.addEventListener(eventName, event => {
          event.preventDefault();
          event.stopPropagation();
          interviewPdfDropzone.classList.add("drag-over");
        });
      });

      ["dragleave", "drop"].forEach(eventName => {
        interviewPdfDropzone.addEventListener(eventName, event => {
          event.preventDefault();
          event.stopPropagation();
          interviewPdfDropzone.classList.remove("drag-over");
        });
      });

      interviewPdfDropzone.addEventListener("drop", event => {
        const file = event.dataTransfer?.files?.[0];

        if (file) {
          handleInterviewPdf(file);
        }
      });
    }

    const interviewBrowseBtn = $("#interview-browse-pdf-btn");

    if (interviewBrowseBtn) {
      interviewBrowseBtn.addEventListener("click", event => {
        event.stopPropagation();
        interviewPdfInput?.click();
      });
    }

    if (interviewPdfInput) {
      interviewPdfInput.addEventListener("change", () => {
        const file = interviewPdfInput.files?.[0];

        if (file) {
          handleInterviewPdf(file);
        }
      });
    }

    const interviewReplaceBtn = $("#interview-replace-pdf-btn");

    if (interviewReplaceBtn) {
      interviewReplaceBtn.addEventListener("click", () => {
        interviewPdfInput?.click();
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

    // Submit job profile.
    const jobForm = $("#job-form");

    if (jobForm) {
      jobForm.addEventListener("submit", event => {
        event.preventDefault();

        const jobError = $("#job-error");

        if (jobError) {
          jobError.hidden = true;
        }

        saveJob();

        if (jobInputMode === "paste") {
          if (!account.job["job-source"]) {
            return error(
              "#job-error",
              "Paste a job description, HTML, or job link, or click 'Enter 4 fields manually'."
            );
          }
        } else {
          if (manualJobKeys.some(key => !account.job[key])) {
            return error(
              "#job-error",
              "Enter a value for each of the 4 job profile fields."
            );
          }
        }

        if (!isCvOpen) {
          startInterview(null, null, "none");
        } else if (cvInputMode === "custom") {
          if (interviewPdf) {
            startInterview(
              ["", "", "", ""],
              interviewPdf,
              "custom"
            );
          } else {
            const rawText = jobCvRawInput
              ? jobCvRawInput.value.trim()
              : "";

            if (!rawText) {
              return error(
                "#job-error",
                "Paste your CV text or upload a PDF resume, or switch back to saved CV."
              );
            }

            startInterview(
              [rawText, "", "", ""],
              null,
              "custom"
            );
          }
        } else if (
          syncCvCheckbox &&
          syncCvCheckbox.checked
        ) {
          if (account.cvPdf || account.cvMode === "pdf") {
            startInterview(
              ["", "", "", ""],
              account.cvPdf,
              "saved"
            );
          } else {
            startInterview(
              [...account.cv],
              null,
              "saved"
            );
          }
        } else {
          startInterview(null, null, "none");
        }

        go("interview.html");
      });
    }

    $$("[data-save-job]").forEach(link => {
      link.addEventListener("click", saveJob);
    });
  }

  // ============================================================
  // INTERVIEW PAGES
  // ============================================================

  if (
    page === "interview" ||
    page === "interview-1" ||
    page === "interview-2" ||
    page === "interview-3" ||
    $("#interview-step-track")
  ) {
    const interview = activeInterview() || startInterview();

    const questions = DATA.questions || [
      "Imagine you're tasked with curating a time capsule that defines the year 2026 for an alien civilization. What are three objects you put inside?",
      "To be, or not to be, that is the question: whether 'tis nobler in the mind to suffer the slings and arrows of outrageous fortune, or to take arms against a sea of troubles, and by opposing end them.",
      "Wat een wartaa. Het is echt niet alsof ik bezorgd om je was ofzo. Mijn colonne verplaatste zich puur toevallig langs deze strategische route, dus haal je maar niks in je hoofd, begrepen?"
    ];

    const totalQuestions = questions.length;

    let currentStep = 0;

    try {
      const params = new URLSearchParams(window.location.search);
      const qParam = parseInt(params.get("q"), 10);

      if (
        !isNaN(qParam) &&
        qParam >= 1 &&
        qParam <= totalQuestions
      ) {
        currentStep = qParam - 1;
      }
    } catch (_) {
      // Ignore invalid query parameters.
    }

    while (interview.answers.length < totalQuestions) {
      interview.answers.push("");
    }

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
      robotStage.classList.remove(
        "is-watching",
        "is-typing"
      );
    }

    function updateGazeOnTyping() {
      if (!robotStage || !answerInput) return;

      if (robotStage.classList.contains("is-miming")) {
        return;
      }

      robotStage.classList.remove("is-idle");
      robotStage.classList.add("is-watching", "is-typing");

      const text = answerInput.value;
      const cursorPos =
        answerInput.selectionStart ?? text.length;

      const totalLen = Math.max(1, text.length);
      const ratio = Math.max(
        0,
        Math.min(1, cursorPos / totalLen)
      );

      const eyeX = (ratio - 0.5) * 6.4;

      setRobotGaze(eyeX.toFixed(1), 3.5);

      if (typingGazeTimer) {
        clearTimeout(typingGazeTimer);
      }

      typingGazeTimer = setTimeout(() => {
        if (
          !robotStage.classList.contains("is-miming") &&
          !isRecording
        ) {
          robotStage.classList.remove("is-typing");
          setRobotGaze(0, 2);
        }
      }, 1600);
    }

    function startRobotMime(customDuration) {
      if (!robotStage) return;

      if (mimeTimer) {
        clearTimeout(mimeTimer);
      }

      if (typingGazeTimer) {
        clearTimeout(typingGazeTimer);
      }

      resetRobotGaze();

      robotStage.classList.remove(
        "is-idle",
        "is-listening",
        "is-watching",
        "is-typing"
      );

      robotStage.classList.add("is-miming");

      const qText = questions[currentStep] || "";

      const duration =
        customDuration ||
        Math.max(3000, Math.min(5500, qText.length * 40));

      mimeTimer = setTimeout(() => {
        stopRobotMime();
      }, duration);
    }

    function stopRobotMime() {
      if (mimeTimer) {
        clearTimeout(mimeTimer);
      }

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

      charCountEl.textContent =
        `${count} character${count === 1 ? "" : "s"}`;
    }

    function renderStep(index) {
      currentStep = Math.max(
        0,
        Math.min(index, totalQuestions - 1)
      );

      if (questionTitle) {
        questionTitle.textContent =
          `Question ${currentStep + 1}`;
      }

      if (questionBadge) {
        questionBadge.textContent =
          `${currentStep + 1} of ${totalQuestions}`;
      }

      if (questionText) {
        questionText.textContent = questions[currentStep];
      }

      if (answerInput) {
        answerInput.dataset.answer = currentStep;
        answerInput.value =
          interview.answers[currentStep] || "";

        updateCharCount();
      }

      if (prevBtn) {
        prevBtn.classList.toggle(
          "is-hidden",
          currentStep === 0
        );
      }

      if (nextBtn) {
        nextBtn.textContent =
          currentStep === totalQuestions - 1
            ? "Finalize Interview"
            : "Next Question →";
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
        if (
          robotStage &&
          !robotStage.classList.contains("is-miming") &&
          !isRecording
        ) {
          robotStage.classList.add("is-watching");
          setRobotGaze(0, 3);
        }
      });

      answerInput.addEventListener("blur", () => {
        if (!isRecording) {
          resetRobotGaze();

          if (
            robotStage &&
            !robotStage.classList.contains("is-miming")
          ) {
            robotStage.classList.add("is-idle");
          }
        }
      });

      answerInput.addEventListener(
        "keyup",
        updateGazeOnTyping
      );

      answerInput.addEventListener(
        "click",
        updateGazeOnTyping
      );
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        if (currentStep > 0) {
          if (answerInput) {
            interview.answers[currentStep] = answerInput.value;
          }

          save();
          renderStep(currentStep - 1);
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        if (answerInput) {
          interview.answers[currentStep] = answerInput.value;
        }

        save();

        if (currentStep < totalQuestions - 1) {
          renderStep(currentStep + 1);
        } else {
          interview.finished = true;
          save();
          go("done-interview.html");
        }
      });
    }

    // Save and exit handling.
    function triggerSaveAndExit(targetHref) {
      if (answerInput) {
        interview.answers[currentStep] = answerInput.value;
      }

      save();

      if (exitModal) {
        if (exitModalName) {
          exitModalName.textContent = interview.name;
        }

        if (exitModalConfirmBtn) {
          const destination =
            targetHref || "dashboard.html";

          exitModalConfirmBtn.href = destination;
          exitModalConfirmBtn.textContent = "Proceed";
        }

        exitModal.classList.remove("is-hidden");

        const header = $(".site-header");
        const mainPanel = $(".interview-panel");
        const footer = $(".site-footer");

        if (header) header.inert = true;
        if (mainPanel) mainPanel.inert = true;
        if (footer) footer.inert = true;

        exitModalConfirmBtn?.focus();
      } else {
        go("interview-interrupt.html");
      }
    }

    $$(".site-header a").forEach(link => {
      link.addEventListener("click", event => {
        event.preventDefault();

        triggerSaveAndExit(
          link.getAttribute("href") || "dashboard.html"
        );
      });
    });

    try {
      history.pushState({ interview: true }, "");

      window.addEventListener("popstate", () => {
        triggerSaveAndExit("dashboard.html");
      });
    } catch (_) {
      // Ignore unavailable history APIs.
    }

    // Demo microphone interaction.
    function startRecording() {
      isRecording = true;

      if (robotStage) {
        if (mimeTimer) clearTimeout(mimeTimer);
        if (typingGazeTimer) clearTimeout(typingGazeTimer);

        robotStage.classList.remove(
          "is-miming",
          "is-idle",
          "is-watching",
          "is-typing"
        );

        robotStage.classList.add("is-listening");

        setRobotGaze(0, 3.5);
      }

      micToggleBtn?.classList.add("is-recording");

      if (micLabel) {
        micLabel.textContent =
          "Recording... (Click to stop)";
      }

      if (micSub) {
        micSub.textContent = "Listening to your voice...";
      }

      voiceWaveform?.classList.add("is-active");

      recordingTimer = setTimeout(() => {
        if (isRecording && answerInput) {
          const sampleSpoken = [
            "In my perspective, this role requires strong adaptability and rapid problem-solving.",
            "Furthermore, I prioritize clear communication and delivering reliable results under pressure.",
            "My previous background gives me a distinct advantage in tackling complex technical challenges."
          ];

          const addition =
            sampleSpoken[currentStep] ||
            "I believe this approach creates the strongest foundation for success.";

          answerInput.value =
            (answerInput.value.trim()
              ? answerInput.value.trim() + " "
              : "") + addition;

          interview.answers[currentStep] = answerInput.value;

          save();
          updateCharCount();
        }
      }, 2400);
    }

    function stopRecording() {
      isRecording = false;

      if (recordingTimer) {
        clearTimeout(recordingTimer);
      }

      if (robotStage) {
        robotStage.classList.remove("is-listening");
        resetRobotGaze();
        robotStage.classList.add("is-idle");
      }

      micToggleBtn?.classList.remove("is-recording");

      if (micLabel) {
        micLabel.textContent =
          "Record Answer with Microphone";
      }

      if (micSub) {
        micSub.textContent =
          "Click to start speech-to-text";
      }

      voiceWaveform?.classList.remove("is-active");
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

    $$("[data-save-answer]").forEach(link => {
      link.addEventListener("click", () => {
        if (answerInput) {
          interview.answers[currentStep] = answerInput.value;
        }

        save();
      });
    });

    renderStep(currentStep);
  }

  // ============================================================
  // INTERVIEW INTERRUPT PAGE
  // ============================================================

  if (page === "interview-interrupt") {
    const interview = activeInterview();

    if (interview && $("#saved-name")) {
      $("#saved-name").textContent = interview.name;
    }

    const header = $(".site-header");
    const footer = $(".site-footer");
    const home = $(".saved-dialog a");
    const dialog = $(".saved-dialog");

    if (header) header.inert = true;
    if (footer) footer.inert = true;

    home?.focus();

    dialog?.addEventListener("keydown", event => {
      if (event.key === "Tab" && home) {
        event.preventDefault();
        home.focus();
      }
    });
  }

  // ============================================================
  // COMPLETED INTERVIEW PAGE
  // ============================================================

  if (page === "done-interview") {
    const doneForm = $("#done-form");

    if (doneForm) {
      doneForm.addEventListener("submit", event => {
        event.preventDefault();

        const interview =
          activeInterview() || startInterview();

        const name = $("#interview-name")?.value.trim();

        if (name) {
          interview.name = name;
        }

        interview.finished = true;

        save();
        go("report.html");
      });
    }
  }

  // ============================================================
  // STORAGE PAGE
  // ============================================================

  if (page === "storage") {
    const listContainer = $("#interview-list");
    const emptyContainer = $("#storage-empty");
    const gridHead = $(".storage-grid-head");

    function renderInterviews() {
      if (!listContainer) return;

      listContainer.replaceChildren();

      const total = account.interviews
        ? account.interviews.length
        : 0;

      if (total === 0) {
        gridHead?.classList.add("is-hidden");
        emptyContainer?.classList.remove("is-hidden");
        return;
      }

      gridHead?.classList.remove("is-hidden");
      emptyContainer?.classList.add("is-hidden");

      account.interviews.forEach((interview, index) => {
        const row = document.createElement("div");
        row.className = "storage-row-card";

        // Interview name.
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
        editBtn.setAttribute(
          "aria-label",
          `Edit name for ${interview.name}`
        );

        editBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round"
            aria-hidden="true">
            <path d="M12 20h9"></path>
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
          </svg>
        `;

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
          saveBtn.setAttribute(
            "aria-label",
            "Save interview name"
          );

          saveBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" stroke-width="2.5"
              stroke-linecap="round" stroke-linejoin="round"
              aria-hidden="true">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          `;

          const cancelBtn = document.createElement("button");
          cancelBtn.type = "button";
          cancelBtn.className = "btn-rename-cancel";
          cancelBtn.title = "Cancel";
          cancelBtn.setAttribute(
            "aria-label",
            "Cancel editing name"
          );

          cancelBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" stroke-width="2.2"
              stroke-linecap="round" stroke-linejoin="round"
              aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          `;

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

          saveBtn.addEventListener(
            "mousedown",
            event => event.preventDefault()
          );

          saveBtn.addEventListener("click", commitRename);

          cancelBtn.addEventListener(
            "mousedown",
            event => event.preventDefault()
          );

          cancelBtn.addEventListener("click", cancelRename);

          input.addEventListener("keydown", event => {
            if (event.key === "Enter") {
              event.preventDefault();
              commitRename();
            } else if (event.key === "Escape") {
              event.preventDefault();
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

        // Interview date.
        const colDate = document.createElement("div");
        colDate.className = "col-date-text";
        colDate.textContent = interview.date;

        // Interview status.
        const colStatus = document.createElement("div");
        colStatus.className = "col-status-wrap";

        const status = document.createElement("span");
        status.className =
          "status" + (interview.finished ? "" : " unfinished");

        status.textContent = interview.finished
          ? "Finished"
          : "Unfinished";

        colStatus.append(status);

        // Interview actions.
        const colActions = document.createElement("div");
        colActions.className = "col-actions-group";

        const actionLink = document.createElement("a");
        actionLink.className =
          "btn btn-secondary btn-session-action";

        actionLink.href = interview.finished
          ? "report.html"
          : "interview.html";

        actionLink.textContent = interview.finished
          ? "View report"
          : "Continue";

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

          if (account.activeId === interview.id) {
            account.activeId = null;
          }

          save();
          renderInterviews();
        });

        colActions.append(actionLink, deleteBtn);

        row.append(
          colName,
          colDate,
          colStatus,
          colActions
        );

        listContainer.append(row);
      });
    }

    renderInterviews();
  }

  // ============================================================
  // REPORT PAGE
  // ============================================================

  if (page === "report") {
    const interview = reportInterview();

    if (interview) {
      if ($("#report-name")) {
        $("#report-name").textContent = interview.name;
      }

      if ($("#report-date") && interview.date) {
        $("#report-date").textContent = interview.date;
      }

      $$("[data-report-answer]").forEach((element, index) => {
        element.textContent =
          interview.answers[index] || "No answer provided.";
      });

      const retakeBtn = $("#retake-interview-btn");

      if (retakeBtn) {
        retakeBtn.addEventListener("click", event => {
          event.preventDefault();

          const newInterview = startInterview(
            interview.cv,
            interview.cvPdf,
            interview.cvMode === "pdf"
              ? "saved"
              : (
                interview.cv &&
                  interview.cv.some(
                    text => text && text.trim()
                  )
                  ? "custom"
                  : "none"
              )
          );

          if (interview.job) {
            newInterview.job = { ...interview.job };
          }

          save();
          go("interview.html");
        });
      }
    }
  }

  // ============================================================
  // SYSTEM FEEDBACK PAGE
  // ============================================================

  if (page === "system-feedback") {
    const inputs = [0, 1, 2, 3].map(
      index => $("#feedback-" + index)
    );

    inputs.forEach((input, index) => {
      if (!input) return;

      input.value =
        typeof account.feedback[index] === "string"
          ? account.feedback[index]
          : "";

      input.addEventListener("input", () => {
        account.feedback = inputs.map(
          item => item?.value || ""
        );

        save();
      });
    });

    const feedbackForm = $("#feedback-form");

    if (feedbackForm) {
      feedbackForm.addEventListener("submit", event => {
        event.preventDefault();

        account.feedback = inputs.map(
          input => input?.value || ""
        );

        save();
        go("thank-you.html");
      });
    }
  }

  // ============================================================
  // DASHBOARD PAGE
  // ============================================================

  if (page === "dashboard") {
    const cards = $$(".reveal-on-scroll");

    if (cards.length > 0) {
      document.body.classList.add("js-scroll-ready");

      if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(
          (entries, obs) => {
            entries.forEach(entry => {
              if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                obs.unobserve(entry.target);
              }
            });
          },
          {
            threshold: 0.12,
            rootMargin: "0px 0px -40px 0px"
          }
        );

        cards.forEach(card => observer.observe(card));
      } else {
        const checkScroll = () => {
          const triggerBottom = window.innerHeight * 0.92;

          cards.forEach(card => {
            if (
              card.getBoundingClientRect().top < triggerBottom
            ) {
              card.classList.add("is-visible");
            }
          });
        };

        window.addEventListener(
          "scroll",
          checkScroll,
          { passive: true }
        );

        checkScroll();
      }
    }
  }

  // Preserve local application data during navigation.
  window.addEventListener("pagehide", save);

})();
