"""Profile/CV, history, report and feedback APIs (src/assistant/user_api.py)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from assistant.api import create_app
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewError, InterviewService

ALICE = {"Authorization": "Bearer token-alice"}
BOB = {"Authorization": "Bearer token-bob"}
JOB = {"job_profile": {"title": "Python intern"}}
ANSWER = "I built a small Python project and wrote tests with my team to verify the result."
CV = {"cv": ["summary", "education", "experience", "skills"], "cvMode": "text", "cvPdf": None}
FEEDBACK = {"grade_rating": 4, "quality_rating": 5, "difficulty": "just_right",
            "comments": "Useful questions", "would_recommend": True}


def fake_auth(request):
    users = {"Bearer token-alice": "alice", "Bearer token-bob": "bob"}
    user = users.get(request.headers.get("authorization", ""))
    if user is None:
        raise InterviewError(401, "authentication_required", "Sign in first")
    return user


@pytest.fixture
def service(tmp_path):
    store = SQLAlchemyInterviewRepository.local(tmp_path / "user_api.sqlite")
    yield InterviewService(store)
    store.close()


@pytest.fixture
def client(service):
    app = create_app(service=service, demo_enabled=False, auth_resolver=fake_auth)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client


def make_interview(client, headers=ALICE, finish=True, name=None):
    body = {**JOB, "name": name} if name else JOB
    created = client.post("/api/interviews", json=body, headers=headers).json()
    path, revision = f'/api/interviews/{created["id"]}', created["revision"]
    if finish:
        for index in range(3):
            response = client.post(f"{path}/answers/{index}", headers=headers,
                                   json={"revision": revision, "text": ANSWER})
            revision = response.json()["revision"]
        assert client.post(f"{path}/finalize", json={"revision": revision},
                           headers=headers).status_code == 200
    return created["id"]


# ---------------------------------------------------------------- auth


@pytest.mark.parametrize("method,path", [
    ("get", "/api/cv"), ("put", "/api/cv"), ("get", "/api/interviews"),
    ("get", "/api/interviews/00000000-0000-0000-0000-000000000000/report"),
    ("post", "/api/feedback"),
])
def test_every_route_needs_sign_in(client, method, path):
    kwargs = {"json": {}} if method in ("put", "post") else {}
    response = getattr(client, method)(path, headers={"Authorization": "Bearer stolen"}, **kwargs)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_auth_not_integrated_is_503(service, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    app = create_app(service=service, demo_enabled=False)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/cv", headers=ALICE).status_code == 503


# ---------------------------------------------------------------- CV


def test_cv_404_then_save_then_read(client):
    assert client.get("/api/cv", headers=ALICE).status_code == 404
    assert client.put("/api/cv", json=CV, headers=ALICE).json() == {"ok": True}
    assert client.get("/api/cv", headers=ALICE).json() == CV


def test_cv_is_private_per_user(client):
    client.put("/api/cv", json=CV, headers=ALICE)
    assert client.get("/api/cv", headers=BOB).status_code == 404


@pytest.mark.parametrize("size", [1234, "120 KB"])
def test_pdf_cv(client, size):
    # frontend/js/app.js sends size as a display string ("120 KB").
    pdf = {**CV, "cvMode": "pdf", "cvPdf": {"name": "cv.pdf", "size": size, "date": "Nov 8, 2026"}}
    assert client.put("/api/cv", json=pdf, headers=ALICE).status_code == 200
    assert client.get("/api/cv", headers=ALICE).json()["cvPdf"]["size"] == size


@pytest.mark.parametrize("bad", [
    {},
    {**CV, "cv": ["only", "three", "items"]},
    {**CV, "cv": ["a", "b", "c", 4]},
    {**CV, "cv": ["x" * 5001, "", "", ""]},
    {**CV, "cvMode": "word"},
    {**CV, "cvMode": "pdf", "cvPdf": None},
    {**CV, "cvPdf": {"name": "", "size": 1, "date": "d"}},
    {**CV, "cvPdf": {"name": "a.pdf", "size": -1, "date": "d"}},
    {**CV, "owner": "bob"},
])
def test_invalid_cv_is_400_and_not_saved(client, bad):
    response = client.put("/api/cv", json=bad, headers=ALICE)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert client.get("/api/cv", headers=ALICE).status_code == 404


def test_cors_preflight_allows_put(service, monkeypatch):
    monkeypatch.setenv("CORS_ORIGIN", "https://yourin.vercel.app")
    app = create_app(service=service, demo_enabled=False, auth_resolver=fake_auth)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.options("/api/cv", headers={
            "Origin": "https://yourin.vercel.app", "Access-Control-Request-Method": "PUT"})
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]


# ---------------------------------------------------------------- history


def test_history_empty(client):
    assert client.get("/api/interviews", headers=ALICE).json() == {"interviews": []}


def test_history_lists_only_own_interviews_newest_first(client):
    first = make_interview(client, finish=True, name="First")
    second = make_interview(client, finish=False, name="Second")
    make_interview(client, headers=BOB, finish=False)

    items = client.get("/api/interviews", headers=ALICE).json()["interviews"]
    assert [item["id"] for item in items] == [second, first]
    assert items[0]["finished"] is False and items[0]["has_report"] is False
    assert items[1]["finished"] is True and items[1]["has_report"] is True
    assert items[1]["progress"]["graded"] == 3
    # Summary only: no questions, answers, CV or report body in the list.
    assert not {"questions", "answers", "cv", "report", "owner_id"} & set(items[0])


# ---------------------------------------------------------------- report


def test_report_of_finalized_interview(client):
    interview_id = make_interview(client, finish=True)
    response = client.get(f"/api/interviews/{interview_id}/report", headers=ALICE)
    assert response.status_code == 200
    report = response.json()["report"]
    assert len(report["items"]) == 3
    assert report["label"] in ("Good", "Needs Improvement")


def test_report_before_finalize_is_409(client):
    interview_id = make_interview(client, finish=False)
    response = client.get(f"/api/interviews/{interview_id}/report", headers=ALICE)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "report_not_ready"


def test_report_of_other_user_or_unknown_is_404(client):
    interview_id = make_interview(client, finish=True)
    assert client.get(f"/api/interviews/{interview_id}/report", headers=BOB).status_code == 404
    unknown = "/api/interviews/00000000-0000-0000-0000-000000000000/report"
    assert client.get(unknown, headers=ALICE).status_code == 404


def test_report_bad_id_is_400(client):
    assert client.get("/api/interviews/not-a-uuid/report", headers=ALICE).status_code == 400


# ---------------------------------------------------------------- feedback


def test_feedback_saved_with_verified_user(client):
    response = client.post("/api/feedback", json=FEEDBACK, headers=ALICE)
    assert response.status_code == 201 and response.json() == {"ok": True}
    saved = client.app.state.profile_store.feedback[0]
    assert saved["user_id"] == "alice" and saved["grade_rating"] == 4 and "created" in saved


def test_feedback_optional_fields(client):
    minimal = {"grade_rating": 1, "quality_rating": 5}
    assert client.post("/api/feedback", json=minimal, headers=ALICE).status_code == 201


@pytest.mark.parametrize("bad", [
    {},
    {**FEEDBACK, "grade_rating": 0},
    {**FEEDBACK, "quality_rating": 6},
    {**FEEDBACK, "grade_rating": True},
    {**FEEDBACK, "grade_rating": "4"},
    {**FEEDBACK, "difficulty": "very hard"},
    {**FEEDBACK, "comments": "x" * 2001},
    {**FEEDBACK, "would_recommend": "yes"},
    {**FEEDBACK, "user_id": "bob"},
])
def test_invalid_feedback_is_400(client, bad):
    assert client.post("/api/feedback", json=bad, headers=ALICE).status_code == 400
    store = getattr(client.app.state, "profile_store", None)
    assert store is None or store.feedback == []


def test_unknown_put_api_is_json_404(client):
    response = client.put("/api/unknown", json={}, headers=ALICE)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
