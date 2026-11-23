"""Tests for the opt-in question bank reader (no network, no real project)."""
import json
from urllib.error import URLError

import pytest

from assistant.interview_schemas import CreateInterview, Question
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewService
from assistant.question_bank import (
    QuestionBankError, SupabaseQuestionBank, bank_count, bank_domain, bank_enabled, draw_questions,
)

URL = "https://project.supabase.co"
SECRET = "sb_secret_test_key"


def rubric_row(points=4, good="Shows a concrete result"):
    return {"name": "impact", "points": points, "good": good}


def bank_row(index=1, points=4):
    return {
        "id": index,
        "question": f"Describe project {index} and what you measured.",
        "category": "backend",
        "rubrics": [rubric_row(points, f"Shows a concrete result {index}")],
    }


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def read(self, limit=None):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def bank_with_payload(monkeypatch, payload):
    bank = SupabaseQuestionBank(URL, SECRET)
    monkeypatch.setattr(bank, "_fetch", lambda count: payload)
    return bank


def test_bank_is_off_by_default_and_needs_an_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("INTERVIEW_QUESTION_BANK", raising=False)
    assert bank_enabled() is False
    for value in ("1", "on", "true", "AUTO", " True "):
        monkeypatch.setenv("INTERVIEW_QUESTION_BANK", value)
        assert bank_enabled() is True
    for value in ("0", "off", "false", ""):
        monkeypatch.setenv("INTERVIEW_QUESTION_BANK", value)
        assert bank_enabled() is False


def test_domain_and_count_come_from_the_environment(monkeypatch):
    monkeypatch.delenv("INTERVIEW_BANK_DOMAIN", raising=False)
    monkeypatch.delenv("INTERVIEW_BANK_LIMIT", raising=False)
    assert bank_domain() == "information_technology"
    assert bank_count() == 3
    monkeypatch.setenv("INTERVIEW_BANK_DOMAIN", " finance ")
    monkeypatch.setenv("INTERVIEW_BANK_LIMIT", "99")
    assert bank_domain() == "finance"
    assert bank_count() == 10
    monkeypatch.setenv("INTERVIEW_BANK_LIMIT", "not-a-number")
    assert bank_count() == 3


def test_bank_rejects_an_untrusted_origin_and_a_publishable_key():
    with pytest.raises(QuestionBankError):
        SupabaseQuestionBank("http://project.supabase.co", SECRET)
    with pytest.raises(QuestionBankError):
        SupabaseQuestionBank("https://user:pw@project.supabase.co", SECRET)
    with pytest.raises(QuestionBankError):
        SupabaseQuestionBank("https://project.supabase.co", "sb_publishable_abc")
    with pytest.raises(QuestionBankError):
        SupabaseQuestionBank("https://project.supabase.co", "fake_secret")


def test_draw_maps_bank_rows_into_valid_questions(monkeypatch):
    bank = bank_with_payload(monkeypatch, [bank_row(1), bank_row(2), bank_row(3)])
    questions = bank.draw({"title": "Backend intern"}, 3)
    assert questions is not None and len(questions) == 3
    for question in questions:
        Question.model_validate(question)
        assert question["source_type"] == "open" and question["reference"] is None
        assert question["rubric"]["max_score"] == 10
        assert sum(c["points"] for c in question["rubric"]["criteria"]) == 10


def test_draw_scales_rubric_points_to_exactly_ten(monkeypatch):
    rows = [bank_row(1, points=3), bank_row(2, points=3), bank_row(3, points=2)]
    questions = bank_with_payload(monkeypatch, rows).draw({"title": "Intern"}, 3)
    assert questions is not None
    for question in questions:
        points = [c["points"] for c in question["rubric"]["criteria"]]
        assert sum(points) == 10
        assert all(value > 0 for value in points)


def test_draw_returns_none_when_the_bank_cannot_supply_the_count(monkeypatch):
    assert bank_with_payload(monkeypatch, []).draw({}, 3) is None
    assert bank_with_payload(monkeypatch, [bank_row(1)]).draw({}, 3) is None
    # A row without usable text or rubric is skipped, not guessed.
    assert bank_with_payload(monkeypatch, [{"question": "   ", "rubrics": [rubric_row()]}]
                             ).draw({}, 3) is None
    assert bank_with_payload(monkeypatch, [{"question": "No rubric here"}]).draw({}, 3) is None
    assert bank_with_payload(monkeypatch, [bank_row(1), bank_row(2), bank_row(3)]
                             ).draw({}, 5) is None


def test_fetch_swallows_network_errors(monkeypatch):
    bank = SupabaseQuestionBank(URL, SECRET)

    def offline(request, timeout=None):
        raise URLError("offline")

    monkeypatch.setattr(bank._opener, "open", offline)
    assert bank._fetch(3) is None
    assert bank.draw({}, 3) is None


def test_fetch_reads_a_json_list_and_rejects_anything_else(monkeypatch):
    bank = SupabaseQuestionBank(URL, SECRET)
    monkeypatch.setattr(bank._opener, "open", lambda request, timeout=None: FakeResponse([bank_row(1)]))
    assert bank._fetch(3) == [bank_row(1)]
    monkeypatch.setattr(bank._opener, "open", lambda request, timeout=None: FakeResponse({"error": "nope"}))
    assert bank._fetch(3) is None
    monkeypatch.setattr(bank._opener, "open", lambda request, timeout=None: FakeResponse(b"not json"))
    assert bank._fetch(3) is None


def test_draw_questions_stays_off_without_the_opt_in(monkeypatch):
    monkeypatch.setenv("INTERVIEW_QUESTION_BANK", "0")
    assert draw_questions({"title": "Intern"}) is None


def test_draw_questions_returns_none_when_supabase_is_not_configured(monkeypatch):
    monkeypatch.setenv("INTERVIEW_QUESTION_BANK", "1")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "")
    assert draw_questions({"title": "Intern"}) is None


def test_draw_questions_uses_the_configured_project(monkeypatch):
    monkeypatch.setenv("INTERVIEW_QUESTION_BANK", "1")
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    monkeypatch.setattr("assistant.question_bank.SupabaseQuestionBank.draw",
                        lambda self, job_profile, count: [bank_row(1), bank_row(2), bank_row(3)])
    questions = draw_questions({"title": "Intern"})
    assert questions is not None and len(questions) == 3


def bank_questions():
    return [Question.model_validate({
        "text": f"Bank question {index}", "source_type": "open", "reference": None,
        "criteria": ["Shows a concrete result"], "rubric": {"max_score": 10, "criteria": [
            {"name": "impact", "points": 10, "good": "Shows a concrete result"}]}}
    ).model_dump() for index in range(1, 4)]


def create_interview(tmp_path, monkeypatch, payload):
    monkeypatch.setattr("assistant.question_bank.draw_questions", lambda job_profile: payload)
    repo = SQLAlchemyInterviewRepository.local(tmp_path / "bank.sqlite")
    try:
        service = InterviewService(repo)
        return service.create("user-a", CreateInterview.model_validate({
            "job_profile": {"title": "Backend intern"}, "cv": "I study Python."}))
    finally:
        repo.close()


def test_interview_uses_the_bank_questions_when_the_bank_answers(tmp_path, monkeypatch):
    item = create_interview(tmp_path, monkeypatch, bank_questions())
    assert item["question_generation"] == {"model": "question-bank", "used_fallback": False}
    assert item["questions"][0]["text"] == "Bank question 1"
    assert item["questions"][0]["rubric"]["max_score"] == 10


def test_interview_generates_when_the_bank_is_empty_or_broken(tmp_path, monkeypatch):
    for payload in (None, [], [bank_questions()[0]], "not a list"):
        item = create_interview(tmp_path, monkeypatch, payload)
        assert item["question_generation"] == {"model": "local-mock", "used_fallback": True}
        assert len(item["questions"]) == 3


def test_interview_generates_when_the_bank_raises(tmp_path, monkeypatch):
    def broken(job_profile):
        raise RuntimeError("bank unavailable")

    monkeypatch.setattr("assistant.question_bank.draw_questions", broken)
    repo = SQLAlchemyInterviewRepository.local(tmp_path / "broken.sqlite")
    try:
        service = InterviewService(repo)
        item = service.create("user-a", CreateInterview.model_validate({
            "job_profile": {"title": "Backend intern"}}))
        assert item["question_generation"] == {"model": "local-mock", "used_fallback": True}
    finally:
        repo.close()