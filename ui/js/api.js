/* API client and Supabase authentication for Render (`src/assistant/web.py`) + Vercel */
(() => {
  "use strict";

  // Live Render Web Service. Set window.YOURIN_API_URL before this file loads to override.
  const DEFAULT_API_URL = "https://assistant-team06.onrender.com";
  const OVERRIDE_API_URL = (window.YOURIN_API_URL || "").trim();
  const USERNAME_REGEX = /^[a-z0-9_]{3,60}$/;

  let config = null;
  let supabaseClient = null;
  let resolveReady;
  let rejectReady;

  const ready = new Promise((resolve, reject) => {
    resolveReady = resolve;
    rejectReady = reject;
  });
  // Consumers await this promise; keep an empty catch so an unused rejection is not noisy.
  ready.catch(() => {});
  window.YourinAPIReady = ready;

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

  function showLoading(input) {
    const loading = window.YourinUI?.loading;
    if (!loading || typeof loading.show !== "function") return null;

    const source = typeof input === "string"
      ? { title: input }
      : (input && typeof input === "object" ? input : {});
    const options = {
      title: source.title || "Working...",
      detail: source.detail || "",
      steps: Array.isArray(source.steps) ? source.steps : null,
      onCancel: typeof source.onCancel === "function" ? source.onCancel : null
    };

    ["eyebrow", "stepInterval", "coldStartAfter", "coldStartText", "cancelLabel"].forEach(key => {
      if (source[key] !== undefined) options[key] = source[key];
    });

    try {
      return loading.show(options);
    } catch (_) {
      return null;
    }
  }

  async function getAccessToken() {
    if (!supabaseClient) return null;
    try {
      const { data } = await supabaseClient.auth.getSession();
      return data?.session?.access_token || null;
    } catch (_) {
      return null;
    }
  }

  async function request(path, options = {}) {
    const base = resolveBaseUrl();
    if (!base) {
      return { status: 0, ok: false, data: null, networkError: true, fallback: true };
    }

    const {
      auth = true,
      notify: shouldNotify = true,
      loading: loadingOption = false,
      headers: optionHeaders,
      ...fetchOptions
    } = options;

    const loading = loadingOption ? showLoading(loadingOption) : null;
    const headers = { "Content-Type": "application/json", ...(optionHeaders || {}) };
    if (auth) {
      const token = await getAccessToken();
      if (token) headers.Authorization = `Bearer ${token}`;
    }

    try {
      const response = await fetch(`${base}${path}`, { ...fetchOptions, headers });
      let data = null;
      try { data = await response.json(); } catch (_) { data = null; }
      if (!response.ok && shouldNotify) {
        notify(response.status, data);
      }
      return { status: response.status, ok: response.ok, data };
    } catch (err) {
      if (err?.name === "AbortError") {
        return { status: 0, ok: false, data: null, aborted: true };
      }
      if (shouldNotify) notify(0, null);
      return { status: 0, ok: false, data: null, networkError: true, fallback: true };
    } finally {
      if (loading) loading.hide();
    }
  }

  // Backward-compatible helper: returns parsed JSON on success, null otherwise.
  async function requestJson(path, options = {}) {
    const result = await request(path, options);
    if (result.ok) return result.data;
    return null;
  }

  // Convenience wrapper for long-running operations (AI generation, finalize).
  function requestWithLoading(path, options = {}) {
    const hasLoading = Object.prototype.hasOwnProperty.call(options, "loading");
    return request(path, { ...options, loading: hasLoading ? options.loading : true });
  }

  async function requireClient() {
    await ready;
    if (!supabaseClient) {
      throw new Error("Supabase authentication is not configured.");
    }
    return supabaseClient;
  }

  function normalizeUsername(username) {
    return String(username || "").trim().toLowerCase();
  }

  function usernameToEmail(username) {
    return `${normalizeUsername(username)}@yourin.app`;
  }

  function validateUsername(username) {
    const normalized = normalizeUsername(username);
    if (!USERNAME_REGEX.test(normalized)) {
      throw new Error("Username must contain 3-60 characters: lowercase letters, numbers, or underscores.");
    }
    return normalized;
  }

  function validatePassword(password) {
    if (typeof password !== "string" || password.length < 8) {
      throw new Error("Password must contain at least 8 characters.");
    }
    if (password.length > 128) {
      throw new Error("Password must not exceed 128 characters.");
    }
  }

  function authError(error) {
    throw new Error(error?.message || "Authentication failed.");
  }

  async function signUp(username, password, confirmPassword) {
    const client = await requireClient();
    const normalizedUsername = validateUsername(username);
    validatePassword(password);
    if (password !== confirmPassword) {
      throw new Error("Passwords do not match.");
    }

    const { data, error } = await client.auth.signUp({
      email: usernameToEmail(normalizedUsername),
      password,
      options: { data: { username: normalizedUsername } }
    });
    if (error) authError(error);

    return {
      success: true,
      user: data.user,
      session: data.session,
      requiresEmailConfirmation: !data.session
    };
  }

  async function signIn(username, password) {
    const client = await requireClient();
    const normalizedUsername = validateUsername(username);
    if (!password) throw new Error("Password is required.");

    const { data, error } = await client.auth.signInWithPassword({
      email: usernameToEmail(normalizedUsername),
      password
    });
    if (error) authError(error);

    return { success: true, user: data.user, session: data.session };
  }

  async function signOut() {
    const client = await requireClient();
    const { error } = await client.auth.signOut();
    if (error) authError(error);
    return { success: true };
  }

  async function getSession() {
    const client = await requireClient();
    const { data, error } = await client.auth.getSession();
    if (error) authError(error);
    return data.session || null;
  }

  async function getCurrentUser() {
    const client = await requireClient();
    const { data, error } = await client.auth.getUser();
    if (error) {
      if (error.name === "AuthSessionMissingError") return null;
      authError(error);
    }
    return data.user || null;
  }

  async function isAuthenticated() {
    return Boolean(await getCurrentUser());
  }

  // Re-authenticate before allowing username/password changes.
  async function unlockEditing(password) {
    const client = await requireClient();
    if (!password) throw new Error("Password is required.");

    const currentUser = await getCurrentUser();
    if (!currentUser) throw new Error("You must be signed in to unlock editing.");

    const username = currentUser.user_metadata?.username;
    if (!username) throw new Error("Unable to retrieve the current username.");

    const { data, error } = await client.auth.signInWithPassword({
      email: usernameToEmail(username),
      password
    });
    if (error) authError(error);
    if (data.user?.id !== currentUser.id) {
      throw new Error("Authentication failed. The account does not match.");
    }

    return { success: true, user: data.user };
  }

  async function updateAccount({ username, password } = {}) {
    const client = await requireClient();
    const currentUser = await getCurrentUser();
    if (!currentUser) throw new Error("You must be signed in to update your account.");

    const updates = {};

    if (username !== undefined) {
      const normalizedUsername = validateUsername(username);
      const currentUsername = normalizeUsername(currentUser.user_metadata?.username);
      if (normalizedUsername !== currentUsername) {
        updates.email = usernameToEmail(normalizedUsername);
        updates.data = {
          ...(currentUser.user_metadata || {}),
          username: normalizedUsername
        };
      }
    }

    if (password) {
      validatePassword(password);
      updates.password = password;
    }

    if (Object.keys(updates).length === 0) {
      throw new Error("No account changes were provided.");
    }

    const { data, error } = await client.auth.updateUser(updates);
    if (error) authError(error);
    return { success: true, user: data.user };
  }

  function onAuthStateChange(callback) {
    if (!supabaseClient) {
      throw new Error("Supabase authentication is not configured.");
    }
    const { data } = supabaseClient.auth.onAuthStateChange((event, session) => {
      callback({ event, session, user: session?.user || null });
    });
    return data.subscription;
  }

  async function init() {
    if (!window.supabase || typeof window.supabase.createClient !== "function") {
      throw new Error("The Supabase client library could not be loaded.");
    }

    const result = await request("/api/config", { auth: false, notify: false });
    if (!result.ok || !result.data) {
      throw new Error("Unable to load application configuration from the backend.");
    }

    const cfg = result.data;
    if (cfg.supabaseConfigured === false || !cfg.supabaseUrl || !cfg.supabasePublishableKey) {
      throw new Error("Supabase authentication is not configured on the backend.");
    }

    config = Object.freeze({
      supabaseUrl: cfg.supabaseUrl,
      supabasePublishableKey: cfg.supabasePublishableKey,
      jwksConfigured: Boolean(cfg.jwksConfigured),
      llmConfigured: Boolean(cfg.llmConfigured)
    });

    supabaseClient = window.supabase.createClient(
      config.supabaseUrl,
      config.supabasePublishableKey,
      {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true
        }
      }
    );

    return config;
  }

  window.YourinAPI = {
    getBaseUrl: resolveBaseUrl,
    request,
    requestJson,
    requestWithLoading,
    getConfig: () => request("/api/config", { auth: false }),
    getAuthConfig: () => config,
    getAccessToken,
    signUp,
    signIn,
    signOut,
    getSession,
    getCurrentUser,
    isAuthenticated,
    unlockEditing,
    updateAccount,
    onAuthStateChange,
    getHealth: () => request("/api/health"),
    askAssistant: question =>
      request("/api/answer", {
        method: "POST",
        body: JSON.stringify({ question })
      }),
    getCV: (options = {}) =>
      request("/api/cv", { loading: false, ...(options || {}) }),
    saveCV: (payload, options = {}) =>
      request("/api/cv", {
        method: "PUT",
        body: JSON.stringify(payload || {}),
        loading: false,
        ...(options || {})
      }),
    submitFeedback: (payload, options = {}) =>
      request("/api/feedback", {
        method: "POST",
        body: JSON.stringify(payload || {}),
        loading: false,
        ...(options || {})
      })
  };

  init().then(resolveReady, rejectReady);
})();
