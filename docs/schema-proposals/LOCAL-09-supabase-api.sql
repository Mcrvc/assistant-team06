-- PROPOSAL FOR HUY TO REVIEW. Not executed on shared Supabase by the agent.
-- Replaces the old 14-column direct-Postgres proposal for the API adapter only.
-- Existing rows remain untouched. Backend service_role only; no browser access.
BEGIN;
ALTER TABLE public.sessions
  ADD COLUMN IF NOT EXISTS current_question_index integer,
  ADD COLUMN IF NOT EXISTS interview_state jsonb;

CREATE OR REPLACE FUNCTION public.yourin_interview_v1(
  p_operation text, p_owner uuid DEFAULT NULL, p_id text DEFAULT NULL,
  p_item jsonb DEFAULT NULL, p_expected_version integer DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE
  old_item jsonb;
  q jsonb;
  a jsonb;
  g jsonb;
  qid bigint;
  idx integer;
BEGIN
  IF p_operation = 'check' THEN
    RETURN jsonb_build_object('schema_version', 1);
  END IF;
  IF p_owner IS NULL THEN
    RAISE EXCEPTION 'Verified owner required' USING ERRCODE='22023';
  END IF;
  IF p_operation = 'list' THEN
    RETURN coalesce((SELECT jsonb_agg(s.interview_state->'interview' ORDER BY s.created DESC,s.id)
      FROM public.sessions s WHERE s.user_id=p_owner AND s.interview_state->>'format'='1'), '[]'::jsonb);
  END IF;
  IF p_operation = 'get' THEN
    RETURN (SELECT s.interview_state->'interview' FROM public.sessions s
      WHERE s.id=p_id AND s.user_id=p_owner AND s.interview_state->>'format'='1');
  END IF;
  IF p_operation NOT IN ('create','save','delete') THEN
    RAISE EXCEPTION 'Invalid operation' USING ERRCODE='22023';
  END IF;
  IF p_operation IN ('save','delete') THEN
    SELECT s.interview_state->'interview' INTO old_item FROM public.sessions s
      WHERE s.id=p_id AND s.user_id=p_owner AND s.interview_state->>'format'='1' FOR UPDATE;
    IF old_item IS NULL THEN
      RAISE EXCEPTION 'Interview changed or missing' USING ERRCODE='PT409';
    END IF;
    IF p_operation = 'delete' THEN
      -- Parent is owner-checked/locked before deleting any child rows.
      DELETE FROM public.grades WHERE session_id=p_id;
      DELETE FROM public.answers WHERE session_id=p_id;
      DELETE FROM public.session_questions WHERE session_id=p_id;
      DELETE FROM public.sessions WHERE id=p_id AND user_id=p_owner;
      -- Keep question-bank records: other sessions may reference them.
      RETURN 'null'::jsonb;
    END IF;
    IF p_expected_version IS NULL OR (old_item->>'version')::integer <> p_expected_version THEN
      RAISE EXCEPTION 'Interview changed' USING ERRCODE='PT409';
    END IF;
  END IF;
  IF p_item IS NULL OR jsonb_typeof(p_item) <> 'object'
    OR (p_item->>'id') IS DISTINCT FROM p_id
    OR (p_item->>'owner_id')::uuid IS DISTINCT FROM p_owner
    OR jsonb_array_length(p_item->'questions') IS DISTINCT FROM 3
    OR jsonb_array_length(p_item->'answers') IS DISTINCT FROM 3
    OR NOT coalesce((p_item->>'current_question')::integer BETWEEN 0 AND 2, false)
    OR NOT coalesce(p_item->>'status' IN ('in_progress','interrupted','finalized'),false)
    OR (p_item->>'version') IS NULL THEN
    RAISE EXCEPTION 'Invalid interview state' USING ERRCODE='22023';
  END IF;
  IF p_operation = 'create' THEN
    IF (p_item->>'version')::integer <> 0 THEN
      RAISE EXCEPTION 'Invalid initial version' USING ERRCODE='22023';
    END IF;
    INSERT INTO public.sessions(id,user_id,created)
      VALUES(p_id,p_owner,(p_item->>'created_at')::timestamptz);
    FOR idx IN 0..2 LOOP
      q := p_item->'questions'->idx;
      INSERT INTO public.questions(question_text,role_hint,seniority)
        VALUES(q->>'text',p_item->'job_profile'->>'title',p_item->'job_profile'->>'level')
        RETURNING id INTO qid;
      INSERT INTO public.session_questions(session_id,question_id,display_order,grounded)
        VALUES(p_id,qid,idx,q->>'source_type'='reference');
      INSERT INTO public.answers(session_id,question_id,answer_text)
        VALUES(p_id,qid,'');
    END LOOP;
  ELSE
    IF (p_item->>'version')::integer <> p_expected_version+1
      OR p_item->'questions' IS DISTINCT FROM old_item->'questions'
      OR p_item->>'created_at' IS DISTINCT FROM old_item->>'created_at'
      OR p_item->'job_profile' IS DISTINCT FROM old_item->'job_profile'
      OR p_item->'cv' IS DISTINCT FROM old_item->'cv' THEN
      RAISE EXCEPTION 'Invalid state update' USING ERRCODE='22023';
    END IF;
  END IF;
  UPDATE public.sessions SET
    interview_name=p_item->>'name', company=p_item->'job_profile'->>'company',
    role=p_item->'job_profile'->>'title', seniority=p_item->'job_profile'->>'level',
    parsed_cv=p_item->>'cv', finished=p_item->>'status'='finalized',
    finished_at=CASE WHEN p_item->>'status'='finalized' THEN (p_item->>'updated_at')::timestamptz END,
    current_question_index=(p_item->>'current_question')::integer,
    ai_overall_comment=p_item->'report'->>'feedback',
    ai_overall_rating=p_item->'report'->>'label',
    interview_state=jsonb_build_object('format',1,'interview',p_item)
    WHERE id=p_id AND user_id=p_owner;
  FOR idx IN 0..2 LOOP
    SELECT question_id INTO STRICT qid FROM public.session_questions
      WHERE session_id=p_id AND display_order=idx;
    a := p_item->'answers'->idx;
    g := a->'grade';
    UPDATE public.answers SET answer_text=a->>'text',
      ai_comment=CASE WHEN a->>'grading_status'='graded' THEN g->>'feedback' END,
      -- Existing UI/report rule, pending AI-owner review; not grades.level.
      ai_rating=CASE WHEN a->>'grading_status'='graded' THEN
        CASE WHEN (g->>'score')::numeric >= 6 THEN 'Good' ELSE 'Needs Improvement' END END
      WHERE session_id=p_id AND question_id=qid;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'Answer row missing' USING ERRCODE='22023';
    END IF;
    DELETE FROM public.grades WHERE session_id=p_id AND question_id=qid;
    IF a->>'grading_status'='graded' THEN
      INSERT INTO public.grades(session_id,question_id,evidence_quoted,accepted)
        SELECT p_id,qid,value,true FROM jsonb_array_elements_text(g->'evidence');
      -- No invented conversion from score 0..10 to competency level 1..5.
      -- Full score, grading_id, rubric, sources and report remain in state.
    END IF;
  END LOOP;
  RETURN 'null'::jsonb;
END;
$$;
REVOKE ALL ON FUNCTION public.yourin_interview_v1(text,uuid,text,jsonb,integer) FROM PUBLIC;
-- Supabase roles exist on cloud. Conditional grants also allow isolated local tests.
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
    REVOKE ALL ON FUNCTION public.yourin_interview_v1(text,uuid,text,jsonb,integer) FROM anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
    REVOKE ALL ON FUNCTION public.yourin_interview_v1(text,uuid,text,jsonb,integer) FROM authenticated;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN
    GRANT EXECUTE ON FUNCTION public.yourin_interview_v1(text,uuid,text,jsonb,integer) TO service_role;
  END IF;
END $$;
NOTIFY pgrst, 'reload schema';
COMMIT;
