-- Minimal local fixture of the pre-LOCAL-04 team columns used by the adapter.
-- This is NOT a migration for Supabase: auth.users and RLS are not emulated.
CREATE TABLE accounts (id uuid PRIMARY KEY, username varchar NOT NULL UNIQUE);
CREATE TABLE sessions (
    id text PRIMARY KEY, user_id uuid REFERENCES accounts(id),
    role text, seniority text, parsed_cv text, created timestamptz DEFAULT now(),
    finished boolean DEFAULT false, finished_at timestamptz,
    interview_name varchar(255), company varchar(255)
);
CREATE TABLE questions (
    id bigserial PRIMARY KEY, question_text text, role_hint text, seniority text
);
CREATE TABLE session_questions (
    id bigserial PRIMARY KEY, session_id text REFERENCES sessions(id) ON DELETE CASCADE,
    question_id bigint REFERENCES questions(id) ON DELETE CASCADE,
    display_order smallint, grounded boolean
);
CREATE TABLE answers (
    id bigserial PRIMARY KEY, session_id text REFERENCES sessions(id) ON DELETE CASCADE,
    question_id bigint REFERENCES questions(id) ON DELETE CASCADE,
    answer_text text
);
CREATE TABLE grades (
    id bigserial PRIMARY KEY, session_id text REFERENCES sessions(id) ON DELETE CASCADE,
    question_id bigint REFERENCES questions(id) ON DELETE CASCADE,
    competency text, level smallint, evidence_quoted text, accepted boolean
);
