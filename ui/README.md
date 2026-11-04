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

### Option 2: Offline Static Demo
Open `ui/index.html` directly in Chrome or Edge (no server or internet required):
1. The entry page redirects to `sign-in.html`.
2. Pre-filled demo credentials: **`Eric Arthur Blair` / `demo1234`** → click **Sign in**.

---

## Demo Walkthrough

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
   - Enter any demo password and click **Unlock editing** to update your username or default CV (4 text sections or PDF upload).

---

## Directory Structure (`ui/`)

| Category | Files |
| --- | --- |
| **Entry & Auth** | `index.html`, `sign-in.html`, `sign-up.html`, `profile.html` |
| **Main Navigation** | `dashboard.html`, `storage.html` |
| **Interview Flow** | `job-profile.html`, `interview.html`, `interview-interrupt.html`, `done-interview.html` |
| **Results & Survey** | `report.html`, `system-feedback.html`, `thank-you.html` |
| **Styles & Scripts** | `css/styles.css`, `js/data.js` (sample Figma data), `js/app.js` (state & UI controller) |
| **Vector Assets** | `assets/*.svg` (`logo.svg`, `avatar.svg`, `microphone.svg`, `dashboard-hero-banner.svg`, `card-banner-1..3.svg`, `decor-top.svg`, `decor-bottom.svg`) |

See [`docs/ui-transitions.md`](../docs/ui-transitions.md) for the complete screen-to-screen transition map.

## Owner
- `team06`
