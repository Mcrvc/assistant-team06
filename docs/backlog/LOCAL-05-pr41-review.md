# LOCAL-05: Review PR #41 and isolate the existing Auth test

User relayed Truong Bao Anh's request to review PR #41, which adds Profile/CV,
history, report and feedback APIs to the shared feature branch.

- [x] Review exact head 6ebf1b3 against base cb94194 in an isolated worktree.
- [x] Run the submitted suite with disposable PostgreSQL and browser tests.
- [x] Exercise PostgreSQL list_for_owner and reproduce missing boundary cases.
- [x] Fix the base branch's environment-dependent Auth test and verify both modes.
- [x] Record findings and reproduction details for the user to forward.

Results: PR unchanged 192 tests passed; PR + base test fix preview 193 passed
with Supabase configured. Two extra probes reproduce P2 issues, documented in
docs/reviews/PR-41.md. PostgreSQL owner/order/legacy-filter probe passed.

No merge, approval, PR comment, teammate message, deployment or shared database
write is part of this review. Do not rewrite the author's PR branch.
