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
    state, job = service.start_follow_up("owner", item["id"], StartFollowUp(revision=item["revision"], parent_grading_id=item["answers"][0]["grading_id"]))
    return state, job or state["follow_up"]["request_id"]

def test_lifecycle_restart_report_and_retry(setup):
    service, item = setup
    state, job = start(service, item)
    replay, duplicate = service.start_follow_up("owner", item["id"], StartFollowUp(revision=item["revision"], parent_grading_id=item["answers"][0]["grading_id"]))
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
    item.pop("follow_up", None)
    item.pop("follow_ups", None)
    service.repository.save(item, item["version"])
    with TestClient(create_app(service=service, auth_resolver=lambda request: request.headers.get("x-owner", "owner"))) as client:
        assert client.get(path).json()["follow_up"] is None
        body = {"revision": item["revision"], "parent_grading_id": item["answers"][0]["grading_id"]}
        assert client.post(path + "/follow-up", json=body, headers={"x-owner": "other"}).status_code == 404
        assert client.post(path + "/follow-up", json=body).status_code == 202
        state = client.get(path).json()
        service.generate_follow_up("owner", item["id"], state["follow_up"]["request_id"])
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
        interview_follow_up.generate({"text": "What did you do?", "criteria": ["Verified outcome"]}, ANSWER, [])

def coverage(status="missing", index=0, gap="result_evidence_missing", evidence=None):
    return {"criterion_index": index, "checks": [{"gap": gap, "status": status,
            "evidence": evidence if evidence is not None else ["40%"],
            "missing_information": "How the result was measured"}]}


def test_provider_uses_actual_answer_and_independent_coverage(monkeypatch):
    import json
    calls = []
    def complete(messages, **kwargs):
        calls.append(messages)
        payload = {"coverage": [coverage()]}
        if len(calls) == 2:
            payload["questions"] = [{"criterion_index": 0, "gap": "result_evidence_missing", "question": "How did you measure that?"}]
        return SimpleNamespace(text=json.dumps(payload))
    monkeypatch.setattr(interview_follow_up, "complete", complete)
    result = interview_follow_up.generate({"text": "What did you do?", "criteria": ["Verified outcome"]}, ANSWER, [])
    assert result["quote"] == "40%"
    assert len(calls) == 2
    second_input = json.loads(calls[1][1]["content"])
    assert second_input["answer"] == ANSWER
    assert second_input["candidate_keys"] == [{"criterion_index": 0, "gap": "result_evidence_missing"}]
    assert "proposal" not in second_input and "missing_information" not in second_input


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


@pytest.mark.parametrize("status", ["present", "uncertain"])
def test_second_reader_can_find_information_elsewhere(monkeypatch, status):
    replies = iter([
        {"coverage": [coverage()]},
        {"coverage": [coverage(status=status)], "questions": []},
    ])
    monkeypatch.setattr(interview_follow_up, "_json_reply", lambda messages: next(replies))
    assert interview_follow_up.generate({"text": "What did you do?", "criteria": ["Verified outcome"]}, ANSWER, []) is None


def test_covered_answer_uses_only_one_call(monkeypatch):
    calls = []
    def reply(messages):
        calls.append(messages)
        return {"coverage": [coverage(status="present")]}
    monkeypatch.setattr(interview_follow_up, "_json_reply", reply)
    assert interview_follow_up.generate({"text": "What did you do?", "criteria": ["Verified outcome"]}, ANSWER, []) is None
    assert len(calls) == 1


@pytest.mark.parametrize("bad", [
    {"criterion_index": 10}, {"criterion_index": True},
    {"checks": [{"gap": "low_score", "status": "missing", "evidence": ["40%"]}]},
    {"checks": [{"gap": "result_evidence_missing", "status": "missing", "evidence": ["invented"], "missing_information": "How measured"}]},
    {"checks": [{"gap": "result_evidence_missing", "status": "present", "evidence": []}]},
])
def test_coverage_must_match_criterion_and_real_evidence(monkeypatch, bad):
    monkeypatch.setattr(interview_follow_up, "_json_reply", lambda messages: {"coverage": [{**coverage(), **bad}]})
    with pytest.raises(ValueError):
        interview_follow_up.generate({"text": "What did you do?", "criteria": ["Verified outcome"]}, ANSWER, [])


def test_all_criteria_are_considered_before_selecting(monkeypatch):
    first = [coverage(status="present", gap="personal_action_missing"), coverage(index=1)]
    second = {"coverage": first, "questions": [{"criterion_index": 1, "gap": "result_evidence_missing", "question": "How did you measure it?"}]}
    replies = iter([{"coverage": first}, second])
    monkeypatch.setattr(interview_follow_up, "_json_reply", lambda messages: next(replies))
    result = interview_follow_up.generate({"text": "What did you do?", "criteria": ["Personal actions", "Verified outcome"]}, ANSWER, [])
    assert result["criterion_index"] == 1


def test_second_reader_cannot_reopen_a_covered_criterion(monkeypatch):
    first = [coverage(status="present", gap="personal_action_missing"), coverage(index=1)]
    second = {"coverage": [coverage(gap="personal_action_missing"), coverage(index=1)],
              "questions": [{"criterion_index": 0, "gap": "personal_action_missing", "question": "What did you do?"}]}
    replies = iter([{"coverage": first}, second])
    monkeypatch.setattr(interview_follow_up, "_json_reply", lambda messages: next(replies))
    with pytest.raises(ValueError):
        interview_follow_up.generate({"text": "What did you do?", "criteria": ["Personal actions", "Verified outcome"]}, ANSWER, [])


def test_omitted_criterion_fails_closed(monkeypatch):
    monkeypatch.setattr(interview_follow_up, "_json_reply", lambda messages: {"coverage": [coverage()]})
    with pytest.raises(ValueError):
        interview_follow_up.generate({"text": "What did you do?", "criteria": ["Personal actions", "Verified outcome"]}, ANSWER, [])


def test_duplicate_empty_criterion_entries_do_not_discard_valid_coverage():
    payload = {"coverage": [coverage(), {"criterion_index": 0, "checks": []}]}
    parsed = interview_follow_up._coverage(payload, ["Verified outcome"], ANSWER)
    assert parsed[0, "result_evidence_missing"]["status"] == "missing"


def test_conflicting_duplicate_findings_are_uncertain():
    payload = {"coverage": [coverage(), coverage(status="present")]}
    parsed = interview_follow_up._coverage(payload, ["Verified outcome"], ANSWER)
    assert parsed[0, "result_evidence_missing"]["status"] == "uncertain"


def test_two_question_budget_and_required_answer(setup):
    service, item = setup
    for index in range(3):
        current = service.get("owner", item["id"])
        if index:
            current, grading_id = service.submit_answer("owner", item["id"], index, SubmitAnswer(revision=current["revision"], text=ANSWER))
            service.grade_answer("owner", item["id"], index, grading_id)
        follow = current["follow_up"]
        service.generate_follow_up("owner", item["id"], follow["request_id"])
        current = service.get("owner", item["id"])
        follow = current["follow_up"]
        if index < 2:
            assert follow["status"] == "ready"
            with pytest.raises(InterviewError) as error:
                service.finalize("owner", item["id"], FinalizeInterview(revision=current["revision"]))
            assert error.value.code == "follow_up_required"
            with pytest.raises(InterviewError):
                service.submit_answer("owner", item["id"], index + 1, SubmitAnswer(revision=current["revision"], text=ANSWER))
            with pytest.raises(InterviewError):
                service.finish_follow_up("owner", item["id"], FollowUpAction(revision=current["revision"], request_id=follow["request_id"]), skip=True)
            service.finish_follow_up("owner", item["id"], FollowUpAnswer(revision=current["revision"], request_id=follow["request_id"], text="Ten measurements before and after."))
        else:
            assert follow["status"] == "not_needed"
    final = service.finalize("owner", item["id"], FinalizeInterview(revision=current["revision"]))
    assert len(final["report"]["follow_ups"]) == 2
    assert len(final["report"]["items"]) == 3


def test_editing_an_already_selected_question_does_not_ask_it_again(setup):
    service, item = setup
    follow = item["follow_up"]
    service.generate_follow_up("owner", item["id"], follow["request_id"])
    current = service.get("owner", item["id"])
    current, _ = service.submit_answer("owner", item["id"], 0,
                                      SubmitAnswer(revision=current["revision"], text="A different answer"))
    assert current["follow_up"]["status"] == "not_needed"
    assert current["follow_ups"][0]["status"] == "invalidated"
