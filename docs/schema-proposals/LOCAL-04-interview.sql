-- PROPOSAL ONLY: requires Huy/team approval before shared database use.
-- Additions to the existing team tables; no backfill, score conversion or grants.
-- Existing sessions remain unmanaged (interview_format IS NULL).
BEGIN;
ALTER TABLE sessions
    ADD COLUMN interview_format smallint CHECK (interview_format = 1),
    ADD COLUMN name text,
    ADD COLUMN job_profile jsonb,
    ADD COLUMN question_generation jsonb,
    ADD COLUMN current_question smallint CHECK (current_question BETWEEN 0 AND 2),
    ADD COLUMN status text CHECK (status IN ('in_progress', 'interrupted', 'finalized')),
    ADD COLUMN revision integer CHECK (revision >= 0),
    ADD COLUMN version integer CHECK (version >= 0),
    ADD COLUMN report jsonb,
    ADD COLUMN updated_at timestamptz;
ALTER TABLE session_questions ADD COLUMN question_snapshot jsonb;
ALTER TABLE answers
    ADD COLUMN grading_status text CHECK (grading_status IN
        ('unanswered', 'draft', 'pending', 'graded', 'rejected')),
    ADD COLUMN grading_id text,
    ADD COLUMN error_code text;
ALTER TABLE grades ADD COLUMN result jsonb;
CREATE INDEX sessions_interview_owner_idx ON sessions (user_id, id)
    WHERE interview_format = 1;
CREATE INDEX session_questions_interview_idx ON session_questions (session_id, display_order);
CREATE INDEX answers_interview_idx ON answers (session_id, question_id);
CREATE INDEX grades_interview_idx ON grades (session_id, question_id);
COMMIT;
