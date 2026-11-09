# User Interface — Yourin (Interview AI Assistant)

## Overview
This directory contains the user interface components for the assistant project (`team06`), featuring both:
- **Command Line Interface (CLI)**: `python -m assistant`
- **Web Interface (`ui/`)**: **Yourin — Interview AI Assistant** (HTML/CSS/JS static PoC & local Python web server)

---

## Running the UI

### Option 1: Launch via Python Backend (`src/assistant`)
From the repository root (with virtual environment active):

```bash
python -m assistant --ui
```

This starts a local HTTP server from `src/assistant/web.py`, serves the `ui/` directory at `http://127.0.0.1:8000`, exposes the `/api/answer` endpoint backed by `src/assistant/ai.py`, and opens your browser.

### Option 2: Static preview only
`python -m http.server 8000 --directory ui` can preview the layout, but it does not provide `/api/config`, so authentication and API calls will not work. Use Option 1 for a functional local app. The browser also loads the Supabase SDK from jsDelivr, so internet access is required. Opening the files directly with `file://` is not supported for authentication.

---

## Authentication

- `ui/sign-in.html` and `ui/sign-up.html` use Supabase Auth through `js/api.js`; there are no local demo passwords.
- Usernames are converted to `<username>@yourin.app`. Usernames must be 3–60 lowercase letters, numbers, or underscores; passwords must be 8–128 characters.
- The backend `/api/config` must return `supabaseConfigured: true`, `supabaseUrl`, and `supabasePublishableKey`. Only the publishable/anon key is sent to the browser; secret keys stay on the server.
- Protected pages redirect to `sign-in.html` when there is no session and restore the requested page after login.
- API requests automatically include `Authorization: Bearer <access_token>` when a session exists.
- If Supabase is not configured, the UI shows an explicit error and disables the auth form instead of falling back to fake credentials.
- Supabase email confirmation must be disabled for the synthetic `@yourin.app` addresses, or replaced with a real email/profile flow before production.

Interview data is still stored in `localStorage` per Supabase user id. Replacing that storage with the interview APIs is the next frontend task.

---

## Walkthrough

1. **Create a new interview** (`dashboard.html` → `job-profile.html`):
   - Paste a job description/HTML/URL, or switch to manual 4-field entry (`Job title`, `Domain`, `Company`, `Seniority / Level`).
   - Optionally expand **USE CV FOR THIS INTERVIEW?** to sync your saved CV, paste custom CV text, or upload a PDF.
2. **Start Interview** (`interview.html`):
   - Click **Continue** to start Question 1 of 3 with the interactive **YORI** AI interviewer robot.
   - Type or record your answer (speech-to-text supported where available) and navigate via **Next Question** / **Previous Question**.
   - Navigating away triggers the **Save & Exit** modal (`interview-interrupt.html`); you can resume anytime from **Your Interview** (`storage.html`).
3. **Finalize & View Report** (`done-interview.html` → `report.html`):
   - On Question 3, click **Finalize Interview**, name the session, and click **View Report**.
   - Review side-by-side answers, AI feedback with status badges (`Good` / `Needs Improvement`), and optional CV snapshot.
   - Use **Retake interview** to practice again with the same job/CV setup, or **Rate this feedback →** to open `system-feedback.html`.
4. **Profile & Account Management** (`profile.html`):
   - Verify your current Supabase password to unlock account editing; username/password updates go through Supabase Auth. The default CV (4 text sections or PDF upload) remains local for now.

---

## Directory Structure (`ui/`)

| Category | Files |
| --- | --- |
| **Entry & Auth** | `index.html`, `sign-in.html`, `sign-up.html`, `profile.html` |
| **Main Navigation** | `dashboard.html`, `storage.html` |
| **Interview Flow** | `job-profile.html`, `interview.html`, `interview-interrupt.html`, `done-interview.html` |
| **Results & Survey** | `report.html`, `system-feedback.html`, `thank-you.html` |
| **System Pages** | `404.html` (served automatically by Vercel for unknown paths) |
| **Styles & Scripts** | `css/styles.css`, `js/data.js` (sample Figma data), `js/app.js` (state & UI controller), `js/api.js` (Render API client + Supabase Auth), `js/errors.js` (toast/banner), `js/ui.js` (loading overlay) |
| **Vector Assets** | `assets/*.svg` (`logo.svg`, `avatar.svg`, `microphone.svg`, `dashboard-hero-banner.svg`, `card-banner-1..3.svg`, `decor-top.svg`, `decor-bottom.svg`) |

## Shared UI states

- `js/api.js` resolves the Render URL, calls `/api/...`, and forwards failed HTTP statuses to `js/errors.js`.
- `js/api.js` accepts `{ loading: { title, detail, steps, coldStartAfter } }` or `requestWithLoading(...)` for long-running calls. The overlay switches to the Render cold-start message after 5 seconds by default.
- `js/errors.js` exposes `YourinErrors.showToast()` and `YourinErrors.showBanner()`. It reads nested backend errors (`{ error: { code, message } }`) and FastAPI validation details, shows a toast for 400/403, redirects on 401, and shows a retry banner for 500/503/network failures.
- `js/ui.js` exposes `YourinUI.loading.show()` / `hide()` and waits before showing the Render cold-start notice.
- Preview a loading state without a backend: `dashboard.html?demo=loading`, `?demo=questions`, `?demo=report`, or `?demo=cold-start`.

See [`docs/ui-transitions.md`](../docs/ui-transitions.md) for the complete screen-to-screen transition map.

## Owner
- `team06`
