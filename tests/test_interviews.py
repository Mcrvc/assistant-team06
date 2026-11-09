from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from assistant.interview_ai import MockInterviewAI
from assistant.interview_schemas import (
    CreateInterview, FinalizeInterview, InterviewView, SaveProgress, SubmitAnswer,
)
from assistant.interview_store import SQLAlchemyInterviewRepository, StoreConflict
from assistant.interviews import InterviewError, InterviewService, progress, public_view

OWNER = "user-a"
ANSWER = "I built an API with my team, wrote tests, fixed a data issue and measured the result."


@pytest.fixture
def store(tmp_path):
    repository = SQLAlchemyInterviewRepository.local(tmp_path / "interviews.sqlite")
    yield repository
    repository.close()


@pytest.fixture
def service(store):
    return InterviewService(store)


def create(service, owner=OWNER):
    return service.create(owner, CreateInterview.model_validate({
        "job_profile": {"title": "Backend intern", "company": "Example"},
        "cv": "I study Python.",
    }))


def submit(service, item, index, text=ANSWER):
    item, grading_id = service.submit_answer(OWNER, item["id"], index,
        SubmitAnswer(revision=item["revision"], text=text))
    return item, grading_id


def test_create_snapshots_job_cv_questions_criteria_and_source(service):
    item = create(service)
    assert len(item["questions"]) == 3
    assert all(q["source_type"] == "open" and q["criteria"] for q in item["questions"])
    assert item["job_profile"]["title"] == "Backend intern"
    assert item["cv"] == "I study Python."
    assert item["question_generation"] == {"model": "local-mock", "used_fallback": True}
    assert progress(item) == {"total": 3, "answered": 0, "graded": 0, "pending": 0, "rejected": 0}
    InterviewView.model_validate(public_view(item))


def test_interrupt_survives_new_repository_and_resume(tmp_path):
    path = tmp_path / "restart.sqlite"
    repo = SQLAlchemyInterviewRepository.local(path)
    first = InterviewService(repo)
    item = create(first)
    first.save_progress(OWNER, item["id"], SaveProgress(
        revision=0, answers=[ANSWER, "unfinished draft", ""], current_question=1, status="interrupted"))
    repo.close()
    reopened = SQLAlchemyInterviewRepository.local(path)
    try:
        next_service = InterviewService(reopened)
        saved = next_service.get(OWNER, item["id"])
        assert saved["answers"][0]["text"] == ANSWER
        assert saved["current_question"] == 1
        assert saved["status"] == "interrupted"
        resumed = next_service.save_progress(OWNER, item["id"], SaveProgress(
            revision=1, current_question=1, status="in_progress"))
        assert resumed["answers"][1]["text"] == "unfinished draft"
    finally:
        reopened.close()


def test_owner_cannot_read_edit_submit_or_finalize_another_users_interview(service):
    item = create(service)
    operations = [
        lambda: service.get("user-b", item["id"]),
        lambda: service.save_progress("user-b", item["id"], SaveProgress(revision=0, current_question=0)),
        lambda: service.submit_answer("user-b", item["id"], 0, SubmitAnswer(revision=0, text=ANSWER)),
        lambda: service.finalize("user-b", item["id"], FinalizeInterview(revision=0)),
    ]
    for operation in operations:
        with pytest.raises(InterviewError) as exc:
            operation()
        assert exc.value.status == 404


def test_stale_save_does_not_overwrite_newer_answers(service):
    item = create(service)
    service.save_progress(OWNER, item["id"], SaveProgress(
        revision=0, answers=[ANSWER, "", ""], current_question=0))
    with pytest.raises(InterviewError, match="reload") as exc:
        service.save_progress(OWNER, item["id"], SaveProgress(
            revision=0, answers=["stale text", "", ""], current_question=0))
    assert exc.value.status == 409
    assert service.get(OWNER, item["id"])["answers"][0]["text"] == ANSWER


def test_atomic_store_update_rejects_stale_internal_version(store, service):
    item = create(service)
    other = store.get(item["id"], OWNER)
    item["version"] = 1
    store.save(item, 0)
    other["version"] = 1
    with pytest.raises(StoreConflict):
        store.save(other, 0)


def test_pending_answer_is_stored_before_grading_and_can_retry_after_restart(service, store):
    item, old_job = submit(service, create(service), 0)
    assert store.get(item["id"], OWNER)["answers"][0]["grading_status"] == "pending"
    restarted = InterviewService(store)
    item, new_job = submit(restarted, restarted.get(OWNER, item["id"]), 0)
    restarted.grade_answer(OWNER, item["id"], 0, old_job)
    assert restarted.get(OWNER, item["id"])["answers"][0]["grading_status"] == "pending"
    restarted.grade_answer(OWNER, item["id"], 0, new_job)
    assert restarted.get(OWNER, item["id"])["answers"][0]["grading_status"] == "graded"


def test_finalize_requires_answers_then_completed_grading(service):
    item = create(service)
    with pytest.raises(InterviewError) as exc:
        service.finalize(OWNER, item["id"], FinalizeInterview(revision=0))
    assert exc.value.code == "answers_required"
    for index in range(3):
        item, _ = submit(service, item, index)
    with pytest.raises(InterviewError) as exc:
        service.finalize(OWNER, item["id"], FinalizeInterview(revision=item["revision"]))
    assert exc.value.code == "grading_incomplete"


def test_complete_report_and_idempotent_finalize_with_no_ai_recall(store):
    class CountingAI(MockInterviewAI):
        calls = 0
        def grade_answer(self, *args):
            self.calls += 1
            return super().grade_answer(*args)
    provider = CountingAI()
    service = InterviewService(store, provider)
    item = create(service)
    for index in range(3):
        item, job = submit(service, item, index)
        service.grade_answer(OWNER, item["id"], index, job)
    result = service.finalize(OWNER, item["id"], FinalizeInterview(revision=item["revision"], name="Practice"))
    assert result["status"] == "finalized"
    assert len(result["report"]["items"]) == 3
    assert result["report"]["used_fallback"] is True
    assert result["report"]["overall_score"] == 6
    InterviewView.model_validate(public_view(result))
    again = service.finalize(OWNER, item["id"], FinalizeInterview(revision=item["revision"]))
    assert again["report"] == result["report"] and provider.calls == 3
    with pytest.raises(InterviewError) as exc:
        submit(service, again, 0, "Different answer")
    assert exc.value.code == "already_finalized"


@pytest.mark.parametrize("failure", ["exception", "malformed", "nan"])
def test_provider_failures_use_labeled_fallback(store, failure):
    class BrokenAI:
        def generate_questions(self, *args):
            if failure == "exception":
                raise TimeoutError("private provider details")
            return {"questions": []}
        def grade_answer(self, *args):
            if failure == "exception":
                raise TimeoutError("private provider details")
            if failure == "nan":
                return {"score": float("nan"), "feedback": "x", "evidence": ["x"],
                        "model": "broken", "used_fallback": False}
            return {"score": "invalid"}
    service = InterviewService(store, BrokenAI())
    item, job = submit(service, create(service), 0)
    service.grade_answer(OWNER, item["id"], 0, job)
    saved = service.get(OWNER, item["id"])
    assert saved["question_generation"]["used_fallback"] is True
    assert saved["answers"][0]["grade"]["model"] == "local-mock"


@pytest.mark.parametrize("quote", ["I managed a million-dollar project.", "   ", "i built an api"])
def test_fabricated_blank_or_normalized_evidence_is_rejected(store, quote):
    class FabricatingAI(MockInterviewAI):
        def grade_answer(self, *args):
            return {"score": 9.0, "feedback": "Great", "evidence": [quote],
                    "model": "test-provider", "used_fallback": False}
    service = InterviewService(store, FabricatingAI())
    item, job = submit(service, create(service), 0)
    service.grade_answer(OWNER, item["id"], 0, job)
    saved = service.get(OWNER, item["id"])["answers"][0]
    assert saved["grading_status"] == "rejected"
    assert saved["grade"] is None and saved["error_code"] == "evidence_not_found"


def test_old_inflight_grade_cannot_overwrite_edited_answer(store):
    entered, release = threading.Event(), threading.Event()
    class SlowAI(MockInterviewAI):
        def grade_answer(self, *args):
            entered.set()
            assert release.wait(5)
            return super().grade_answer(*args)
    service = InterviewService(store, SlowAI())
    item, job = submit(service, create(service), 0)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(service.grade_answer, OWNER, item["id"], 0, job)
        try:
            assert entered.wait(5)
            service.save_progress(OWNER, item["id"], SaveProgress(
                revision=item["revision"], current_question=0, answers=["Edited draft", "", ""]))
        finally:
            release.set()
        future.result(timeout=5)
    saved = service.get(OWNER, item["id"])["answers"][0]
    assert saved["text"] == "Edited draft" and saved["grade"] is None
    assert saved["grading_status"] == "draft"


def test_concurrent_grades_merge_without_lost_results_or_client_revision_changes(store):
    barrier = threading.Barrier(2)
    class ConcurrentAI(MockInterviewAI):
        def grade_answer(self, *args):
            barrier.wait(timeout=5)
            return super().grade_answer(*args)
    service = InterviewService(store, ConcurrentAI())
    item, job0 = submit(service, create(service), 0)
    item, job1 = submit(service, item, 1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(service.grade_answer, OWNER, item["id"], i, job)
                   for i, job in enumerate([job0, job1])]
        for future in futures:
            future.result(timeout=10)
    saved = service.get(OWNER, item["id"])
    assert progress(saved)["graded"] == 2
    assert saved["revision"] == 2
    # User can still submit the next answer with the revision from their last edit.
    submit(service, saved, 2)


def test_valid_provider_reference_and_real_grade_metadata_are_preserved(store):
    class ReferencedAI(MockInterviewAI):
        def generate_questions(self, *args):
            result = super().generate_questions(*args)
            result.update(model="test-provider", used_fallback=False)
            result["questions"][0].update(source_type="reference", reference={
                "title": "Team question bank", "locator": "bank:python-1", "excerpt": "API testing criteria",
            })
            return result
        def grade_answer(self, *args):
            return {"score": 7.5, "feedback": "A clear example.", "evidence": ["wrote tests"],
                    "model": "test-provider", "used_fallback": False}
    service = InterviewService(store, ReferencedAI())
    item = create(service)
    for index in range(3):
        item, job = submit(service, item, index)
        service.grade_answer(OWNER, item["id"], index, job)
    result = service.finalize(OWNER, item["id"], FinalizeInterview(revision=item["revision"]))
    assert result["questions"][0]["reference"]["locator"] == "bank:python-1"
    assert result["report"]["overall_score"] == 7.5
    assert result["report"]["used_fallback"] is False


def test_fallback_evidence_handles_leading_whitespace_and_unicode(service):
    text = " " * 150 + "Tôi đã viết API và kiểm thử cùng nhóm."
    item, job = submit(service, create(service), 0, text)
    service.grade_answer(OWNER, item["id"], 0, job)
    answer = service.get(OWNER, item["id"])["answers"][0]
    assert answer["grading_status"] == "graded"
    assert all(quote in text and quote.strip() for quote in answer["grade"]["evidence"])
