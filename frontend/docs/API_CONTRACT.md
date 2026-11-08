# Frontend ↔ Backend API Contract (draft)

## LOCAL-02 implementation update

The working interview contract is documented in [the canonical API guide](../../docs/interview-api.md).
Run one server with `python -m assistant --interview-api`; the team UI is at `/app/`.
`js/interviews.js` maps UI job/CV values to `job_profile`/CV text and uses server IDs.
Writes use revision, POST progress saves drafts, POST answers/{index} queues per-answer
grading, GET progress polls counts, and finalize aggregates already-graded answers.
GET by ID returns the canonical object directly. Demo cookies work only in explicit
local demo mode; the non-demo path verifies Supabase Bearer tokens.

The remaining text below is the original team draft. Its list/CV/report-specific/
feedback APIs are not implemented by the interview lifecycle work. Its finalize-time
grading and payload shapes do not describe the current `/app/` integration.
PDF metadata is not treated as an uploaded CV; real-provider CV forwarding is opt-in.

Base URL: Render service (`src/assistant/web.py`). Frontend resolves it via `RENDER_API_URL`
or `window.location.origin` on localhost. All endpoints return JSON. Protected endpoints
expect `Authorization: Bearer <supabase access token>`.

Authentication itself is handled client-side by Supabase Auth (`frontend/js/api.js`);
the backend only verifies the JWT via `SUPABASE_JWKS_URL`.

## Health / config
- `GET /api/health` → `{ status, supabase_configured, jwks_configured, llm_configured }`
- `GET /api/config` → `{ supabaseConfigured, supabaseUrl, supabasePublishableKey, jwksConfigured, llmConfigured }`

## AI
- `POST /api/answer` `{ question }` → `{ text, sources, model, used_fallback, usage, error }`

## CV (profile.html)
- `GET /api/cv` → `{ cv: string[4], cvMode: "text"|"pdf", cvPdf: {name,size,date}|null }` (404 if none)
- `PUT /api/cv` `{ cv: string[4], cvMode, cvPdf }` → `{ ok: true }`

## Interviews
- `GET /api/interviews` → `{ interviews: [{ id, name, date, finished, answers: string[3], cv, cvPdf, cvMode, job }] }`
- `POST /api/interviews` `{ job, cv, cvMode, cvPdf }` → created interview (with `questions` from AI) `{ id, name, date, finished, answers, cv, cvPdf, cvMode, job, questions }`
- `GET /api/interviews/:id` → `{ interview }`
- `PUT /api/interviews/:id` `{ name?, answers?, finished?, job? }` → `{ ok: true }`
- `DELETE /api/interviews/:id` → `{ ok: true }`
- `POST /api/interviews/:id/finalize` → `{ report }` (triggers AI grading; may be async → returns `{ queued: true, job_id }` per Domain Focus MVP)
- `GET /api/interviews/:id/report` → `{ report }`

## Feedback
- `POST /api/feedback` `{ grade_rating, quality_rating, difficulty, comments, would_recommend }` → `{ ok: true }`

## Notes for backend owners
- Status codes matter for the frontend: 400 → toast, 401 → redirect to sign-in, 500/503/0 → fallback banner.
- Domain Focus MVP asks for background grading with polling `/api/job/{job_id}`; if finalize is async, return `{ queued: true, job_id }` and a `GET /api/job/:job_id` endpoint.
- CV text must never leave the machine per MVP 1.6; backend should store only what the frontend sends and never re-extract.
