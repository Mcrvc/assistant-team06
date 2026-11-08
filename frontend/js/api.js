/* =========================================
   YOURIN - SUPABASE AUTHENTICATION API
   Authentication and account editing.
   User database integration will be added later.
   ========================================= */

window.YourinAPIReady = (async () => {
    "use strict";

    // =========================================
    // 1. SUPABASE CONFIGURATION
    // =========================================

    if (!window.YourinConfigPromise) {
        throw new Error(
            "Supabase configuration promise is unavailable."
        );
    }

    const config = await window.YourinConfigPromise;

    if (!config?.supabaseUrl || !config?.supabasePublishableKey) {
        throw new Error("Supabase configuration is missing.");
    }

    if (!window.supabase) {
        throw new Error("Supabase JavaScript library is unavailable.");
    }

    const supabaseClient = window.supabase.createClient(
        config.supabaseUrl,
        config.supabasePublishableKey
    );

    // =========================================
    // 2. VALIDATION AND HELPERS
    // =========================================

    const USERNAME_REGEX = /^[a-z0-9_]{3,60}$/;

    function normalizeUsername(username) {
        return String(username || "")
            .trim()
            .toLowerCase();
    }

    function usernameToEmail(username) {
        return `${normalizeUsername(username)}@yourin.app`;
    }

    function validateUsername(username) {
        const normalized = normalizeUsername(username);

        if (!USERNAME_REGEX.test(normalized)) {
            throw new Error(
                "Username must contain 3–60 characters and use only lowercase letters, numbers, or underscores."
            );
        }

        return normalized;
    }

    function validatePassword(password) {
        if (typeof password !== "string" || password.length < 8) {
            throw new Error(
                "Password must contain at least 8 characters."
            );
        }

        if (password.length > 128) {
            throw new Error(
                "Password must not exceed 128 characters."
            );
        }
    }

    function handleError(error) {
        if (!error) {
            throw new Error(
                "An unexpected authentication error occurred."
            );
        }

        throw new Error(
            error.message || "Authentication failed."
        );
    }

    // =========================================
    // 3. SIGN UP
    // =========================================

    async function signUp(username, password, confirmPassword) {
        try {
            const normalizedUsername = validateUsername(username);

            validatePassword(password);

            if (password !== confirmPassword) {
                throw new Error("Passwords do not match.");
            }

            const email = usernameToEmail(normalizedUsername);

            const { data, error } = await supabaseClient.auth.signUp({
                email,
                password,
                options: {
                    data: {
                        username: normalizedUsername
                    }
                }
            });

            if (error) {
                handleError(error);
            }

            return {
                success: true,
                user: data.user,
                session: data.session,
                requiresEmailConfirmation: !data.session
            };

        } catch (error) {
            throw new Error(error.message);
        }
    }

    // =========================================
    // 4. SIGN IN
    // =========================================

    async function signIn(username, password) {
        try {
            const normalizedUsername = validateUsername(username);

            if (!password) {
                throw new Error("Password is required.");
            }

            const email = usernameToEmail(normalizedUsername);

            const { data, error } =
                await supabaseClient.auth.signInWithPassword({
                    email,
                    password
                });

            if (error) {
                handleError(error);
            }

            return {
                success: true,
                user: data.user,
                session: data.session
            };

        } catch (error) {
            throw new Error(error.message);
        }
    }

    // =========================================
    // 5. SIGN OUT
    // =========================================

    async function signOut() {
        const { error } = await supabaseClient.auth.signOut();

        if (error) {
            handleError(error);
        }

        return {
            success: true
        };
    }

    // =========================================
    // 6. GET CURRENT SESSION
    // =========================================

    async function getSession() {
        const { data, error } =
            await supabaseClient.auth.getSession();

        if (error) {
            handleError(error);
        }

        return data.session;
    }

    // =========================================
    // 7. GET CURRENT USER
    // =========================================

    async function getCurrentUser() {
        const { data, error } =
            await supabaseClient.auth.getUser();

        if (error) {
            if (error.name === "AuthSessionMissingError") {
                return null;
            }

            handleError(error);
        }

        return data.user;
    }

    // =========================================
    // 8. CHECK AUTHENTICATION
    // =========================================

    async function isAuthenticated() {
        const user = await getCurrentUser();

        return Boolean(user);
    }

    // =========================================
    // 9. UNLOCK EDITING
    // Re-authenticate the current user.
    // =========================================

    async function unlockEditing(password) {
        if (!password) {
            throw new Error("Password is required.");
        }

        const currentUser = await getCurrentUser();

        if (!currentUser) {
            throw new Error(
                "You must be signed in to unlock editing."
            );
        }

        const username = currentUser.user_metadata?.username;

        if (!username) {
            throw new Error(
                "Unable to retrieve the current username."
            );
        }

        const email = usernameToEmail(username);

        const { data, error } =
            await supabaseClient.auth.signInWithPassword({
                email,
                password
            });

        if (error) {
            handleError(error);
        }

        if (data.user.id !== currentUser.id) {
            throw new Error(
                "Authentication failed. The account does not match."
            );
        }

        return {
            success: true,
            user: data.user
        };
    }

    // =========================================
    // 10. UPDATE ACCOUNT
    // Update username and/or password.
    // =========================================

    async function updateAccount({ username, password } = {}) {
        const currentUser = await getCurrentUser();

        if (!currentUser) {
            throw new Error(
                "You must be signed in to update your account."
            );
        }

        const updates = {};

        // Update username and its corresponding synthetic email.
        if (username !== undefined) {
            const normalizedUsername = validateUsername(username);

            const currentUsername = normalizeUsername(
                currentUser.user_metadata?.username
            );

            if (normalizedUsername !== currentUsername) {
                updates.email = usernameToEmail(normalizedUsername);

                updates.data = {
                    ...(currentUser.user_metadata || {}),
                    username: normalizedUsername
                };
            }
        }

        // Update password only when a new password is provided.
        if (password !== undefined && password !== "") {
            validatePassword(password);
            updates.password = password;
        }

        if (Object.keys(updates).length === 0) {
            throw new Error("No account changes were provided.");
        }

        const { data, error } =
            await supabaseClient.auth.updateUser(updates);

        if (error) {
            handleError(error);
        }

        return {
            success: true,
            user: data.user
        };
    }

    // =========================================
    // 11. AUTH STATE LISTENER
    // =========================================

    function onAuthStateChange(callback) {
        const { data } =
            supabaseClient.auth.onAuthStateChange(
                (event, session) => {
                    callback({
                        event,
                        session,
                        user: session?.user || null
                    });
                }
            );

        return data.subscription;
    }

    // =========================================
    // 11b. BACKEND API (Render) — contract for src/assistant/web.py
    // Replace localStorage gradually: each helper calls Render first and
    // returns { status, ok, data, fallback? } so callers can fall back to
    // local state when the backend is unavailable (offline / cold start).
    // =========================================
    const RENDER_API_URL = "";

    function resolveApiBase() {
        if (RENDER_API_URL.trim()) {
            return RENDER_API_URL.trim().replace(/\/+$/, "");
        }
        if (
            window.location.protocol.startsWith("http") &&
            (window.location.hostname === "127.0.0.1" ||
                window.location.hostname === "localhost")
        ) {
            return window.location.origin;
        }
        return "";
    }

    async function getAuthHeaders() {
        try {
            const { data } = await supabaseClient.auth.getSession();
            const token = data?.session?.access_token;
            if (token) {
                return { Authorization: `Bearer ${token}` };
            }
        } catch (_) { /* ignore */ }
        return {};
    }

    async function apiRequest(path, options = {}) {
        const base = resolveApiBase();
        if (!base) {
            return { status: 0, ok: false, data: null, networkError: true, fallback: true };
        }
        try {
            const response = await fetch(`${base}${path}`, {
                headers: {
                    "Content-Type": "application/json",
                    ...(await getAuthHeaders()),
                    ...(options.headers || {})
                },
                ...options
            });
            let data = null;
            try { data = await response.json(); } catch (_) { data = null; }
            if (!response.ok && window.YourinErrors?.handleStatus) {
                window.YourinErrors.handleStatus(response.status, data);
            }
            return { status: response.status, ok: response.ok, data };
        } catch (_) {
            if (window.YourinErrors?.handleStatus) {
                window.YourinErrors.handleStatus(0, null);
            }
            return { status: 0, ok: false, data: null, networkError: true, fallback: true };
        }
    }

    const backend = {
        getHealth: () => apiRequest("/api/health"),
        getConfig: () => apiRequest("/api/config"),
        askAssistant: (question) =>
            apiRequest("/api/answer", {
                method: "POST",
                body: JSON.stringify({ question })
            }),

        // CV
        getCV: () => apiRequest("/api/cv"),
        saveCV: (payload) =>
            apiRequest("/api/cv", {
                method: "PUT",
                body: JSON.stringify(payload || {})
            }),

        // Interviews
        getInterviews: () => apiRequest("/api/interviews"),
        createInterview: (payload) =>
            apiRequest("/api/interviews", {
                method: "POST",
                body: JSON.stringify(payload || {})
            }),
        getInterview: (id) =>
            apiRequest(`/api/interviews/${encodeURIComponent(id)}`),
        updateInterview: (id, payload) =>
            apiRequest(`/api/interviews/${encodeURIComponent(id)}`, {
                method: "PUT",
                body: JSON.stringify(payload || {})
            }),
        finalizeInterview: (id) =>
            apiRequest(`/api/interviews/${encodeURIComponent(id)}/finalize`, {
                method: "POST"
            }),
        deleteInterview: (id) =>
            apiRequest(`/api/interviews/${encodeURIComponent(id)}`, {
                method: "DELETE"
            }),

        // Report + feedback
        getReport: (id) =>
            apiRequest(`/api/interviews/${encodeURIComponent(id)}/report`),
        submitFeedback: (payload) =>
            apiRequest("/api/feedback", {
                method: "POST",
                body: JSON.stringify(payload || {})
            })
    };

    // =========================================
    // 12. PUBLIC API
    // =========================================

    window.YourinAPI = {
        signUp,
        signIn,
        signOut,
        getSession,
        getCurrentUser,
        isAuthenticated,
        unlockEditing,
        updateAccount,
        onAuthStateChange,
        // backend (Render) helpers
        request: apiRequest,
        getHealth: backend.getHealth,
        getConfig: backend.getConfig,
        askAssistant: backend.askAssistant,
        getCV: backend.getCV,
        saveCV: backend.saveCV,
        getInterviews: backend.getInterviews,
        createInterview: backend.createInterview,
        getInterview: backend.getInterview,
        updateInterview: backend.updateInterview,
        finalizeInterview: backend.finalizeInterview,
        deleteInterview: backend.deleteInterview,
        getReport: backend.getReport,
        submitFeedback: backend.submitFeedback,
        backend
    };

    return window.YourinAPI;

})().catch((error) => {
    console.error(
        "Yourin authentication API initialization failed:",
        error
    );

    throw error;
});