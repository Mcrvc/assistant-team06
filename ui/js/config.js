/* =========================================
   YOURIN - PUBLIC CONFIGURATION
   ========================================= */

window.YourinConfigPromise = (async () => {
    const base = String(window.YOURIN_API_URL || window.location.origin).replace(/\/+$/, "");
    const response = await fetch(`${base}/api/config`);

    if (!response.ok) {
        throw new Error("Unable to load application configuration.");
    }

    const config = await response.json();

    if (!config.interviewDemoEnabled && (!config.supabaseUrl || !config.supabasePublishableKey)) {
        throw new Error("Supabase configuration is incomplete.");
    }

    return Object.freeze(config);
})();
