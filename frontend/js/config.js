/* =========================================
   YOURIN - PUBLIC CONFIGURATION
   ========================================= */

window.YourinConfigPromise = (async () => {
    const response = await fetch("http://127.0.0.1:8000/api/config");

    if (!response.ok) {
        throw new Error("Unable to load application configuration.");
    }

    const config = await response.json();

    if (!config.supabaseUrl || !config.supabasePublishableKey) {
        throw new Error("Supabase configuration is incomplete.");
    }

    return Object.freeze(config);
})();