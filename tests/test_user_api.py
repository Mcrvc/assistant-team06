"""Profile CV and feedback APIs (src/assistant/user_api.py)."""
from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from assistant.interviews import InterviewError
from assistant.user_api import InMemoryProfileStore, SupabaseProfileStore, configured_profile_store
from assistant.web import create_app

ALICE_ID = "11111111-1111-4111-8111-111111111111"
BOB_ID = "22222222-2222-4222-8222-222222222222"
ALICE = {"Authorization": "Bearer token-alice"}
BOB = {"Authorization": "Bearer token-bob"}
CV = {"cv": ["summary", "education", "experience", "skills"], "cvMode": "text", "cvPdf": None}
FEEDBACK = {"grade_rating": 4, "quality_rating": 5, "difficulty": "medium",
            "comments": "Useful questions", "would_recommend": True}


def fake_auth(request):
    users = {"Bearer token-alice": ALICE_ID, "Bearer token-bob": BOB_ID}
    user = users.get(request.headers.get("authorization", ""))
    if user is None:
        raise InterviewError(401, "authentication_required", "Sign in first")
    return user


@pytest.fixture
def store():
    return InMemoryProfileStore()


@pytest.fixture
def client(store):
    app = create_app(auth_resolver=fake_auth, profile_store=store)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client


# ---------------------------------------------------------------- auth / config


@pytest.mark.parametrize("method,path", [("get", "/api/cv"), ("put", "/api/cv"), ("post", "/api/feedback")])
def test_every_route_needs_sign_in(client, method, path):
    kwargs = {"json": {}} if method != "get" else {}
    response = getattr(client, method)(path, headers={"Authorization": "Bearer stolen"}, **kwargs)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_no_storage_configured_is_503(monkeypatch):
    monkeypatch.delenv("INTERVIEW_STORAGE", raising=False)
    monkeypatch.delenv("INTERVIEW_LOCAL_STORAGE", raising=False)
    with TestClient(create_app(auth_resolver=fake_auth), base_url="http://127.0.0.1") as client:
        response = client.get("/api/cv", headers=ALICE)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "backend_not_configured"


def test_storage_switch_matches_interview_storage(monkeypatch):
    monkeypatch.delenv("INTERVIEW_STORAGE", raising=False)
    monkeypatch.setenv("INTERVIEW_LOCAL_STORAGE", "1")
    assert isinstance(configured_profile_store(), InMemoryProfileStore)
    monkeypatch.setenv("INTERVIEW_LOCAL_STORAGE", "0")
    assert configured_profile_store() is None


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
    # ui/js/app.js sends size as a display string ("120 KB").
    pdf = {**CV, "cvMode": "pdf", "cvPdf": {"name": "cv.pdf", "size": size, "date": "Nov 9, 2026"}}
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
    {**CV, "user_id": BOB_ID},
])
def test_invalid_cv_is_400_and_not_saved(client, store, bad):
    response = client.put("/api/cv", json=bad, headers=ALICE)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert store.cvs == {}


# ---------------------------------------------------------------- feedback


def test_feedback_saved_with_verified_user(client, store):
    response = client.post("/api/feedback", json=FEEDBACK, headers=ALICE)
    assert response.status_code == 201 and response.json() == {"ok": True}
    assert store.feedback == [{**FEEDBACK, "user_id": ALICE_ID}]


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard", None])
def test_feedback_difficulty_values(client, difficulty):
    body = {**FEEDBACK, "difficulty": difficulty}
    assert client.post("/api/feedback", json=body, headers=ALICE).status_code == 201


def test_feedback_only_ratings_required(client, store):
    assert client.post("/api/feedback", json={"grade_rating": 1, "quality_rating": 5},
                       headers=ALICE).status_code == 201
    assert store.feedback[0]["comments"] == "" and store.feedback[0]["difficulty"] is None


@pytest.mark.parametrize("bad", [
    {},
    {"grade_rating": 3},
    {**FEEDBACK, "grade_rating": 0},
    {**FEEDBACK, "quality_rating": 6},
    {**FEEDBACK, "grade_rating": True},
    {**FEEDBACK, "grade_rating": "4"},
    {**FEEDBACK, "grade_rating": 4.5},
    {**FEEDBACK, "difficulty": "too_hard"},
    {**FEEDBACK, "comments": "x" * 2001},
    {**FEEDBACK, "would_recommend": "yes"},
    {**FEEDBACK, "user_id": BOB_ID},
])
def test_invalid_feedback_is_400(client, store, bad):
    assert client.post("/api/feedback", json=bad, headers=ALICE).status_code == 400
    assert store.feedback == []


def test_cors_preflight_allows_put(store, monkeypatch):
    monkeypatch.setenv("CORS_ORIGIN", "https://yourin.vercel.app")
    app = create_app(auth_resolver=fake_auth, profile_store=store)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.options("/api/cv", headers={
            "Origin": "https://yourin.vercel.app", "Access-Control-Request-Method": "PUT"})
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]


# ---------------------------------------------------------------- Supabase adapter (fake HTTP)


class FakeResponse:
    def __init__(self, status, body):
        self.status, self._raw = status, json.dumps(body).encode() if body is not None else b""

    def read(self, limit=-1):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Records every request; replies with queued (status, body) tuples."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def open(self, request, timeout=None):
        body = json.loads(request.data) if request.data else None
        self.requests.append({"method": request.get_method(), "url": request.full_url,
                              "headers": dict(request.header_items()), "body": body})
        status, payload = self.replies.pop(0)
        if status >= 400:
            raise HTTPError(request.full_url, status, "error", {}, io.BytesIO(b'{"message":"CV text"}'))
        return FakeResponse(status, payload)


def supabase(*replies):
    opener = FakeOpener(*replies)
    return SupabaseProfileStore("https://demo.supabase.co", "sb_secret_test", opener=opener), opener


def test_supabase_get_cv_reads_own_account_row():
    store, opener = supabase((200, [{"cv": ["a", "b", "c", "d"], "cv_mode": "text", "cv_pdf": None}]))
    assert store.get_cv(ALICE_ID) == {"cv": ["a", "b", "c", "d"], "cvMode": "text", "cvPdf": None}
    sent = opener.requests[0]
    assert sent["method"] == "GET"
    assert sent["url"] == ("https://demo.supabase.co/rest/v1/accounts?id=eq." + ALICE_ID
                           + "&select=cv,cv_mode,cv_pdf")
    headers = {k.lower(): v for k, v in sent["headers"].items()}
    assert headers["apikey"] == "sb_secret_test" and "authorization" not in headers


@pytest.mark.parametrize("rows", [[], [{"cv": None, "cv_mode": "text", "cv_pdf": None}]])
def test_supabase_get_cv_none_when_missing(rows):
    store, _ = supabase((200, rows))
    assert store.get_cv(ALICE_ID) is None


def test_supabase_save_cv_patches_cv_columns_only():
    store, opener = supabase((200, [{"id": ALICE_ID}]))
    pdf = {"name": "cv.pdf", "size": "120 KB", "date": "Nov 9, 2026"}
    store.save_cv(ALICE_ID, {"cv": ["a", "b", "c", "d"], "cvMode": "pdf", "cvPdf": pdf})
    sent = opener.requests[0]
    assert sent["method"] == "PATCH"
    assert sent["url"].endswith("/rest/v1/accounts?id=eq." + ALICE_ID + "&select=id")
    assert sent["body"] == {"cv": ["a", "b", "c", "d"], "cv_mode": "pdf", "cv_pdf": pdf}


def test_supabase_save_cv_without_account_row_is_409():
    store, _ = supabase((200, []))
    with pytest.raises(InterviewError) as error:
        store.save_cv(ALICE_ID, CV)
    assert error.value.status == 409 and error.value.code == "account_not_found"


def test_supabase_feedback_inserts_row_for_verified_user():
    store, opener = supabase((201, None))
    store.add_feedback(ALICE_ID, FEEDBACK)
    sent = opener.requests[0]
    assert sent["method"] == "POST" and sent["url"].endswith("/rest/v1/feedback")
    assert sent["body"] == {**FEEDBACK, "user_id": ALICE_ID}


def test_supabase_errors_are_503_without_leaking_body():
    store, _ = supabase((500, None))
    with pytest.raises(InterviewError) as error:
        store.add_feedback(ALICE_ID, FEEDBACK)
    assert error.value.status == 503 and "CV text" not in error.value.message


def test_supabase_rejects_publishable_key_and_non_https():
    with pytest.raises(ValueError):
        SupabaseProfileStore("https://demo.supabase.co", "sb_publishable_x")
    with pytest.raises(ValueError):
        SupabaseProfileStore("http://demo.supabase.co", "sb_secret_x")


def test_supabase_store_over_http_routes():
    """Route -> adapter end to end, still without network."""
    opener = FakeOpener((200, [{"id": ALICE_ID}]), (201, None))
    store = SupabaseProfileStore("https://demo.supabase.co", "sb_secret_test", opener=opener)
    app = create_app(auth_resolver=fake_auth, profile_store=store)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.put("/api/cv", json=CV, headers=ALICE).status_code == 200
        assert client.post("/api/feedback", json=FEEDBACK, headers=ALICE).status_code == 201
    assert [r["method"] for r in opener.requests] == ["PATCH", "POST"]
