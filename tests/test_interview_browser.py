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
def browser_page(website):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as engine:
        browser = engine.chromium.launch(channel=os.environ.get("YOURIN_TEST_BROWSER", "chrome"))
        context = browser.new_context()

        def route_request(route):
            url = route.request.url
            if url.startswith(website + "/"):
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
    page.wait_for_url("**/interview.html?id=*")
    expect(page.locator("#question-badge")).to_have_text("1 of 3")
    expect(page.locator("#answer")).to_be_editable()


def test_playtest_interview_report_and_history(browser_page, website):
    page, expect = browser_page
    start_interview(page, expect, website)
    for index, answer in enumerate(ANSWERS):
        expect(page.locator("#question-badge")).to_have_text(f"{index + 1} of 3")
        if index == 2:
            page.locator("#next-question-btn").click()
            expect(page.locator("#interview-answer-error")).to_be_visible()
            expect(page.locator("#question-badge")).to_have_text("3 of 3")
        page.locator("#answer").fill(answer)
        page.locator("#next-question-btn").click()
    page.wait_for_url("**/done-interview.html")
    page.locator("#interview-name").fill("Playtest report")
    page.locator('#done-form button[type="submit"]').click()
    page.wait_for_url("**/report.html")
    expect(page.locator("#report-name")).to_have_text("Playtest report")
    for answer in ANSWERS:
        expect(page.locator("#report-cards")).to_contain_text(answer)
    page.goto(website + "/storage.html")
    expect(page.get_by_text("Playtest report")).to_be_visible()
    page.get_by_role("link", name="View report").click()
    expect(page.locator("#report-name")).to_have_text("Playtest report")


def test_next_requires_answer_and_stays_on_failed_submission(browser_page, website):
    page, expect = browser_page
    start_interview(page, expect, website)
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("1 of 3")
    expect(page.locator("#answer")).to_be_focused()
    page.locator("#answer").fill(ANSWERS[0])
    page.route("**/api/interviews/*/answers/0", lambda route: route.fulfill(
        status=503, json={"error": {"message": "Test save unavailable"}}))
    with page.expect_response(lambda response: response.url.endswith("/answers/0")):
        page.locator("#next-question-btn").click()
    expect(page.get_by_text("Test save unavailable").first).to_be_visible()
    expect(page.locator("#question-badge")).to_have_text("1 of 3")
    expect(page.locator("#answer")).to_have_value(ANSWERS[0])
    page.unroute("**/api/interviews/*/answers/0")
    page.locator("#next-question-btn").click()
    expect(page.locator("#question-badge")).to_have_text("2 of 3")


def test_exit_waits_for_confirmed_save_and_allows_retry(browser_page, website):
    page, expect = browser_page
    start_interview(page, expect, website)
    page.locator("#answer").fill("Unsaved playtest draft.")
    attempts = []

    def fail_save(route):
        if route.request.method == "POST":
            attempts.append(route.request.url)
            route.fulfill(status=503, json={"error": {"message": "Test exit save failed"}})
        else:
            route.continue_()

    page.route("**/api/interviews/*/progress", fail_save)
    page.locator('.site-header a[data-nav="storage"]').click()
    modal = page.locator("#interview-exit-modal")
    expect(modal).to_be_visible()
    assert not attempts
    confirm = page.locator("#exit-modal-confirm-btn")
    with page.expect_response(lambda response: response.url.endswith("/progress")):
        confirm.click()
    expect(modal.get_by_role("alert")).to_be_visible()
    expect(page).to_have_url(re.compile(r"interview\.html\?id="))
    expect(page.locator("#answer")).to_have_value("Unsaved playtest draft.")
    page.unroute("**/api/interviews/*/progress")
    confirm.click()
    page.wait_for_url("**/storage.html")
    page.get_by_role("link", name="Continue", exact=True).click()
    expect(page.locator("#answer")).to_have_value("Unsaved playtest draft.")


def test_sign_out_saves_before_ending_session(browser_page, website):
    page, expect = browser_page
    start_interview(page, expect, website)
    page.locator("#answer").fill("Keep this answer when signing out.")
    page.get_by_role("link", name="Sign out").click()
    modal = page.locator("#interview-exit-modal")
    expect(modal).to_be_visible()
    modal.get_by_role("button", name="Keep answering").click()
    expect(modal).to_be_hidden()
    expect(page.locator("#answer")).to_have_value("Keep this answer when signing out.")
    page.get_by_role("link", name="Sign out").click()
    with page.expect_response(lambda response: response.url.endswith("/progress")) as progress:
        modal.get_by_role("button", name="Save and leave").click()
    assert progress.value.status == 200
    page.wait_for_url("**/sign-in.html")
    page.goto(website + "/storage.html")
    page.wait_for_url("**/sign-in.html")
    sign_in(page)
    page.wait_for_url("**/storage.html")
    page.get_by_role("link", name="Continue", exact=True).click()
    expect(page.locator("#answer")).to_have_value("Keep this answer when signing out.")
