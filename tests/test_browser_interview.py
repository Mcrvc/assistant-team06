"""Real browser + real local HTTP server; no cloud accounts, keys or real CVs."""
import os
import socket
import threading
import time

import pytest
import uvicorn

from assistant.api import create_app
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewService


@pytest.fixture
def running_app(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERVIEW_AI_PROVIDER", "mock")
    repository = SQLAlchemyInterviewRepository.local(tmp_path / "browser.sqlite")
    app = create_app(service=InterviewService(repository), demo_enabled=True)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(100)
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", proxy_headers=False))
    worker = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    worker.start()
    deadline = time.monotonic() + 5
    while not server.started and worker.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    try:
        yield base, app
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        sock.close()
        repository.close()


@pytest.fixture
def browser_page():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as engine:
        # Use installed Chrome by default; CI may set YOURIN_TEST_BROWSER=chromium
        # after `python -m playwright install chromium`.
        channel = os.environ.get("YOURIN_TEST_BROWSER", "chrome")
        browser = engine.chromium.launch(channel=channel, headless=True)
        context = browser.new_context()
        context.route("**/*", lambda route: route.continue_()
                      if route.request.url.startswith("http://127.0.0.1:") else route.abort())
        page = context.new_page()
        page.set_default_timeout(8000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            yield page, context, errors
        finally:
            context.close()
            browser.close()


def ready(page):
    page.wait_for_selector('body[data-app-ready="true"]', state="attached")


def sign_in(page, base):
    page.goto(base + "/app/sign-in.html")
    ready(page)
    page.locator("#username").fill("demo_user")
    page.locator("#password").fill("demo12345")
    page.locator('#sign-in-form [type="submit"]').click()
    page.wait_for_url("**/dashboard.html")
    ready(page)


def create_interview(page, base):
    page.goto(base + "/app/job-profile.html")
    ready(page)
    page.locator("#job-source").fill("Python Backend Intern. Build APIs and write tests with a team.")
    page.locator('#job-form [type="submit"]').click()
    page.wait_for_url("**/interview.html")
    ready(page)


def test_browser_create_interrupt_resume_grade_finalize_and_report(running_app, browser_page):
    base, app = running_app
    page, context, errors = browser_page
    # The entire demo must work with every non-local request blocked.
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
    sign_in(page, base)
    create_interview(page, base)
    assert "Why are you interested" in page.locator("#question-text").inner_text()
    first = "I built an API with my team and wrote tests to verify the result."
    page.locator("#answer").fill(first)
    page.locator("#next-question-btn").click()
    page.wait_for_function("document.querySelector('#answer').value === ''")
    page.locator("#answer").fill("An unfinished draft for the second question.")
    # Explicit Save & Exit awaits the server; no navigation before persistence.
    page.locator('.site-header a[href="dashboard.html"]').first.click()
    page.locator("#exit-modal-confirm-btn").click()
    page.wait_for_url("**/dashboard.html")
    page.goto(base + "/app/interview.html")
    ready(page)
    assert page.locator("#answer").input_value() == "An unfinished draft for the second question."
    second = "I reproduced the data issue, added validation, wrote a regression test and checked the result."
    page.locator("#answer").fill(second)
    page.locator("#next-question-btn").click()
    page.wait_for_function("document.querySelector('#answer').value === ''")
    page.locator("#answer").fill("I clarify the task, build a small example and test edge cases before asking for review.")
    page.locator("#next-question-btn").click()
    page.wait_for_url("**/done-interview.html")
    ready(page)
    page.locator("#interview-name").fill("Browser verified practice")
    page.locator('#done-form [type="submit"]').click()
    page.wait_for_url("**/report.html")
    ready(page)
    assert "Browser verified practice" == page.locator("#report-name").inner_text()
    assert page.locator('[data-report-answer="0"]').inner_text() == first
    assert page.locator('[data-report-answer="1"]').inner_text() == second
    assert "mock/fallback" in page.locator("#report-score").inner_text()
    assert page.locator(".report-evidence").count() == 3
    page.reload()
    ready(page)
    assert "Browser verified practice" == page.locator("#report-name").inner_text()
    assert errors == []


def test_browser_creation_failure_stays_on_form_without_fake_session(running_app, browser_page):
    base, app = running_app
    page, context, errors = browser_page
    sign_in(page, base)
    page.goto(base + "/app/job-profile.html")
    ready(page)
    page.route("**/api/interviews", lambda route: route.fulfill(status=503,
        content_type="application/json", body='{"error":{"code":"test_outage","message":"Temporary test outage"}}'))
    page.locator("#job-source").fill("Python intern: build APIs.")
    page.locator('#job-form [type="submit"]').click()
    page.wait_for_selector("#interview-api-error")
    assert page.url.endswith("job-profile.html")
    assert "Temporary test outage" in page.locator("#interview-api-error").inner_text()
    assert page.evaluate("JSON.parse(localStorage.getItem('yourin-poc-v2:local-demo')).accounts[0].interviews.length") == 0
    assert errors == []


def test_browser_draft_autosave_survives_reload_and_empty_answer_is_blocked(running_app, browser_page):
    base, app = running_app
    page, context, errors = browser_page
    sign_in(page, base)
    create_interview(page, base)
    page.locator("#next-question-btn").click()
    page.wait_for_selector("#interview-api-error")
    assert "Please answer" in page.locator("#interview-api-error").inner_text()
    page.locator("#answer").fill("Draft persisted by the autosave request.")
    page.wait_for_function("JSON.parse(localStorage.getItem('yourin-poc-v2:local-demo')).accounts[0].interviews[0].dirty === false")
    page.reload()
    ready(page)
    assert page.locator("#answer").input_value() == "Draft persisted by the autosave request."
    assert errors == []


def test_browser_fabricated_evidence_blocks_report(running_app, browser_page):
    from assistant.interview_ai import MockInterviewAI
    class FabricatingAI(MockInterviewAI):
        def grade_answer(self, *args):
            return {"score": 9.0, "feedback": "Unverified", "evidence": ["invented quote"],
                    "model": "test-provider", "used_fallback": False}
    base, app = running_app
    app.state.interview_service.ai.provider = FabricatingAI()
    page, context, errors = browser_page
    sign_in(page, base)
    create_interview(page, base)
    for index in range(3):
        page.locator("#answer").fill(f"Answer {index}: I wrote tests and checked the project result.")
        page.locator("#next-question-btn").click()
        if index < 2:
            page.wait_for_function("document.querySelector('#answer').value === ''")
    page.wait_for_url("**/done-interview.html")
    ready(page)
    page.locator('#done-form [type="submit"]').click()
    page.wait_for_selector("#interview-api-error")
    assert "quotation could not be verified" in page.locator("#interview-api-error").inner_text()
    assert page.url.endswith("done-interview.html")
    # The same UI can retry a rejected/lost background task after the provider recovers.
    app.state.interview_service.ai.provider = MockInterviewAI()
    page.locator("#retry-grading-btn").click()
    page.wait_for_function("!document.querySelector('#retry-grading-btn').disabled")
    page.locator('#done-form [type="submit"]').click()
    page.wait_for_url("**/report.html")
    ready(page)
    assert page.locator(".report-evidence").count() == 3
    assert errors == []
