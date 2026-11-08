# LOCAL-04: Complete the interview persistence implementation independently

Authorized by Tran Bao Anh: finish the interview work locally before the team
settles the remaining formats; commit each completed task as a checkpoint.
This local backlog ID is not a GitHub issue number.

- [x] Implement a relational repository based on the team's existing tables,
  with an explicitly proposed schema extension for lossless lifecycle storage.
- [x] Verify transactions, ownership, concurrent grading, restart/resume,
  invalidated grades and finalized reports independently of cloud services.
- [x] Add explicit PostgreSQL runtime configuration, with no automatic DDL,
  no fallback to SQLite after a database failure, and sanitized errors.
- [x] Provide a repeatable PostgreSQL integration test and a concrete schema
  proposal/handoff for the team. Keep existing UI/API behavior unchanged.

Do not modify the shared Supabase database, push, deploy, or contact teammates.
Profile/CV, history/list and feedback APIs remain the other backend owner's work.
The proposed columns and grade format require team review before cloud use.

Verified locally: 154 tests passed, including 13 real PostgreSQL tests and
8 browser flows. Schema proposal applied only to isolated test schemas.
CI configuration is prepared locally; no claim that GitHub CI or cloud passed.
