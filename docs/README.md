# Project Documentation

This directory contains documentation related to the Smart Virtual Assistant project:
- `interview-api.md`: Local FastAPI interview lifecycle, background grading/evidence guard, API examples and integration handoff.
- `backend-progress.md`: Completed local functionality, verification results and remaining integration work.
- `backend-handoff.md`: Verified new Supabase schema and proposed shared API/Auth boundaries for the other backend owner.
- `interview-postgres.md`: Tested relational adapter, explicit runtime configuration, schema proposal and repeatable PostgreSQL tests (LOCAL-04).
- `schema-proposals/LOCAL-04-interview.sql`: Additive schema proposal for team review; never applied automatically or to shared Supabase in this session.
- `reviews/PR-41.md`: Review of the other backend APIs, two reproduced findings and the base Auth test correction.
- `integration-todo.md`: Ordered plan for joining the local interview lifecycle with AI, Auth, Frontend and the future team database schema.
- `backlog/LOCAL-01-interview-lifecycle.md`: Local backlog scope and acceptance criteria for the interview backend.
- `team.md`: Team members' information and assigned tasks.
- `ai-interface.md`: Contract and function signature for `src/assistant/ai.py` (`answer()`, input/output dataclasses, error hierarchy, and rule-based fallback).
- `ai-or-not.md`: Classification of 20 user questions (10 requiring AI vs. 10 deterministic rule/data lookups).
- `security-check.md`: Summary of manual and automated security audits.
- `ui-transitions.md`: Prototype screen-to-screen transition map for the Yourin Web UI (`ui/`).
