# Frontend ↔ Backend API Contract (draft)

## LOCAL-02 implementation update

The working interview contract is documented in [the canonical API guide](../../docs/interview-api.md).
Run one server with `python -m assistant --interview-api`; the team UI is at `/app/`.
`js/interviews.js` maps UI job/CV values to `job_profile`/CV text and uses server IDs.
Writes use revision, POST progress saves drafts, POST answers/{index} queues per-answer
grading, GET progress polls counts, and finalize aggregates already-graded answers.
GET by ID returns the canonical object directly. Demo cookies work only in explicit
local demo mode; the non-demo path verifies Supabase Bearer tokens.

The remaining text below is the original team draft. The interview lifecycle, CV, history,
report and feedback APIs listed below are now implemented by the backend work; rename/delete
and async job polling are still not implemented. PDF metadata is not treated as an uploaded CV;
real-provider CV forwarding is opt-in.

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
- `GET /api/interviews` → `{ interviews: [{ id, name, status, finished, job_profile, created_at, updated_at, progress, has_report }] }` (newest first; owner-only summaries, no questions/answers/report body)
- `POST /api/interviews` `{ name?, job_profile: { title, description?, domain?, company?, level? }, cv? }` → canonical interview object (`id, owner_id, name, status, questions, answers, current_question, ...`)
- `GET /api/interviews/{id}` → canonical interview object directly (not wrapped)
- `POST /api/interviews/{id}/progress` `{ revision, answers?, current_question?, status? }` → canonical interview object
- `POST /api/interviews/{id}/answers/{index}` `{ revision, text }` → canonical interview object (queues background grading)
- `GET /api/interviews/{id}/progress` → `{ answered, graded, pending, rejected }`
- `POST /api/interviews/{id}/finalize` `{ revision, name? }` → canonical interview object with `report` (requires all 3 answers graded)
- `GET /api/interviews/{id}/report` → `{ id, name, report }` (409 until finalized)
- Rename/delete endpoints are **not implemented yet**; the frontend disables these actions for backend interviews.

## Feedback
- `POST /api/feedback` `{ grade_rating: 1-5, quality_rating: 1-5, difficulty?: "too_easy"|"just_right"|"too_hard", comments?: string (<=2000), would_recommend?: boolean, session_id?: string }` → `{ ok: true }` (201)
- `session_id`, if provided, must belong to the verified user; otherwise 404.
- CV and feedback are currently stored in an in-memory, per-process store until the Supabase schema is ready.

## Notes for backend owners
- Status codes matter for the frontend: 400 → toast, 401 → redirect to sign-in, 500/503/0 → fallback banner.
- Domain Focus MVP asks for background grading with polling `/api/job/{job_id}`; if finalize is async, return `{ queued: true, job_id }` and a `GET /api/job/:job_id` endpoint.
- CV text must never leave the machine per MVP 1.6; backend should store only what the frontend sends and never re-extract.
