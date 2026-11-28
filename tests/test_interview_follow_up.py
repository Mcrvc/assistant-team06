from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from assistant import interview_follow_up
from assistant.interview_ai import MockInterviewAI
from assistant.interview_schemas import CreateInterview, SubmitAnswer, StartFollowUp, FollowUpAction, FollowUpAnswer, SaveProgress, FinalizeInterview
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewService, InterviewError
from assistant.web import create_app

ANSWER = "I improved load times by 40% by adding a database index."

@pytest.fixture
def setup(tmp_path, monkeypatch):
    store = SQLAlchemyInterviewRepository.local(tmp_path / "follow.sqlite")
    service = InterviewService(store, MockInterviewAI())
    monkeypatch.setattr(interview_follow_up, "generate", lambda *args: {"quote": "40%", "question": "How did you measure 40%?"})
    item = service.create("owner", CreateInterview(job_profile={"title": "Intern"}))
    item, job = service.submit_answer("owner", item["id"], 0, SubmitAnswer(revision=0, text=ANSWER))
    service.grade_answer("owner", item["id"], 0, job)
    yield service, service.get("owner", item["id"])
    store.close()

def start(service, item):
    return service.start_follow_up("owner", item["id"], StartFollowUp(revision=item["revision"], parent_grading_id=item["answers"][0]["grading_id"]))

def test_lifecycle_restart_report_and_retry(setup):
    service, item = setup
    state, job = start(service, item)
    replay, duplicate = start(service, item)
    assert duplicate is None and replay == state
    service.generate_follow_up("owner", item["id"], job)
    state = service.get("owner", item["id"])
    assert state["follow_up"]["status"] == "ready"
    request = FollowUpAnswer(revision=state["revision"], request_id=job, text="I compared ten requests before and after the change.")
    state = service.finish_follow_up("owner", item["id"], request)
    assert service.finish_follow_up("owner", item["id"], request) == state
    reopened = InterviewService(service.repository, MockInterviewAI()).get("owner", item["id"])
    assert reopened == state
    final = service.finalize("owner", item["id"], FinalizeInterview(revision=state["revision"]))
    assert final["report"]["follow_up"]["answer"] == request.text
    assert final["report"]["overall_score"] == 3.0
    assert len(final["report"]["items"]) == 3

@pytest.mark.parametrize("action", ["skip", "edit", "resubmit", "finalize"])
def test_late_result_cannot_overwrite_new_intent(setup, action):
    service, item = setup
    state, job = start(service, item)
    if action == "skip":
        service.finish_follow_up("owner", item["id"], FollowUpAction(revision=state["revision"], request_id=job), skip=True)
    elif action == "edit":
        service.save_progress("owner", item["id"], SaveProgress(revision=state["revision"], current_question=0, answers=["New draft"]))
    elif action == "resubmit":
        service.submit_answer("owner", item["id"], 0, SubmitAnswer(revision=state["revision"], text="New answer"))
    else:
        service.finalize("owner", item["id"], FinalizeInterview(revision=state["revision"]))
    before = service.get("owner", item["id"])
    service.generate_follow_up("owner", item["id"], job)
    assert service.get("owner", item["id"]) == before

def test_failure_and_expired_work_can_retry(setup, monkeypatch):
    service, item = setup
    state, job = start(service, item)
    monkeypatch.setattr(interview_follow_up, "generate", lambda *args: (_ for _ in ()).throw(TimeoutError()))
    service.generate_follow_up("owner", item["id"], job)
    state = service.get("owner", item["id"])
    assert state["follow_up"]["status"] == "unavailable"
    state, retry = start(service, state)
    assert retry and retry != job
    state["follow_up"]["started_at"] = "2000-01-01T00:00:00+00:00"
    service.repository.save(state, state["version"])
    state = service.get("owner", item["id"])
    assert state["follow_up"]["status"] == "unavailable"

def test_api_owner_validation_and_old_data(setup):
    service, item = setup
    path = "/api/interviews/" + item["id"]
    assert item.get("follow_up") is None
    with TestClient(create_app(service=service, auth_resolver=lambda request: request.headers.get("x-owner", "owner"))) as client:
        assert client.get(path).json()["follow_up"] is None
        body = {"revision": item["revision"], "parent_grading_id": item["answers"][0]["grading_id"]}
        assert client.post(path + "/follow-up", json=body, headers={"x-owner": "other"}).status_code == 404
        assert client.post(path + "/follow-up", json=body).status_code == 202
        ready = client.get(path).json()
        assert ready["follow_up"]["status"] == "ready"
        body = {"revision": ready["revision"], "request_id": ready["follow_up"]["request_id"], "text": "   "}
        assert client.post(path + "/follow-up/answer", json=body).status_code == 400
        body["text"] = "Ten measurements."
        assert client.post(path + "/follow-up/answer", json=body).status_code == 200

@pytest.mark.parametrize("payload", ['null', '{"quote":"invented","question":"How?"}', '{"quote":"40%","question":""}'])
def test_provider_refuses_invalid_or_invented_quotes(monkeypatch, payload):
    monkeypatch.setattr(interview_follow_up, "complete", lambda *args, **kwargs: SimpleNamespace(text=payload))
    with pytest.raises(ValueError):
        interview_follow_up.generate("What did you do?", ANSWER)

def test_provider_uses_actual_answer(monkeypatch):
    calls = []
    def complete(messages, **kwargs):
        calls.append(messages)
        return SimpleNamespace(text='{"quote":"40%","question":"How did you measure that?"}')
    monkeypatch.setattr(interview_follow_up, "complete", complete)
    assert interview_follow_up.generate("What did you do?", ANSWER)["quote"] == "40%"
    assert ANSWER in calls[0][1]["content"]


def test_result_arriving_after_skip_is_ignored(setup, monkeypatch):
    service, item = setup
    state, job = start(service, item)
    def generate(*args):
        service.finish_follow_up("owner", item["id"], FollowUpAction(revision=state["revision"], request_id=job), skip=True)
        return {"quote": "40%", "question": "How did you measure it?"}
    monkeypatch.setattr(interview_follow_up, "generate", generate)
    service.generate_follow_up("owner", item["id"], job)
    saved = service.get("owner", item["id"])["follow_up"]
    assert saved["status"] == "skipped" and saved["question"] == ""


def test_answer_with_stale_revision_preserves_saved_state(setup):
    service, item = setup
    state, job = start(service, item)
    service.generate_follow_up("owner", item["id"], job)
    before = service.get("owner", item["id"])
    with pytest.raises(InterviewError) as error:
        service.finish_follow_up("owner", item["id"], FollowUpAnswer(revision=0, request_id=job, text="My draft"))
    assert error.value.code == "revision_conflict"
    assert service.get("owner", item["id"]) == before
