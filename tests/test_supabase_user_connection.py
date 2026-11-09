"""Interview connection to Supabase Auth; no real users or cloud writes."""
from io import BytesIO
import json
from urllib.error import HTTPError, URLError
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from assistant.auth import SupabaseUserAuth
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewError, InterviewService
from assistant.web import create_app


class AuthResponse(BytesIO):
    status = 200


def connect(monkeypatch, verifier, handler):
    def open_request(request, *, timeout):
        assert request.full_url == "https://unit-test.supabase.co/auth/v1/user"
        assert request.get_header("Apikey") == "sb_publishable_unit_test"
        assert timeout == 5
        return handler(request)
    monkeypatch.setattr(verifier._opener, "open", open_request)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://unit-test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_unit_test")


def test_browser_access_token_to_verified_owner_and_full_interview(tmp_path, monkeypatch, configured):
    owner, other = str(uuid4()), str(uuid4())
    users = {"browser-session": owner, "other-session": other}
    store = SQLAlchemyInterviewRepository.local(tmp_path / "connection.sqlite")
    app = create_app(service=InterviewService(store))
    assert isinstance(app.state.token_auth, SupabaseUserAuth)

    def auth_server(request):
        token = request.get_header("Authorization").split()[1]
        if token not in users:
            raise HTTPError(request.full_url, 401, "expired", {}, BytesIO(b"private"))
        return AuthResponse(json.dumps({"id": users[token], "role": "authenticated"}).encode())

    connect(monkeypatch, app.state.token_auth, auth_server)
    try:
        with TestClient(app) as client:
            assert client.post("/api/interviews", json={"job_profile": {"title": "Intern"}}).status_code == 401
            client.headers["Authorization"] = "Bearer browser-session"
            created = client.post("/api/interviews", json={"job_profile": {"title": "Intern"}})
            assert created.status_code == 201
            path = "/api/interviews/" + created.json()["id"]
            revision = 0
            for i in range(3):
                reply = client.post(f"{path}/answers/{i}", json={
                    "revision": revision,
                    "text": "I wrote Python tests with my team to check the project and fixed the errors.",
                })
                assert reply.status_code == 202
                revision = reply.json()["revision"]
            assert client.get(path + "/progress").json()["graded"] == 3
            assert client.post(path + "/finalize", json={"revision": revision}).status_code == 200
            client.headers["Authorization"] = "Bearer other-session"
            assert client.get(path).status_code == 404
            client.headers["Authorization"] = "Bearer expired-session"
            assert client.get(path).status_code == 401
            del client.headers["Authorization"]  # Browser sign-out stops sending its token.
            assert client.get(path).status_code == 401
    finally:
        store.close()


@pytest.mark.parametrize("status,expected", [(401, 401), (403, 401), (429, 503), (500, 503), (302, 503)])
def test_provider_failure_is_closed_and_does_not_echo_secrets(monkeypatch, status, expected):
    verifier = SupabaseUserAuth("https://unit-test.supabase.co", "sb_publishable_unit_test")
    def fail(request):
        raise HTTPError(request.full_url, status, "private-token-detail", {}, BytesIO(b"private"))
    connect(monkeypatch, verifier, fail)
    with pytest.raises(InterviewError) as exc:
        verifier.authenticate("Bearer private-token")
    assert exc.value.status == expected
    assert "private" not in exc.value.message


@pytest.mark.parametrize("payload", [b"bad-json", b"{}", b'{"id":"not-uuid","role":"authenticated"}',
                                   b'{"id":"00000000-0000-0000-0000-000000000001","role":"service_role"}'])
def test_invalid_provider_response_never_grants_access(monkeypatch, payload):
    verifier = SupabaseUserAuth("https://unit-test.supabase.co", "sb_publishable_unit_test")
    connect(monkeypatch, verifier, lambda request: AuthResponse(payload))
    with pytest.raises(InterviewError) as exc:
        verifier.authenticate("Bearer session")
    assert exc.value.status == 503


def test_network_timeout_returns_retryable_failure(monkeypatch):
    verifier = SupabaseUserAuth("https://unit-test.supabase.co", "sb_publishable_unit_test")
    def fail(request):
        raise URLError("private network details")
    connect(monkeypatch, verifier, fail)
    with pytest.raises(InterviewError) as exc:
        verifier.authenticate("Bearer session")
    assert exc.value.status == 503
    assert "private" not in exc.value.message


def test_redirects_do_not_forward_login_credentials():
    from assistant.auth import _NoAuthRedirect
    assert _NoAuthRedirect().redirect_request(None, None, 302, "", {}, "https://other.example") is None
