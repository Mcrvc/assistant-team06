"""Tests for the structured grader and the writer contract on branch ``AI``.

Covers the shape the team's interview lifecycle consumes
(``interview_ai.py`` calls ``generate_questions(..., timeout_s=...)`` and
``grade_answer_with_evidence(...)``), the inline-passage evidence rule, and the
mock reply shown when a grade is refused. All offline.
"""
from __future__ import annotations

import json

import pytest

from assistant import ai, aiworker
from assistant.ai import Completion


RUBRIC = {"max_score": 10, "criteria": [
    {"name": "definitions", "points": 5, "good": "Defines both algorithms"},
    {"name": "applied choice", "points": 5, "good": "Justifies a choice"},
]}

# Every quoted span below is copied character-for-character out of ANSWER,
# because that is what the grader requires and what we assert on.
GOOD_PAYLOAD = {
    "score": 8.0,
    "feedback": 'Ban neu "Token bucket cho phep burst" va "leaky bucket lam phang" '
                'nhung chua neu duoc khi nao chon leaky bucket.',
    "evidence": ["Token bucket cho phep burst", "leaky bucket lam phang"],
}

ANSWER = (
    "Token bucket cho phep burst theo dung tich, con leaky bucket lam phang "
    "luong request ra mot toc do co dinh. Toi se dung token bucket cho API "
    "cong khai vi luong request cua chung ta theo dot tu batch job."
)

GROUNDED_SPAN = "Token bucket cho phep burst"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No provider network, and no retry delay, for every test here."""
    monkeypatch.setattr(ai.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("unit tests must not reach a provider")))
    monkeypatch.setenv("AI_RETRY_DELAY_S", "0")
    ai.reset_config_cache()
    yield
    ai.reset_config_cache()


def _completion(payload) -> Completion:
    return Completion(text=json.dumps(payload, ensure_ascii=False), model="test-model")


# --------------------------------------------------------------------------
# The contract the team's adapter consumes
# --------------------------------------------------------------------------
def _plan_payload(total=4):
    """A valid interview plan: seniority, total and per-slot arc.

    Phases cycle with distinct focuses so any total (up to 15) validates.
    """
    arc = [("starter", "easy"), ("cv", "medium"), ("experience", "medium"),
           ("skills", "medium"), ("technical", "hard"), ("market", "hard"),
           ("behavioral", "hard")]
    slots = []
    for index in range(total):
        phase, difficulty = arc[index % len(arc)]
        slots.append({"phase": phase, "focus": f"probe {phase} theme {index}",
                      "difficulty": difficulty})
    return {"seniority": "intern", "total": total, "slots": slots}


def _question_payload(index):
    """One valid slot question (short, so the grounding pool check is a no-op)."""
    return {
        "question": f"Q{index}?",
        "phase": "cv",
        "why": "w",
        "rubric": {"max_score": 10, "criteria": [
            {"name": "a", "points": 5, "good": "g"},
            {"name": "b", "points": 5, "good": "g"}]},
    }


def _router_fake(monkeypatch, seen=None, plan_total=4, fail_slots=False):
    """Fake ``complete`` that answers the planner, then one question per slot."""
    state = {"slots": 0}

    def fake_complete(messages, **options):
        if seen is not None:
            seen.update(options)
        if messages[0]["content"] == aiworker.PLANNER_SYSTEM:
            return _completion(_plan_payload(plan_total))
        state["slots"] += 1
        if fail_slots:
            return _completion({"questions": "not a question object"})
        return _completion(_question_payload(state["slots"]))

    monkeypatch.setattr(aiworker, "complete", fake_complete)
    return state


def test_generate_questions_accepts_and_forwards_timeout(monkeypatch):
    seen = {}
    _router_fake(monkeypatch, seen)
    out = aiworker.generate_questions({"title": "x"}, {}, "", [], timeout_s=9.0)
    assert seen["timeout_s"] == 9.0
    assert len(out["questions"]) == 4  # the planner decided, not a fixed three


def test_generate_questions_returns_source_notes_and_sources(monkeypatch):
    _router_fake(monkeypatch)
    out = aiworker.generate_questions({"title": "x"}, {}, "notes here", ["https://a"])
    assert out["source"] == "nvidia"
    assert out["research_notes"] == "notes here"
    assert out["sources"] == ["https://a"]
    assert len(out["questions"]) == 4


def test_generate_questions_runs_one_call_per_planned_slot(monkeypatch):
    state = _router_fake(monkeypatch, plan_total=6)
    out = aiworker.generate_questions({"title": "x"}, {}, "notes", [])
    assert state["slots"] == 6
    assert [f"Q{i}?" for i in range(1, 7)] == [q["question"] for q in out["questions"]]


def test_generate_questions_falls_back_to_the_default_plan_when_the_planner_fails(monkeypatch):
    asked = {"n": 0}

    def planner_down(messages, **options):
        if messages[0]["content"] == aiworker.PLANNER_SYSTEM:
            raise aiworker.AiError("planner offline")
        asked["n"] += 1
        return _completion(_question_payload(asked["n"]))

    monkeypatch.setattr(aiworker, "complete", planner_down)
    out = aiworker.generate_questions({"title": "x"}, {}, "notes", [])
    assert len(out["questions"]) == aiworker.DEFAULT_PLAN["total"]


def test_grade_answer_with_evidence_returns_the_five_expected_keys(monkeypatch):
    monkeypatch.setattr(aiworker, "complete",
                        lambda m, **o: _completion(GOOD_PAYLOAD))

    grade = aiworker.grade_answer_with_evidence("Why rate limit?", ANSWER, RUBRIC)
    assert set(grade) == {"score", "feedback", "evidence", "model", "used_fallback"}
    assert grade["score"] == 8.0
    assert grade["used_fallback"] is False
    assert grade["model"] == "test-model"
    assert grade["evidence"] == GOOD_PAYLOAD["evidence"]


def test_grade_answer_with_evidence_forwards_timeout(monkeypatch):
    seen = {}

    def fake_complete(messages, **options):
        seen.update(options)
        return _completion(GOOD_PAYLOAD)
    monkeypatch.setattr(aiworker, "complete", fake_complete)

    aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC, timeout_s=7.0)
    assert seen["timeout_s"] == 7.0


# --------------------------------------------------------------------------
# Evidence must be verbatim and must be cited in the feedback
# --------------------------------------------------------------------------
def test_grounded_feedback_and_evidence_pass(monkeypatch):
    monkeypatch.setattr(aiworker, "complete",
                        lambda m, **o: _completion(GOOD_PAYLOAD))
    grade = aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC)
    for quote in grade["evidence"]:
        assert quote in ANSWER
    for span in aiworker._quoted_spans(grade["feedback"]):
        assert span in ANSWER


def test_fabricated_evidence_is_refused_not_passed(monkeypatch):
    monkeypatch.setattr(aiworker, "complete", lambda m, **o: _completion({
        "score": 9.0,
        "feedback": 'Ban neu "em dung Redis de luu cache" nhung chua noi ttl.',
        "evidence": ["em dung Redis de luu cache"],
    }))
    with pytest.raises(aiworker.EvidenceRejected) as excinfo:
        aiworker.grade_answer_with_evidence("q?", "Toi dung Redis.", RUBRIC)
    assert excinfo.value.code == "evidence_not_found"
    # A grade must never be returned alongside the refusal.
    assert excinfo.value.reply["used_fallback"] is True
    assert "score" not in excinfo.value.reply


def test_refused_grade_is_retried_three_times_before_it_is_given_up(monkeypatch):
    """A refusal is repaired up to GRADE_REPAIR_TURNS times: first call plus
    three repair turns, then EvidenceRejected - never a graded reply."""
    calls = {"n": 0}

    def always_fabricates(messages, **options):
        calls["n"] += 1
        return _completion({
            "score": 9.0,
            "feedback": 'Ban neu "em dung Redis de luu cache" nhung chua noi ttl.',
            "evidence": ["em dung Redis de luu cache"],
        })

    monkeypatch.setattr(aiworker, "complete", always_fabricates)
    with pytest.raises(aiworker.EvidenceRejected):
        aiworker.grade_answer_with_evidence("q?", "Toi dung Redis.", RUBRIC)
    assert calls["n"] == 1 + aiworker.GRADE_REPAIR_TURNS


def test_grade_recovered_on_the_third_repair_turn_passes(monkeypatch):
    """The repair loop keeps going while a turn can still fix the payload."""
    calls = {"n": 0}

    def bad_twice(messages, **options):
        calls["n"] += 1
        if calls["n"] <= 2:
            return _completion({
                "score": 9.0,
                "feedback": 'Ban neu "em dung Redis de luu cache" nhung chua noi ttl.',
                "evidence": ["em dung Redis de luu cache"],
            })
        return _completion(GOOD_PAYLOAD)

    monkeypatch.setattr(aiworker, "complete", bad_twice)
    grade = aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC)
    assert grade["score"] == GOOD_PAYLOAD["score"] and grade["used_fallback"] is False
    assert calls["n"] == 3


def test_feedback_quoting_a_passage_not_in_the_answer_is_refused(monkeypatch):
    monkeypatch.setattr(aiworker, "complete", lambda m, **o: _completion({
        "score": 6.0,
        "feedback": 'Ban viet "toi da scale 10 trieu request tren mot may" nhung thieu so lieu.',
        "evidence": [GROUNDED_SPAN],
    }))
    with pytest.raises(aiworker.EvidenceRejected) as excinfo:
        aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC)
    assert excinfo.value.code == "feedback_ungrounded"


def test_empty_evidence_list_is_refused(monkeypatch):
    monkeypatch.setattr(aiworker, "complete", lambda m, **o: _completion({
        "score": 5.0, "feedback": f'Tra loi on, thay "{GROUNDED_SPAN}".',
        "evidence": [],
    }))
    with pytest.raises(aiworker.EvidenceRejected):
        aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC)


def test_non_numeric_score_is_refused(monkeypatch):
    monkeypatch.setattr(aiworker, "complete", lambda m, **o: _completion({
        "score": "8", "feedback": f'Ban neu "{GROUNDED_SPAN}".',
        "evidence": [GROUNDED_SPAN],
    }))
    with pytest.raises(aiworker.EvidenceRejected) as excinfo:
        aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC)
    assert excinfo.value.code == "bad_score"


def test_missing_feedback_is_refused(monkeypatch):
    monkeypatch.setattr(aiworker, "complete", lambda m, **o: _completion({
        "score": 8.0, "feedback": "", "evidence": [GROUNDED_SPAN],
    }))
    with pytest.raises(aiworker.EvidenceRejected) as excinfo:
        aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC)
    assert excinfo.value.code == "no_feedback"


def test_blank_answer_is_a_caller_error(monkeypatch):
    with pytest.raises(ValueError):
        aiworker.grade_answer_with_evidence("q?", "   ", RUBRIC)


def test_quoted_span_extraction_ignores_empty_and_unbalanced():
    assert aiworker._quoted_spans('a "" b "x y" c') == ["x y"]
    assert aiworker._quoted_spans("no quotes here") == []


# --------------------------------------------------------------------------
# Diacritic tolerance: a real model drops one accent and must not be rejected
# --------------------------------------------------------------------------
def test_feedback_quote_missing_one_diacritic_is_accepted(monkeypatch):
    """The answer has "và", the prose writes "va". That is a transcription
    slip, not a fabrication, so the grade must still go through."""
    monkeypatch.setattr(aiworker, "complete", lambda m, **o: _completion({
        "score": 8.0,
        "feedback": 'Ban neu "Token bucket cho phep burst" va "leaky bucket lam phang".',
        "evidence": [GROUNDED_SPAN, "leaky bucket lam phang"],
    }))
    grade = aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC)
    assert grade["score"] == 8.0
    assert grade["used_fallback"] is False


def test_feedback_quoting_content_absent_from_the_answer_is_refused(monkeypatch):
    """Fabrication - not a diacritic slip - must still be rejected."""
    monkeypatch.setattr(aiworker, "complete", lambda m, **o: _completion({
        "score": 8.0,
        "feedback": 'Ban neu "Token bucket cho phep burst" va "toi da xu ly 1 tieu request".',
        "evidence": [GROUNDED_SPAN],
    }))
    with pytest.raises(aiworker.EvidenceRejected) as excinfo:
        aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC)
    assert excinfo.value.code == "feedback_ungrounded"


def test_normalise_folds_diacritics_case_and_whitespace():
    assert aiworker._normalise("Ví Dụ  TEST") == aiworker._normalise("vi du test")
    assert aiworker._normalise("a  b") == aiworker._normalise("a b")
    assert aiworker._normalise("và") == aiworker._normalise("va")


def test_evidence_must_stay_strictly_verbatim(monkeypatch):
    """Unlike the prose, evidence is matched exactly by the interview
    service, so a diacritic-only difference must be refused there."""
    monkeypatch.setattr(aiworker, "complete", lambda m, **o: _completion({
        "score": 8.0,
        "feedback": f'Ban neu "{GROUNDED_SPAN}".',
        "evidence": ["token bucket cho phep burst"],  # lower-case 't'
    }))
    with pytest.raises(aiworker.EvidenceRejected) as excinfo:
        aiworker.grade_answer_with_evidence("q?", ANSWER, RUBRIC)
    assert excinfo.value.code == "evidence_not_found"


# --------------------------------------------------------------------------
# Reject reply: explanatory, and never carries a score
# --------------------------------------------------------------------------
def test_rejected_reply_explains_without_scoring():
    for reason in ("evidence_not_found", "feedback_ungrounded", "bad_score",
                   "no_feedback", "no_evidence", "unknown_reason"):
        reply = aiworker.rejected_reply("q?", ANSWER, RUBRIC, reason)
        assert reply["used_fallback"] is True
        assert "score" not in reply
        assert reply["feedback"].strip()
    # An unknown reason still explains something usable.
    assert aiworker.rejected_reply("q", "a", RUBRIC, "nope")["reason"] == "nope"


def test_rejected_reply_messages_are_distinct_and_non_empty():
    """Each reason explains a different problem; none are blank."""
    seen = {}
    for reason in ("evidence_not_found", "feedback_ungrounded", "bad_score",
                   "no_feedback", "no_evidence"):
        text = aiworker.rejected_reply("q", "a", RUBRIC, reason)["feedback"]
        assert text.strip()
        seen[reason] = text
    # Every reason produces its own message, not one shared sentence.
    assert len(set(seen.values())) == len(seen)
    # The primary case must tell the candidate the evidence did not match.
    assert "word for word" in seen["evidence_not_found"]


def test_rejected_reply_messages_are_ascii_safe_for_logs():
    """The reply must survive a JSON round trip and stay readable."""
    import json
    payload = json.dumps(aiworker.rejected_reply("q", "a", RUBRIC),
                         ensure_ascii=False)
    assert "word for word" in json.loads(payload)["feedback"]


# --------------------------------------------------------------------------
# Writer shape: what the team's Generation/Rubric schema can accept
# --------------------------------------------------------------------------
def _questions(count=3, max_score=10, points=(4, 3, 3)):
    return {"questions": [
        {"question": f"Q{i}?", "category": "technical", "why": "w",
         "rubric": {"max_score": max_score, "criteria": [
             {"name": f"c{j}", "points": p, "good": "g"} for j, p in enumerate(points)]}}
        for i in range(count)]}


def test_valid_writer_payload_is_accepted():
    assert len(aiworker._validate_questions(_questions())) == 3


@pytest.mark.parametrize("payload,needle", [
    (_questions(count=0), "between 1 and 15"),
    (_questions(count=16), "between 1 and 15"),
    (_questions(max_score="10"), "number 10"),
    (_questions(points=(4, 3, 2)), "expected exactly 10"),
])
def test_writer_shape_the_team_schema_cannot_take_is_refused(payload, needle):
    with pytest.raises(ValueError) as excinfo:
        aiworker._validate_questions(payload)
    assert needle in str(excinfo.value)


def test_writer_may_return_many_questions():
    """The question count is not capped at 3 or 6: up to 15 validate."""
    for count in (3, 6, 10, 15):
        assert len(aiworker._validate_questions(_questions(count=count))) == count


# --------------------------------------------------------------------------
# JSON extraction: the breakage a reasoning model actually produces
# --------------------------------------------------------------------------
def test_extract_json_tolerates_fences_trailing_commas_and_raw_newlines():
    fenced = ('```json\n{"question": "Line one\nstill going", "why": "w",}\n```')
    assert aiworker._extract_json(fenced)["why"] == "w"


def test_extract_json_escapes_unescaped_inner_quotes():
    broken = '{"question": "Tell me about "the incident" you fixed", "why": "w"}'
    payload = aiworker._extract_json(broken)
    assert payload["question"] == 'Tell me about "the incident" you fixed'
    assert payload["why"] == "w"


def test_extract_json_keeps_structural_quotes_and_escapes_intact():
    payload = aiworker._extract_json('{"question": "say \\"hi\\" now", "why": "w"}')
    assert payload == {"question": 'say "hi" now', "why": "w"}
    with pytest.raises(ValueError):
        aiworker._extract_json("no json object at all")


def test_a_slot_is_retried_three_times_before_it_is_given_up(monkeypatch):
    """Three repair turns, like grading: 4 calls for one stubborn slot."""
    calls = {"n": 0}

    def fake(messages, **options):
        if messages[0]["content"] == aiworker.PLANNER_SYSTEM:
            return _completion(_plan_payload(1))
        calls["n"] += 1
        if calls["n"] <= 3:  # three refusals, then the repair lands
            return _completion("not json at all")
        return _completion(_question_payload(calls["n"]))

    monkeypatch.setattr(aiworker, "complete", fake)
    out = aiworker.generate_questions({"title": "x"}, {}, "", [])
    assert calls["n"] == 4  # 1 initial + 3 repairs, slot then succeeds
    assert len(out["questions"]) == 1


def test_a_permanently_broken_slot_is_skipped_not_fatal(monkeypatch):
    """One unusable slot is skipped; the interview still gets the rest."""
    def fake(messages, **options):
        if messages[0]["content"] == aiworker.PLANNER_SYSTEM:
            return _completion(_plan_payload(4))
        about_cv = any("phase: cv" in m["content"] for m in messages
                       if m["role"] == "user")
        if about_cv:
            return _completion("still not json")
        return _completion(_question_payload(len(messages)))

    monkeypatch.setattr(aiworker, "complete", fake)
    out = aiworker.generate_questions({"title": "x"}, {}, "notes", [])
    assert len(out["questions"]) == 3  # the cv slot was skipped, rest kept


def test_generate_questions_can_return_fifteen(monkeypatch):
    state = _router_fake(monkeypatch, plan_total=15)
    out = aiworker.generate_questions({"title": "x"}, {}, "notes", [])
    assert state["slots"] == 15 and len(out["questions"]) == 15


def test_writer_payload_with_overlong_criterion_is_refused():
    payload = _questions()
    payload["questions"][0]["rubric"]["criteria"][0]["good"] = "x" * 1001
    with pytest.raises(ValueError) as excinfo:
        aiworker._validate_questions(payload)
    assert "1000" in str(excinfo.value)


def test_generate_questions_rejects_bad_shape_before_returning(monkeypatch):
    monkeypatch.setattr(aiworker, "complete",
                        lambda m, **o: _completion(_questions(count=7)))
    with pytest.raises(ValueError):
        aiworker.generate_questions({"title": "x"}, {}, "", [])


# --------------------------------------------------------------------------
# Prompt content the guarantees rely on
# --------------------------------------------------------------------------
def test_grader_prompt_demands_verbatim_citation_and_no_fabrication():
    system = aiworker.EVIDENCE_SYSTEM
    assert "ONLY a JSON object" in system
    assert "character-for-character" in system
    assert "Never invent" in system
    # Unwrapped-in-a-needle check: the prompt must ask for inline quoting.
    assert "double quotes" in system
    # HM2: the calibration table pins the strong band below 9 and the generic
    # band to the middle, so a correct-but-generic answer cannot be a 9.
    assert "9.0-10.0" in system
    assert "7.0-8.5" in system
    assert "5.5-6.5" in system
    assert "measured" in system.lower()
    # HM2: anti-refusal rules.
    assert "shortest safe span" in system
    assert 'Never "fix" missing diacritics' in system
    # The Good threshold is exposed to the eval harness and embedded here.
    assert aiworker.GOOD_THRESHOLD == 6.0
    assert f"{aiworker.GOOD_THRESHOLD:g} or above" in system
    # Two worked examples (one strong, one generic).
    assert "WORKED EXAMPLE 1" in system
    assert "WORKED EXAMPLE 2" in system


def test_grader_prompt_requires_english_prose_with_verbatim_quotes():
    """Feedback prose is English, but a quote copied from a Vietnamese answer
    keeps its original language - a translated quote fails the exact gate."""
    system = aiworker.EVIDENCE_SYSTEM
    assert "in ENGLISH" in system
    assert "original language" in system
    assert "translated quote is NOT in the answer" in system
    # The worked examples show English prose over English answers.
    assert "You covered the technology" in system
    # The rejected replies shown to candidates are English too.
    for reason in ("evidence_not_found", "feedback_ungrounded", "bad_score",
                   "no_feedback", "no_evidence", "bad_json"):
        assert aiworker.rejected_reply("q", "a", RUBRIC, reason)["feedback"].isascii()


# The few-shot answer/evidence below are copied out of EVIDENCE_SYSTEM itself,
# so the test fails the moment the prompt's own example stops matching the
# "verbatim span" rule it teaches.
EXAMPLE_1_ANSWER = (
    "I used Redis to cache the product lookup API. During a flash "
    "sale, p99 dropped from 800ms to 120ms and 5xx errors fell by 90%. "
    "After that I added a 5-minute TTL to each key to avoid stale data."
)
EXAMPLE_1_EVIDENCE = [
    "I used Redis to cache the product lookup API",
    "p99 dropped from 800ms to 120ms",
    "I added a 5-minute TTL to each key",
]
EXAMPLE_2_ANSWER = (
    "I usually work in a team very well and always try my best. "
    "I have experience with many projects and learn quickly. I think I am a "
    "good fit for this job."
)
EXAMPLE_2_EVIDENCE = ["I usually work in a team very well"]


def test_grader_few_shot_examples_are_self_consistent():
    """The embedded examples must follow the rule they teach: every evidence
    entry is an exact substring of the example answer, accents included."""
    system = aiworker.EVIDENCE_SYSTEM
    assert EXAMPLE_1_ANSWER in system
    assert EXAMPLE_2_ANSWER in system
    for span in EXAMPLE_1_EVIDENCE:
        assert span in EXAMPLE_1_ANSWER
        assert span in system
    for span in EXAMPLE_2_EVIDENCE:
        assert span in EXAMPLE_2_ANSWER
        assert span in system
    # One strong example scored 8.5, one generic example scored 5.5.
    assert '"score": 8.5' in system
    assert '"score": 5.5' in system


def test_writer_prompt_pins_the_schema_limits():
    system = aiworker.QUESTION_SYSTEM
    assert 'NUMBER 10' in system
    assert "1000 characters" in system
    # The question must talk to the candidate, never cite paperwork.
    assert "NEVER reference documents" in system
    assert '"the job profile"' in system
    # Every slot sees the earlier questions and must not repeat one.
    assert "Do NOT repeat an already-asked question" in system
    # The "why" field still ties the question to a concrete element.
    assert '"why"' in system


def test_planner_prompt_decides_count_seniority_and_arc():
    system = aiworker.PLANNER_SYSTEM
    # The planner - not a fixed count - decides how many questions.
    assert '"total"' in system
    assert "6 to 12" in system
    assert "15 is the hard maximum" in system
    assert '"seniority"' in system
    # The split follows the role, not a template.
    for weight in ("intern/junior", "mid", "senior", "regulated domains",
                   "job description"):
        assert weight in system
    # The arc covers CV/experience/skills plus market reality from research.
    for phase in aiworker.INTERVIEW_PHASES:
        assert f'"{phase}"' in system
    # The default plan satisfies the same validator as a model plan.
    assert aiworker._validate_plan({
        "seniority": "junior", "total": 2,
        "slots": [{"phase": "cv", "focus": "a", "difficulty": "easy"},
                  {"phase": "market", "focus": "b", "difficulty": "hard"}]})["total"] == 2
    with pytest.raises(ValueError):
        aiworker._validate_plan({"seniority": "wizard", "total": 4, "slots": []})


def test_default_plan_is_a_full_arc():
    plan = aiworker.DEFAULT_PLAN
    assert plan["total"] == len(plan["slots"]) >= 6
    assert plan["slots"][0]["phase"] == "starter"
    assert sum(s["phase"] == "starter" for s in plan["slots"]) == 1


def test_questions_may_not_reference_documents_or_repeat_themselves():
    pool = set()  # grounding is covered elsewhere
    item = _question_payload(1)
    item["question"] = "The job profile requires FastAPI experience - tell me about it."
    with pytest.raises(ValueError, match="reference documents"):
        aiworker._validate_question(item, pool=pool, label="question 1")
    repeat = _question_payload(2)
    with pytest.raises(ValueError, match="repeats"):
        aiworker._validate_question(repeat, pool=pool,
                                    previous=[_question_payload(2)])
    assert aiworker._validate_question(_question_payload(3), pool=pool)["question"] == "Q3?"
