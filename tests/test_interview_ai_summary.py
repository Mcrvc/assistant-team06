from types import SimpleNamespace

import pytest

from assistant.interview_ai import MockInterviewAI, SafeInterviewAI, TeamInterviewAI
from assistant.interview_schemas import CreateInterview, FinalizeInterview, InterviewView, SubmitAnswer
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewService, public_view

OWNER = "user-a"
ANSWER = "I built an API with my team, wrote tests, fixed a data issue and measured the result."

ITEMS = [
    {"question": "Q1?", "score": 8.0, "feedback": "Clear actions and a result."},
    {"question": "Q2?", "score": 4.5, "feedback": "Vague, no example."},
]


def worker(summary=None):
    def summarize(items, **options):
        assert options["timeout_s"] == 9
        return summary if summary is not None else {
            "summary": "Strong on Q1; work on Q2.", "model": "duy-model", "used_fallback": False}
    return SimpleNamespace(
        generate_questions=lambda job, cv, notes, sources, **options: {"source": "nvidia", "questions": [
            {"question": f"Q{i}?", "rubric": {"max_score": 10, "criteria": [
                {"name": "actions", "points": 10, "good": "Explain personal actions"}]}}
            for i in range(3)]},
        grade_answer_with_evidence=lambda *args, **kwargs: {
            "score": 7.5, "feedback": "Clear actions", "evidence": [ANSWER[:20]],
            "model": "duy-model", "used_fallback": False},
        EvidenceRejected=Exception, summarize_interview=summarize)


def test_adapter_forwards_trimmed_items_and_timeout():
    provider = TeamInterviewAI(worker=worker(), model="duy-model", timeout_s=9)
    result = SafeInterviewAI(provider).summarize_interview([ITEMS[0]])
    assert result == {"summary": "Strong on Q1; work on Q2.", "model": "duy-model", "used_fallback": False}


def test_provider_failure_degrades_to_a_deterministic_summary():
    def offline(items, **options):
        raise TimeoutError("private provider details")
    provider = TeamInterviewAI(worker=SimpleNamespace(
        generate_questions=lambda *a, **k: {}, grade_answer_with_evidence=offline,
        EvidenceRejected=Exception, summarize_interview=offline), timeout_s=9)
    result = SafeInterviewAI(provider).summarize_interview(ITEMS)
    assert result["used_fallback"] is True and result["model"] == "local-mock"
    assert "Q1 (8.0/10)" in result["summary"] and "Q2 (4.5/10)" in result["summary"]


def test_malformed_provider_summary_is_replaced_by_the_mock():
    provider = TeamInterviewAI(worker=worker(summary={"summary": "", "model": ""}), timeout_s=9)
    result = SafeInterviewAI(provider).summarize_interview(ITEMS)
    assert result["used_fallback"] is True and result["summary"]
    provider = TeamInterviewAI(worker=worker(summary="not a dict"), timeout_s=9)
    result = SafeInterviewAI(provider).summarize_interview(ITEMS)
    assert result["used_fallback"] is True and result["summary"]


def test_mock_summary_never_leaks_raw_answers_or_secrets():
    items = [{"question": "Q1?", "score": 8.0, "feedback": "Clear actions and a result.",
              "answer": ANSWER, "cv": "secret cv body"}]
    result = MockInterviewAI().summarize_interview(items)
    assert ANSWER not in result["summary"] and "secret" not in result["summary"]
    assert result == MockInterviewAI().summarize_interview(items)


def test_mock_summary_handles_an_unscored_interview():
    result = MockInterviewAI().summarize_interview([{"question": "Q1?", "score": None}])
    assert result["used_fallback"] is True and "No answer was graded" in result["summary"]


def finalized(service):
    item = service.create(OWNER, CreateInterview.model_validate({
        "job_profile": {"title": "Backend intern"}, "cv": "I study Python."}))
    for index in range(3):
        item, grading_id = service.submit_answer(OWNER, item["id"], index,
            SubmitAnswer(revision=item["revision"], text=ANSWER))
        service.grade_answer(OWNER, item["id"], index, grading_id)
    return service.finalize(OWNER, item["id"], FinalizeInterview(revision=item["revision"]))


def test_finalize_stores_one_overall_comment_next_to_the_report(tmp_path):
    repo = SQLAlchemyInterviewRepository.local(tmp_path / "summary.sqlite")
    try:
        service = InterviewService(repo)
        item = finalized(service)
        report = item["report"]
        assert report["overall_comment"] and report["summary_model"] == "local-mock"
        assert report["used_fallback"] is True
        assert ANSWER not in report["overall_comment"]
        InterviewView.model_validate(public_view(item))
        stored = InterviewView.model_validate(public_view(service.get(OWNER, item["id"])))
        assert stored.report.overall_comment == report["overall_comment"]
    finally:
        repo.close()


def test_finalize_keeps_scoring_when_every_summary_provider_fails(tmp_path):
    def offline(items, **options):
        raise TimeoutError("private provider details")

    class NoSummary:
        generate_questions = MockInterviewAI().generate_questions
        grade_answer = MockInterviewAI().grade_answer

        def summarize_interview(self, items):
            raise TimeoutError("private provider details")

    repo = SQLAlchemyInterviewRepository.local(tmp_path / "nosummary.sqlite")
    try:
        service = InterviewService(repo, NoSummary())
        item = finalized(service)
        assert item["report"]["overall_comment"] and item["report"]["overall_score"] is not None
        assert item["report"]["summary_model"] == "local-mock"
    finally:
        repo.close()


def test_real_provider_failure_still_finalizes_with_a_rule_summary(tmp_path):
    class FailingTeam:
        generate_questions = MockInterviewAI().generate_questions
        grade_answer = MockInterviewAI().grade_answer

        def summarize_interview(self, items):
            return {"summary": "ok", "model": "x", "used_fallback": False}

    repo = SQLAlchemyInterviewRepository.local(tmp_path / "teamsafe.sqlite")
    try:
        service = InterviewService(repo, FailingTeam())
        item = finalized(service)
        assert item["report"]["overall_comment"] == "ok"
        assert item["report"]["summary_model"] == "x"
        # The grades came from the mock, so the report stays flagged as mock.
        assert item["report"]["used_fallback"] is True
        assert "offline fallback" not in item["report"]["notice"]
    finally:
        repo.close()