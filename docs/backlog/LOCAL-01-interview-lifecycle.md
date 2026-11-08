# LOCAL-01: Local interview lifecycle backend

Owner: Tran Bao Anh. Local backlog item; no GitHub issue number assigned.
Scope authorized by the user: implement an independently runnable backend with
local persistence and mock AI before team integration.

Acceptance criteria:

- Create an interview from a job profile and optional CV text, storing 3 questions.
- Save answers and the current question; interrupt and resume after a server restart.
- Use FastAPI/Uvicorn/Pydantic/SQLAlchemy per the user's additional Backend design.
- Persist each submitted answer before background grading; check every evidence
  quote against the exact answer text and reject fabricated evidence.
- Store question criteria and source labels; expose answered/graded progress.
- Finalize completed, graded answers and persist a clearly labeled mock report.
- Keep interview ownership checks, validate requests, prevent lost concurrent updates,
  and use a deterministic fallback if an injected AI provider fails.
- Supply an API contract, an executable local walkthrough and meaningful tests.
- Preserve the existing CLI, API and static UI. Do not wire the team's UI yet.

Integration still needed: team PostgreSQL schema/repository, verified session-cookie Auth identity, real AI
provider, frontend calls, deployment and teammate review. No cloud changes or
GitHub publication are part of this local implementation.
