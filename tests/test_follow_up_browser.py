"""Playtest the browser against the real local HTTP app and disposable storage."""
import os
import re
import socket
import threading
import time

import pytest
import uvicorn

from assistant.interview_ai import MockInterviewAI
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewError, InterviewService
from assistant.user_api import InMemoryProfileStore
from assistant.web import create_app

pytestmark = pytest.mark.slow

# Stand in for the external Auth SDK. All app JavaScript and interview requests
# run as usual, and the in-process backend checks the bearer token.
AUTH_SDK = """
window.supabase = {createClient: () => {
    const user = {id: "playtest-owner", user_metadata: {username: "playtester"}};
    const session = {user, access_token: "playtest-token"};
    const signedIn = () => sessionStorage.getItem("playtest:signedIn") === "1";
    return {auth: {
        getSession: async () => ({data: {session: signedIn() ? session : null}}),
        getUser: async () => ({data: {user: signedIn() ? user : null}}),
        signInWithPassword: async () => {
            sessionStorage.setItem("playtest:signedIn", "1");
            return {data: {user, session}};
        },
        signOut: async () => { sessionStorage.removeItem("playtest:signedIn"); return {}; }
    }};
}};
"""
ANSWERS = [
    "I built a Python API with my team and used tests to verify the result.",
    "I isolated the failing request and wrote a regression test before fixing it.",
    "I compared the results and asked a teammate to review the changes.",
]


@pytest.fixture
def website(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://playtest.example")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "public-playtest-key")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "server-playtest-key")
    repository = SQLAlchemyInterviewRepository.local(tmp_path / "browser.sqlite")

    def resolve_user(request):
        if request.headers.get("authorization") == "Bearer playtest-token":
            return "playtest-owner"
        raise InterviewError(401, "authentication_required", "Sign in first")

    app = create_app(service=InterviewService(repository, MockInterviewAI()),
                     auth_resolver=resolve_user, profile_store=InMemoryProfileStore())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        base = f"http://127.0.0.1:{sock.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", proxy_headers=False))
        worker = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and worker.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started
            yield base
        finally:
            server.should_exit = True
            worker.join(timeout=5)
            repository.close()


@pytest.fixture
def browser_page(website, request):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as engine:
        browser = engine.chromium.launch(channel=os.environ.get("YOURIN_TEST_BROWSER", "chrome"))
        context = browser.new_context(**getattr(request, "param", {}))

        def route_request(route):
            url = route.request.url
            if url.startswith(website + "/api/tts"):
                route.fulfill(status=503, body="Test audio unavailable")
            elif url.startswith(website + "/"):
                route.continue_()
            elif url.startswith("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"):
                route.fulfill(content_type="application/javascript", body=AUTH_SDK)
            else:
                route.abort()

        context.route("**/*", route_request)
        page = context.new_page()
        page.set_default_timeout(5000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            yield page, playwright.expect
            assert not errors
        finally:
            browser.close()


def sign_in(page):
    page.locator("#username").fill("playtester")
    page.locator("#password").fill("playtest-password")
    page.locator('#sign-in-form button[type="submit"]').click()


def start_interview(page, expect, base):
    # Open a protected page to make sure the signed-out redirect works.
    page.goto(base + "/storage.html")
    page.wait_for_url("**/sign-in.html")
    sign_in(page)
    page.wait_for_url("**/storage.html")
    expect(page.get_by_text("No saved interviews")).to_be_visible()
    page.goto(base + "/job-profile.html")
    expect(page.locator("[data-username]").first).to_have_text("playtester")
    page.locator("#job-source").fill("Python backend intern. Build APIs and write tests.")
    page.locator('#job-form button[type="submit"]').click()
    try:
        page.wait_for_url("**/interview.html?id=*")
    except Exception:
        print("Interview creation diagnostics:", page.url, page.locator("#job-error").inner_text())
        raise
    expect(page.locator("#question-badge")).to_have_text("1 of 3")
    expect(page.locator("#answer")).to_be_editable()


def select_first(question, answer, previous):
    if "Python API" in answer:
        return {"quote": "Python API", "question": "How did you test your Python API?"}
    return None


def test_follow_up_browser_round_trip(browser_page, website, monkeypatch):
    from assistant import interview_follow_up
    monkeypatch.setattr(interview_follow_up, "generate", select_first)
    page, expect = browser_page
    page.route("**/js/voice.js*", lambda route: route.fulfill(content_type="application/javascript", body="""
        window.spoken = [];
        window.Voice = {
            ttsSupported: () => true, sttSupported: () => true,
            speak: text => { window.spoken.push(text); return false; }, stopSpeaking: () => {},
            startListening: options => { options.onText('I dictated six integration tests.'); return true; },
            stopListening: () => {}
        };
    """))
    start_interview(page, expect, website)
    page.locator("#answer").fill(ANSWERS[0])
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("1 of 3 - Follow-up")
    expect(page.locator("#answer-status")).to_have_text("Answer this follow-up to continue.")
    expect(page.locator("#question-text")).to_contain_text("How did you test your Python API?")
    expect(page.locator("#robot-stage")).to_be_visible()
    assert page.locator("#follow-up-practice").count() == 0
    page.locator("#robot-replay-btn").click()
    assert "How did you test your Python API?" in page.evaluate("spoken[spoken.length - 1]")
    page.locator("#mic-toggle-btn").click()
    expect(page.locator("#answer")).to_have_value("I dictated six integration tests.")
    page.locator("#mic-toggle-btn").click()
    page.locator("#answer").fill("I added six integration tests.")
    page.reload()
    expect(page.locator("#answer")).to_have_value("I added six integration tests.")
    expect(page.locator("#question-badge")).to_have_text("1 of 3 - Follow-up")
    page.locator("#prev-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("1 of 3")
    expect(page.locator("#answer")).to_have_value(ANSWERS[0])
    page.locator("#next-question-btn").click()
    expect(page.locator("#answer")).to_have_value("I added six integration tests.")
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("2 of 3")
    expect(page.locator("#question-text")).not_to_contain_text("How did you test")
    page.locator("#answer").fill(ANSWERS[1])
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("3 of 3")
    page.locator("#answer").fill(ANSWERS[2])
    page.locator("#next-question-btn").click()
    page.wait_for_url("**/done-interview.html")
    page.locator("#interview-name").fill("Follow-up round trip")
    page.locator('#done-form button[type="submit"]').click()
    page.wait_for_url("**/report.html")
    cards = page.locator("#report-cards > article")
    expect(cards).to_have_count(3)
    expect(cards.first.locator(".report-follow-up")).to_contain_text("I added six integration tests.")
    expect(cards.first).to_contain_text("This score includes your original answer and follow-up.")
    expect(cards.first.locator(".feedback-eval-badge")).to_contain_text("/10")
    expect(cards.nth(1).locator(".report-follow-up")).to_have_count(0)


def test_provider_failure_continues_interview(browser_page, website, monkeypatch):
    from assistant import interview_follow_up
    def fail(*args):
        raise TimeoutError()
    monkeypatch.setattr(interview_follow_up, "generate", fail)
    page, expect = browser_page
    start_interview(page, expect, website)
    page.locator("#answer").fill(ANSWERS[0])
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("2 of 3")
    page.locator("#answer").fill("My main draft stays here.")
    expect(page.locator("#answer")).to_have_value("My main draft stays here.")


def test_sign_out_saves_follow_up_before_leaving(browser_page, website, monkeypatch):
    from assistant import interview_follow_up
    monkeypatch.setattr(interview_follow_up, "generate", select_first)
    page, expect = browser_page
    start_interview(page, expect, website)
    page.locator("#answer").fill(ANSWERS[0])
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("1 of 3 - Follow-up")
    page.locator("#answer").fill("I wrote integration tests before release.")
    page.get_by_role("link", name="Sign out").click()
    modal = page.locator("#interview-exit-modal")
    expect(modal).to_be_visible()
    modal.get_by_role("button", name="Save and leave").click()
    page.wait_for_url("**/sign-in.html")
    sign_in(page)
    page.wait_for_url("**/dashboard.html")
    page.goto(website + "/storage.html")
    page.get_by_role("link", name="Continue", exact=True).click()
    expect(page.locator("#question-badge")).to_have_text("2 of 3")
    page.locator("#prev-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("1 of 3 - Follow-up")
    expect(page.locator("#answer")).to_have_value("I wrote integration tests before release.")


def test_second_question_can_require_follow_up_and_save_retry(browser_page, website, monkeypatch):
    from assistant import interview_follow_up
    def select_second(question, answer, previous):
        if answer == ANSWERS[1]:
            return {"quote": "regression test", "question": "What did your regression test verify?"}
        return None
    monkeypatch.setattr(interview_follow_up, "generate", select_second)
    page, expect = browser_page
    start_interview(page, expect, website)
    page.locator("#answer").fill(ANSWERS[0])
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("2 of 3")
    page.locator("#answer").fill(ANSWERS[1])
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-text")).to_contain_text("What did your regression test verify?")
    expect(page.locator("#question-badge")).to_have_text("2 of 3 - Follow-up")
    page.locator("#answer").fill("It verified invalid requests return 400.")
    page.route("**/follow-up/answer", lambda route: route.fulfill(status=503, json={"error": {"code": "storage_unavailable", "message": "Try again"}}))
    page.locator("#next-question-btn").click()
    expect(page.locator("#interview-answer-error")).to_be_visible()
    expect(page.locator("#answer")).to_have_value("It verified invalid requests return 400.")
    expect(page.locator("#question-badge")).to_have_text("2 of 3 - Follow-up")
    page.unroute("**/follow-up/answer")
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("3 of 3")


def test_slow_selection_times_out_without_late_question_popup(browser_page, website, monkeypatch):
    from assistant import interview_follow_up
    release = threading.Event()
    def delayed(*args):
        assert release.wait(20)
        return {"quote": "Python API", "question": "How did you verify it?"}
    monkeypatch.setattr(interview_follow_up, "generate", delayed)
    page, expect = browser_page
    page.add_init_script("""
        const timeout = window.setTimeout.bind(window);
        window.setTimeout = (fn, ms, ...args) => timeout(fn, ms === 15000 ? 700 : ms, ...args);
    """)
    try:
        start_interview(page, expect, website)
        page.locator("#answer").fill(ANSWERS[0])
        page.locator("#next-question-btn").click()
        expect(page.locator("#answer-status")).to_have_text("Checking your answer...")
        expect(page.locator("#next-question-btn")).to_be_disabled()
        expect(page.locator("#question-badge")).to_have_text("2 of 3")
        release.set()
        page.locator("#answer").fill("Draft after the slow decision.")
        api_url = website + "/api/interviews/" + page.url.split("?id=")[1]
        state = page.request.get(api_url, headers={"Authorization": "Bearer playtest-token"}).json()
        assert state["follow_up"]["status"] == "skipped"
        expect(page.locator("#question-badge")).to_have_text("2 of 3")
        expect(page.locator("#answer")).to_have_value("Draft after the slow decision.")
    finally:
        release.set()


def test_lost_follow_up_response_retries_without_duplicate_grading(browser_page, website, monkeypatch):
    from assistant import interview_follow_up
    monkeypatch.setattr(interview_follow_up, "generate", select_first)
    grade = MockInterviewAI.grade_answer
    calls = []
    def count_grades(ai, *args):
        calls.append(args[-1])
        return grade(ai, *args)
    monkeypatch.setattr(MockInterviewAI, "grade_answer", count_grades)
    page, expect = browser_page
    start_interview(page, expect, website)
    page.locator("#answer").fill(ANSWERS[0])
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("1 of 3 - Follow-up")
    page.locator("#answer").fill("I added six integration tests.")
    pending = []
    page.route("**/follow-up/answer", lambda route: pending.append(route))
    page.locator("#next-question-btn").click()
    expect(page.locator("#next-question-btn")).to_be_disabled()
    page.locator("#next-question-btn").dispatch_event("click")
    assert len(pending) == 1
    assert pending[0].fetch().ok
    pending[0].abort("internetdisconnected")
    expect(page.locator("#next-question-btn")).to_be_enabled()
    expect(page.locator("#answer")).to_have_value("I added six integration tests.")
    page.unroute("**/follow-up/answer")
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("2 of 3")
    assert len(calls) == 2  # One original grade, one combined grade, no replay grade.


def test_other_tab_invalidating_follow_up_cannot_replace_main_answer(browser_page, website, monkeypatch):
    from assistant import interview_follow_up
    monkeypatch.setattr(interview_follow_up, "generate", select_first)
    page, expect = browser_page
    start_interview(page, expect, website)
    page.locator("#answer").fill(ANSWERS[0])
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("1 of 3 - Follow-up")
    page.locator("#answer").fill("Keep this clarification draft in this tab.")
    api_url = website + "/api/interviews/" + page.url.split("?id=")[1]
    headers = {"Authorization": "Bearer playtest-token"}
    state = page.request.get(api_url, headers=headers).json()
    changed = page.request.post(api_url + "/progress", headers=headers, data={
        "revision": state["revision"], "current_question": 0, "answers": ["Main edited in another tab"]})
    assert changed.ok
    page.locator("#next-question-btn").click()
    expect(page.locator("#interview-answer-error")).to_be_visible()
    expect(page.locator("#question-badge")).to_have_text("1 of 3")
    expect(page.locator("#answer")).to_have_value("Main edited in another tab")
    assert page.request.get(api_url, headers=headers).json()["answers"][0]["text"] == "Main edited in another tab"
