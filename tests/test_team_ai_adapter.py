import json

import pytest

from assistant import ai, aiworker
from assistant.interview_ai import SafeInterviewAI, TeamInterviewAI, configured_ai
from assistant.interview_schemas import Generation

RUBRIC = {"max_score": 10, "criteria": [
    {"name": "actions", "points": 6, "good": "Explain personal actions"},
    {"name": "result", "points": 4, "good": "Give a measured result"},
]}
JOB = {"title": "Python intern"}


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Unit tests must not use a real provider")
    monkeypatch.setattr(ai.urllib.request, "urlopen", deny)
    ai.reset_config_cache()
    yield
    ai.reset_config_cache()


def generation():
    return {"source": "nvidia", "questions": [
        {"question": f"Question {i}?", "rubric": RUBRIC} for i in range(3)
    ]}


def test_adapter_uses_team_generator_and_preserves_weighted_rubric(monkeypatch):
    calls = []
    def generate(job, cv, notes, sources, **options):
        calls.append((job, cv, notes, sources, options))
        return generation()
    monkeypatch.setattr(aiworker, "generate_questions", generate)
    result = SafeInterviewAI(TeamInterviewAI(timeout_s=12)).generate_questions(JOB, "private CV")
    assert result["used_fallback"] is False
    assert result["questions"][0]["rubric"]["criteria"][0]["points"] == 6
    assert calls[0][1] == {} and calls[0][4] == {"timeout_s": 12}


def test_cv_forwarding_requires_explicit_opt_in(monkeypatch):
    received = []
    def generate(job, cv, *args, **kwargs):
        received.append(cv)
        return generation()
    monkeypatch.setattr(aiworker, "generate_questions", generate)
    TeamInterviewAI(allow_cv=True).generate_questions(JOB, "fake CV for testing")
    assert received == [{"raw": "fake CV for testing"}]


def test_team_generation_uses_the_configured_timeout(monkeypatch):
    calls = []
    def complete(messages, **options):
        calls.append(options)
        return ai.Completion(text=json.dumps(generation()), model="test-model")
    monkeypatch.setattr(aiworker, "complete", complete)
    result = aiworker.generate_questions(JOB, {}, "", [], timeout_s=9)
    assert len(result["questions"]) == 3 and calls[0]["timeout_s"] == 9


def test_evidence_is_requested_from_model_and_not_synthesized(monkeypatch):
    def complete(messages, **options):
        assert options["timeout_s"] == 7
        assert "exact quotations" in messages[0]["content"]
        return ai.Completion(text=json.dumps({"score": 7.5, "feedback": "Clear result",
                                             "evidence": ["wrote tests"]}), model="team-model")
    monkeypatch.setattr(aiworker, "complete", complete)
    result = TeamInterviewAI(timeout_s=7).grade_answer(
        JOB, {"text": "Your project?", "rubric": RUBRIC}, "I wrote tests.")
    assert result["evidence"] == ["wrote tests"] and result["model"] == "team-model"
    assert result["used_fallback"] is False


@pytest.mark.parametrize("bad", ["two_questions", "bad_weights", "provider_error"])
def test_provider_failures_keep_three_labeled_fallback_questions(monkeypatch, bad):
    def generate(*args, **kwargs):
        if bad == "provider_error":
            raise TimeoutError("private error details")
        value = generation()
        if bad == "two_questions":
            value["questions"].pop()
        else:
            value["questions"][0] = {"question": "x", "rubric": {"max_score": 10,
                "criteria": [{"name": "x", "points": 3, "good": "x"}]}}
        return value
    monkeypatch.setattr(aiworker, "generate_questions", generate)
    result = SafeInterviewAI(TeamInterviewAI()).generate_questions(JOB, None)
    assert result["used_fallback"] and len(result["questions"]) == 3
    Generation.model_validate(result)


def test_missing_or_non_numeric_score_falls_back_without_passing_as_real_ai(monkeypatch):
    monkeypatch.setattr(aiworker, "grade_answer_with_evidence", lambda *a, **k: {
        "score": None, "feedback": "placeholder", "model": "nvidia", "used_fallback": False,
    })
    result = SafeInterviewAI(TeamInterviewAI()).grade_answer(JOB, {"text": "x", "rubric": RUBRIC}, "I wrote tests")
    assert result["used_fallback"] and result["model"] == "local-mock"


def test_provider_selection_is_explicit(monkeypatch):
    monkeypatch.setenv("INTERVIEW_AI_PROVIDER", "nvidia")
    monkeypatch.delenv("INTERVIEW_ALLOW_CV_TO_AI", raising=False)
    assert configured_ai().allow_cv is False
    monkeypatch.setenv("INTERVIEW_AI_PROVIDER", "unknown")
    with pytest.raises(ValueError):
        configured_ai()


def test_placeholder_nvidia_key_does_not_hide_the_shared_llm_key(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "insert_your_key_here")
    monkeypatch.setenv("LLM_API_KEY", "unit-test-key-not-real")
    assert ai.get_config().nvidia_api_key == "unit-test-key-not-real"


def test_team_generator_and_grader_integrate_through_http_to_non_mock_report(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from assistant.api import create_app
    from assistant.interviews import InterviewService
    from assistant.interview_store import SQLAlchemyInterviewRepository
    calls = []
    monkeypatch.setenv("NVIDIA_MODEL", "unit-team-provider")
    def complete(messages, **options):
        calls.append(messages)
        if "keys score" in messages[0]["content"]:
            payload = {"score": 7.0, "feedback": "Clear actions", "evidence": ["wrote tests"]}
        else:
            payload = generation()
        return ai.Completion(text=json.dumps(payload), model="unit-team-provider")
    monkeypatch.setattr(aiworker, "complete", complete)
    repository = SQLAlchemyInterviewRepository.local(tmp_path / "provider-http.sqlite")
    try:
        app = create_app(service=InterviewService(repository, TeamInterviewAI()), demo_enabled=True)
        with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
            client.post("/api/demo/session")
            created = client.post("/api/interviews", json={"job_profile": JOB}).json()
            path = f'/api/interviews/{created["id"]}'
            revision = 0
            for index in range(3):
                result = client.post(path + f"/answers/{index}", json={
                    "revision": revision, "text": "I wrote tests and checked the result.",
                })
                assert result.status_code == 202
                revision = result.json()["revision"]
            completed = client.post(path + "/finalize", json={"revision": revision})
            assert completed.status_code == 200
            assert completed.json()["report"]["used_fallback"] is False
            assert completed.json()["report"]["items"][0]["question"]["rubric"]["criteria"][0]["points"] == 6
            assert len(calls) == 4
    finally:
        repository.close()
