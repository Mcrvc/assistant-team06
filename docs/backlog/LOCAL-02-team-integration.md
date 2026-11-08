# LOCAL-02: Integrate the existing team branches locally

Authorized by Tran Bao Anh on 08/11/2026: complete work that does not require
teammate coordination, with a tested local commit after each task. No push,
shared database writes, deployment or messages to teammates are authorized.

- [x] Preserve the tested local lifecycle as checkpoint `3d89d55` (41 tests).
- [x] Bring in origin/frontend (including AI/authen), expose one ASGI app and a
  consistent install/configuration path while preserving the original prototype.
- [x] Add an opt-in real AI adapter, weighted rubrics, model-generated evidence,
  safe timeouts/fallback and explicit CV forwarding controls. Test without keys.
- [x] Add verified Supabase Bearer authentication matching the existing branches.
  Keep demo authentication explicitly local and separate from the production path.
- [ ] Wire the team's interview UI to the API: creation, answers, resume,
  grading progress and finalize; test the integrated browser flow with fake data.
- [ ] Document completed checkpoints and remaining integration decisions.

Wait for coordination: team PostgreSQL schema/migrations, actual provider keys,
CV data policy confirmation, live Auth configuration, PR review and deployment.
Profile/history/report-specific/feedback APIs remain the other backend owner's scope.

AI assistance must be disclosed in the eventual PR. These local IDs are not
GitHub issue numbers; link the team's actual issue before publishing the PR.
