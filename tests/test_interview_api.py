from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from fastapi.testclient import TestClient

from assistant.api import create_app, get_current_user
from assistant.interview_ai import MockInterviewAI
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewService

JOB = {"job_profile": {"title": "Python intern"}}
ANSWER = "I built a small Python project and wrote tests with my team to verify the result."


@pytest.fixture
def service(tmp_path):
    store = SQLAlchemyInterviewRepository.local(tmp_path / "api.sqlite")
    yield InterviewService(store)
    store.close()


def client_for(app, **kwargs):
    return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000), **kwargs)


@pytest.fixture
def client(service):
    with client_for(create_app(service=service, demo_enabled=True)) as client:
        assert client.post("/api/demo/session").status_code == 200
        yield client


def test_http_full_lifecycle_and_progress(client):
    response = client.post("/api/interviews", json=JOB)
    assert response.status_code == 201
    created = response.json()
    assert created["question"]["criteria"] and created["total_questions"] == 3
    path = f'/api/interviews/{created["id"]}'
    revision = 0
    for index in range(3):
        response = client.post(f"{path}/answers/{index}", json={"revision": revision, "text": ANSWER})
        assert response.status_code == 202
        assert response.json()["answers"][index]["grading_status"] == "pending"
        revision = response.json()["revision"]
    assert client.get(f"{path}/progress").json()["graded"] == 3
    result = client.post(f"{path}/finalize", json={"revision": revision})
    assert result.status_code == 200
    assert result.json()["report"]["used_fallback"] is True
    assert client.get(path).json()["status"] == "finalized"
    assert client.post(f"{path}/finalize", json={"revision": revision}).json() == result.json()


def test_cookie_required_and_demo_disabled_by_default(service, monkeypatch):
    monkeypatch.delenv("INTERVIEW_DEMO_ENABLED", raising=False)
    with client_for(create_app(service=service, demo_enabled=False)) as client:
        assert client.post("/api/demo/session").status_code == 404
        assert client.post("/api/interviews", json=JOB).status_code == 503
    with client_for(create_app(service=service, demo_enabled=True)) as client:
        assert client.post("/api/interviews", json=JOB).status_code == 401
        login = client.post("/api/demo/session")
        assert "HttpOnly" in login.headers["set-cookie"]
        assert "SameSite=strict" in login.headers["set-cookie"]
        assert client.post("/api/interviews", json=JOB).status_code == 201


def test_demo_rejects_remote_clients_and_cross_origin_requests(service):
    app = create_app(service=service, demo_enabled=True)
    with TestClient(app, base_url="http://127.0.0.1", client=("203.0.113.5", 50000)) as remote:
        assert remote.post("/api/demo/session").status_code == 403
    with client_for(app) as client:
        assert client.post("/api/demo/session", headers={"Origin": "https://other.example"}).status_code == 403
        assert client.post("/api/demo/session", headers={"Host": "other.example"}).status_code == 403


@pytest.mark.parametrize("payload", [
    {}, {"job_profile": {}}, {"job_profile": {"title": 123}},
    {**JOB, "owner_id": "other-user"}, {**JOB, "cv": {"name": "cv.pdf"}},
    {"job_profile": {"title": "x" * 201}}, {**JOB, "cv": "x" * 40001},
])
def test_invalid_creation_payloads(client, payload):
    assert client.post("/api/interviews", json=payload).status_code == 400


def test_malformed_json_and_validation_do_not_echo_private_data(client):
    response = client.post("/api/interviews", content='{"cv": "private-cv",',
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert "private-cv" not in response.text
    assert client.post("/api/interviews", json=[]).status_code == 400


def test_http_progress_conflict_and_invalid_indexes(client):
    item = client.post("/api/interviews", json=JOB).json()
    path = f'/api/interviews/{item["id"]}'
    payload = {"revision": 0, "current_question": 1, "status": "interrupted", "answers": [ANSWER, "", ""]}
    assert client.post(f"{path}/progress", json=payload).status_code == 200
    assert client.post(f"{path}/progress", json=payload).status_code == 409
    assert client.get(path).json()["status"] == "interrupted"
    for bad in [True, "1", -1]:
        assert client.post(f"{path}/progress", json={"revision": bad, "current_question": 1}).status_code == 400
    assert client.post(f"{path}/answers/3", json={"revision": 1, "text": ANSWER}).status_code == 400
    assert client.post(f"{path}/answers/0", json={"revision": 1, "text": "   "}).status_code == 400


def test_auth_seam_applies_ownership_to_every_endpoint(service):
    app = create_app(service=service, demo_enabled=False)
    app.dependency_overrides[get_current_user] = lambda: "user-a"
    with client_for(app) as client:
        item = client.post("/api/interviews", json=JOB).json()
        path = f'/api/interviews/{item["id"]}'
        app.dependency_overrides[get_current_user] = lambda: "user-b"
        assert client.get(path).status_code == 404
        assert client.get(f"{path}/progress").status_code == 404
        assert client.post(f"{path}/progress", json={"revision": 0, "current_question": 0}).status_code == 404
        assert client.post(f"{path}/answers/0", json={"revision": 0, "text": ANSWER}).status_code == 404
        assert client.post(f"{path}/finalize", json={"revision": 0}).status_code == 404


def test_existing_endpoints_static_ui_and_openapi_remain_available(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert "supabaseUrl" in client.get("/api/config").json()
    assert client.post("/api/answer", json={"question": "hi"}).json()["used_fallback"] is True
    assert client.get("/dashboard.html").status_code == 200
    assert client.get("/docs").status_code == 200
    assert "/api/interviews/{interview_id}/answers/{index}" in client.get("/openapi.json").json()["paths"]
    assert client.get("/api/unknown").json()["error"]["code"] == "not_found"


def test_response_body_is_sent_while_background_ai_is_still_blocked(service):
    entered, release, sent = threading.Event(), threading.Event(), threading.Event()
    statuses = []
    class SlowAI(MockInterviewAI):
        def grade_answer(self, *args):
            entered.set()
            assert release.wait(5)
            return super().grade_answer(*args)
    service.ai.provider = SlowAI()
    app = create_app(service=service, demo_enabled=True)

    class CaptureSend:
        def __init__(self, wrapped):
            self.wrapped = wrapped
        async def __call__(self, scope, receive, send):
            async def capture(message):
                if "/answers/" in scope.get("path", ""):
                    if message["type"] == "http.response.start":
                        statuses.append(message["status"])
                    if message["type"] == "http.response.body" and not message.get("more_body"):
                        sent.set()
                await send(message)
            await self.wrapped(scope, receive, capture)

    with client_for(CaptureSend(app)) as client:
        client.post("/api/demo/session")
        item = client.post("/api/interviews", json=JOB).json()
        path = f'/api/interviews/{item["id"]}'
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(client.post, f"{path}/answers/0", json={"revision": 0, "text": ANSWER})
            try:
                assert sent.wait(5) and entered.wait(5)
                assert statuses == [202]
                assert service.get("local-demo", item["id"])["answers"][0]["grading_status"] == "pending"
            finally:
                release.set()
            assert future.result(timeout=5).status_code == 202
        assert client.get(f"{path}/progress").json()["graded"] == 1


def test_storage_failure_is_sanitized(client, service, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    item = client.post("/api/interviews", json=JOB).json()
    def unavailable(*args):
        raise SQLAlchemyError("private database connection details")
    monkeypatch.setattr(service.repository, "get", unavailable)
    response = client.get(f'/api/interviews/{item["id"]}')
    assert response.status_code == 503
    assert "private database" not in response.text


def test_cookie_resolver_seam_without_demo_login(service):
    app = create_app(service=service, demo_enabled=False,
                     auth_resolver=lambda request: "verified-user" if request.cookies.get("session") == "test-session" else "")
    with client_for(app) as client:
        assert client.post("/api/interviews", json=JOB).status_code == 401
        client.cookies.set("session", "test-session")
        assert client.post("/api/interviews", json=JOB).status_code == 201
        assert client.post("/api/demo/session").status_code == 404


def test_app_restart_keeps_data_but_requires_new_demo_cookie(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERVIEW_DB_PATH", str(tmp_path / "lifecycle.sqlite"))
    first_app = create_app(demo_enabled=True)
    with client_for(first_app) as client:
        client.post("/api/demo/session")
        item = client.post("/api/interviews", json=JOB).json()
        path = f'/api/interviews/{item["id"]}'
        saved = client.post(path + "/progress", json={
            "revision": 0, "answers": [ANSWER, "draft two", ""],
            "current_question": 1, "status": "interrupted",
        })
        assert saved.status_code == 200
        old_cookie = dict(client.cookies)
    with client_for(create_app(demo_enabled=True)) as client:
        client.cookies.update(old_cookie)
        assert client.get(path).status_code == 401
        client.post("/api/demo/session")
        resumed = client.get(path).json()
        assert resumed["answers"][1]["text"] == "draft two"
        assert resumed["status"] == "interrupted" and resumed["current_question"] == 1
