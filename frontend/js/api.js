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
        onAuthStateChange
    };

    return window.YourinAPI;

})().catch((error) => {
    console.error(
        "Yourin authentication API initialization failed:",
        error
    );

    throw error;
});