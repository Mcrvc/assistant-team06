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
def test_generate_questions_accepts_and_forwards_timeout(monkeypatch):
    seen = {}

    def fake_complete(messages, **options):
        seen.update(options)
        return _completion({"questions": [
            {"question": f"Q{i}?", "category": "technical", "why": "w",
             "rubric": {"max_score": 10, "criteria": [
                 {"name": "a", "points": 5, "good": "g"},
                 {"name": "b", "points": 5, "good": "g"}]}}
            for i in range(3)]})

    monkeypatch.setattr(aiworker, "complete", fake_complete)
    aiworker.generate_questions({"title": "x"}, {}, "", [], timeout_s=9.0)

    assert seen["timeout_s"] == 9.0


def test_generate_questions_returns_source_notes_and_sources(monkeypatch):
    def fake_complete(messages, **options):
        return _completion({"questions": [
            {"question": f"Q{i}?", "category": "behavioral", "why": "w",
             "rubric": {"max_score": 10, "criteria": [
                 {"name": "a", "points": 5, "good": "g"},
                 {"name": "b", "points": 5, "good": "g"}]}}
            for i in range(3)]})
    monkeypatch.setattr(aiworker, "complete", fake_complete)

    out = aiworker.generate_questions({"title": "x"}, {}, "notes here", ["https://a"])
    assert out["source"] == "nvidia"
    assert out["research_notes"] == "notes here"
    assert out["sources"] == ["https://a"]
    assert len(out["questions"]) == 3


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
    assert "nguy\u00ean v\u0103n" in seen["evidence_not_found"]


def test_rejected_reply_messages_are_ascii_safe_for_logs():
    """The reply must survive a JSON round trip and stay readable."""
    import json
    payload = json.dumps(aiworker.rejected_reply("q", "a", RUBRIC),
                         ensure_ascii=False)
    assert "Tr" in json.loads(payload)["feedback"]


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
    (_questions(count=2), "exactly 3"),
    (_questions(count=4), "exactly 3"),
    (_questions(max_score="10"), "number 10"),
    (_questions(points=(4, 3, 2)), "expected exactly 10"),
])
def test_writer_shape_the_team_schema_cannot_take_is_refused(payload, needle):
    with pytest.raises(ValueError) as excinfo:
        aiworker._validate_questions(payload)
    assert needle in str(excinfo.value)


def test_writer_payload_with_overlong_criterion_is_refused():
    payload = _questions()
    payload["questions"][0]["rubric"]["criteria"][0]["good"] = "x" * 1001
    with pytest.raises(ValueError) as excinfo:
        aiworker._validate_questions(payload)
    assert "1000" in str(excinfo.value)


def test_generate_questions_rejects_bad_shape_before_returning(monkeypatch):
    monkeypatch.setattr(aiworker, "complete",
                        lambda m, **o: _completion(_questions(count=2)))
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


def test_writer_prompt_pins_the_schema_limits():
    system = aiworker.WRITER_SYSTEM
    assert "exactly 3 questions" in system
    assert 'NUMBER 10' in system
    assert "1000 characters" in system
