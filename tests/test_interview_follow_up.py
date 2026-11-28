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
    state, grade_job = service.finish_follow_up("owner", item["id"], request)
    assert grade_job and state["answers"][0]["grading_status"] == "pending"
    assert service.finish_follow_up("owner", item["id"], request) == (state, None)
    reopened = InterviewService(service.repository, MockInterviewAI()).get("owner", item["id"])
    assert reopened == state
    with pytest.raises(InterviewError, match="pending grading"):
        service.finalize("owner", item["id"], FinalizeInterview(revision=state["revision"]))
    service.grade_answer("owner", item["id"], 0, grade_job)
    final = service.finalize("owner", item["id"], FinalizeInterview(revision=state["revision"]))
    assert final["report"]["follow_up"]["answer"] == request.text
    assert final["report"]["overall_score"] == 6.0
    assert final["report"]["items"][0]["includes_follow_up"]
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
    monkeypatch.setattr(interview_follow_up, "_request_json", lambda *args, **kwargs: payload)
    with pytest.raises(ValueError):
        interview_follow_up.generate({"text": "What did you do?", "criteria": ["Verified outcome"]}, ANSWER, [])

def coverage(status="missing", index=0, gap="result_evidence_missing", evidence=None):
    quotes = evidence if evidence is not None else ["40%"]
    return {"criterion_index": index, "gap": gap, "status": status,
            "quote": quotes[0] if quotes else "",
            "missing_information": "How the result was measured"}


def test_provider_uses_actual_answer_and_independent_coverage(monkeypatch):
    import json
    calls = []
    def complete(messages, **kwargs):
        calls.append(messages)
        payload = {"coverage": [coverage()], "questions": []}
        if len(calls) == 2:
            payload["questions"] = [{"criterion_index": 0, "gap": "result_evidence_missing", "question": "How did you measure that?"}]
        return json.dumps(payload)
    monkeypatch.setattr(interview_follow_up, "_request_json", complete)
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
    {"criterion_index": 10}, {"criterion_index": True}, {"gap": "low_score"},
    {"quote": "invented"}, {"status": "present", "quote": ""},
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
    payload = {"coverage": [coverage(), {"criterion_index": 0, "gap": None, "status": "not_applicable", "quote": ""}]}
    parsed = interview_follow_up._coverage(payload, ["Verified outcome"], ANSWER)
    assert parsed[0, "result_evidence_missing"]["status"] == "missing"


def test_conflicting_duplicate_findings_are_uncertain():
    payload = {"coverage": [coverage(), coverage(status="present")]}
    parsed = interview_follow_up._coverage(payload, ["Verified outcome"], ANSWER)
    assert parsed[0, "result_evidence_missing"]["status"] == "uncertain"


@pytest.mark.parametrize("raw", ['{"coverage": []', '{"coverage": [}', '{"coverage": [], "questions": []}'])
def test_structured_json_reader_rejects_invalid_responses(monkeypatch, raw):
    monkeypatch.setattr(interview_follow_up, "_request_json", lambda *args, **kwargs: raw)
    with pytest.raises(ValueError):
        interview_follow_up._json_reply([])


def test_json_transport_requests_a_constrained_schema(monkeypatch):
    calls = []
    monkeypatch.setattr(interview_follow_up, "get_config", lambda: SimpleNamespace(
        llm_ready=True, model="test-model", base_url="https://unit.test", nvidia_api_key="fake_key"))

    def http(url, **kwargs):
        calls.append(kwargs)
        return 200, {"choices": [{"message": {"content": '{"coverage":[],"questions":[]}'}}]}

    monkeypatch.setattr(interview_follow_up, "_http_json", http)
    assert interview_follow_up._request_json([]) == '{"coverage":[],"questions":[]}'
    payload = calls[0]["payload"]
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["response_format"]["json_schema"]["schema"]["required"] == ["coverage", "questions"]
    assert payload["reasoning_effort"] == "none"


def test_covered_unrelated_criterion_does_not_discard_a_real_gap():
    parsed = interview_follow_up._coverage({"coverage": [
        {"criterion_index": 0, "gap": None, "status": "present", "quote": ANSWER},
        coverage(index=1),
    ]}, ["Clarity", "Verified outcome"], ANSWER)
    assert list(parsed) == [(1, "result_evidence_missing")]


def test_uncertain_prior_evidence_cannot_create_a_question():
    row = coverage(status="uncertain", evidence=["A quote from an earlier follow-up"])
    parsed = interview_follow_up._coverage({"coverage": [row]}, ["Verified outcome"], ANSWER)
    assert parsed[0, "result_evidence_missing"]["status"] == "uncertain"
    assert parsed[0, "result_evidence_missing"]["evidence"] == []


def test_prior_answer_can_prove_coverage_but_cannot_anchor_a_new_question():
    previous = [{"question": "How did you measure it?", "answer": "I compared 100 requests."}]
    row = coverage(status="present", evidence=["I compared 100 requests."])
    parsed = interview_follow_up._coverage({"coverage": [row]}, ["Verified outcome"], ANSWER, previous)
    assert parsed[0, "result_evidence_missing"]["status"] == "present"
    row["status"] = "missing"
    with pytest.raises(ValueError):
        interview_follow_up._coverage({"coverage": [row]}, ["Verified outcome"], ANSWER, previous)


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
            current, grade_job = service.finish_follow_up("owner", item["id"], FollowUpAnswer(revision=current["revision"], request_id=follow["request_id"], text="Ten measurements before and after."))
            service.grade_answer("owner", item["id"], index, grade_job)
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


def ready_follow(service, item):
    follow = item["follow_up"]
    service.generate_follow_up("owner", item["id"], follow["request_id"])
    return service.get("owner", item["id"])


def test_original_grade_returning_during_combined_submit_is_discarded(setup, monkeypatch):
    service, item = setup
    item, original_job = service.submit_answer("owner", item["id"], 0,
        SubmitAnswer(revision=item["revision"], text=ANSWER + " More detail."))
    item = ready_follow(service, item)
    combined = []
    def grade(profile, question, text):
        if not combined:
            result, job = service.finish_follow_up("owner", item["id"], FollowUpAnswer(
                revision=item["revision"], request_id=item["follow_up"]["request_id"],
                text="I measured ten requests before and after."))
            combined.append(job)
            return {"score": 2, "feedback": "Old result", "evidence": ["40%"],
                    "model": "test", "used_fallback": False}
        assert "I measured ten requests" in text
        assert question["criteria"] == item["questions"][0]["criteria"]
        assert "How did you measure 40%?" in question["text"]
        return {"score": 8, "feedback": "Measured result", "evidence": ["ten requests before and after"],
                "model": "test", "used_fallback": False}
    monkeypatch.setattr(service.ai, "grade_answer", grade)
    service.grade_answer("owner", item["id"], 0, original_job)
    assert service.get("owner", item["id"])["answers"][0]["grade"] is None
    service.grade_answer("owner", item["id"], 0, combined[0])
    state = service.get("owner", item["id"])
    final = service.finalize("owner", item["id"], FinalizeInterview(revision=state["revision"]))
    assert final["report"]["overall_score"] == 8
    assert len(final["report"]["items"]) == 3
    assert final["report"]["items"][0]["answer"] == ANSWER + " More detail."


@pytest.mark.parametrize("quote", ["How did you measure 40%?", "An invented measurement"])
def test_combined_grade_rejects_question_or_invented_evidence(setup, monkeypatch, quote):
    service, item = setup
    item = ready_follow(service, item)
    item, job = service.finish_follow_up("owner", item["id"], FollowUpAnswer(
        revision=item["revision"], request_id=item["follow_up"]["request_id"], text="I ran ten requests."))
    monkeypatch.setattr(service.ai, "grade_answer", lambda *args: {
        "score": 9, "feedback": "Test", "evidence": [quote], "model": "test", "used_fallback": False})
    service.grade_answer("owner", item["id"], 0, job)
    state = service.get("owner", item["id"])
    assert state["answers"][0]["grading_status"] == "rejected"
    assert state["answers"][0]["grade"] is None


def test_combined_retry_survives_reload_and_does_not_enqueue_twice(setup):
    service, item = setup
    item = ready_follow(service, item)
    follow_id = item["follow_up"]["request_id"]
    item, old_job = service.finish_follow_up("owner", item["id"], FollowUpAnswer(
        revision=item["revision"], request_id=follow_id, text="I ran ten requests."))
    reloaded = InterviewService(service.repository, MockInterviewAI())
    request = FollowUpAction(revision=item["revision"], request_id=follow_id)
    item, job = reloaded.retry_follow_up_grade("owner", item["id"], request)
    assert job != old_job
    assert reloaded.retry_follow_up_grade("owner", item["id"], request) == (item, None)
    reloaded.grade_answer("owner", item["id"], 0, old_job)
    assert reloaded.get("owner", item["id"])["answers"][0]["grading_status"] == "pending"
    reloaded.grade_answer("owner", item["id"], 0, job)
    assert reloaded.get("owner", item["id"])["answers"][0]["grading_status"] == "graded"


def test_edit_during_combined_grading_discards_late_result(setup, monkeypatch):
    service, item = setup
    item = ready_follow(service, item)
    item, job = service.finish_follow_up("owner", item["id"], FollowUpAnswer(
        revision=item["revision"], request_id=item["follow_up"]["request_id"], text="Ten measurements."))
    def grade(*args):
        service.save_progress("owner", item["id"], SaveProgress(
            revision=item["revision"], current_question=0, answers=["Edited main answer"]))
        return {"score": 8, "feedback": "Old combined grade", "evidence": ["Ten measurements."],
                "model": "test", "used_fallback": False}
    monkeypatch.setattr(service.ai, "grade_answer", grade)
    service.grade_answer("owner", item["id"], 0, job)
    state = service.get("owner", item["id"])
    assert state["answers"][0]["grading_status"] == "draft"
    assert state["follow_ups"][0]["status"] == "invalidated"
