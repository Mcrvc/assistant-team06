"""Exercise the local HTTP lifecycle without changing the team's frontend.

Start the API first, then: python scripts/demo_interview.py
Uses fake CV/answers, never requires API keys. Database rows are retained.
"""
from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler, Request


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    url = urlsplit(base)
    if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("This walkthrough is only for a local HTTP demo server")
    opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))

    def call(method: str, path: str, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(base + path, data=data, method=method,
                          headers={"Content-Type": "application/json"})
        with opener.open(request, timeout=30) as response:
            return response.status, json.load(response)

    try:
        call("POST", "/api/demo/session")
        status, created = call("POST", "/api/interviews", {
            "name": "Local backend walkthrough", "job_profile": {
                "title": "Python Backend Intern", "domain": "Software", "company": "Example",
                "level": "Intern", "description": "Build and test Python APIs.",
            }, "cv": "Demo CV: I study Python and have built a small class project.",
        })
        path = f'/api/interviews/{created["id"]}'
        print(f'CREATE {status}: interview {created["id"]}; 3 questions with criteria')
        _, saved = call("POST", path + "/progress", {
            "revision": created["revision"], "current_question": 0,
            "status": "interrupted", "answers": ["My unfinished draft", "", ""],
        })
        _, saved = call("GET", path)
        assert saved["status"] == "interrupted" and saved["answers"][0]["text"] == "My unfinished draft"
        print("SAVE / RESUME: draft and question position persisted")
        answers = [
            "I built a small Python API with my team, wrote tests and fixed a bug before our demo.",
            "A project had inconsistent data. I reproduced the error, validated inputs and added a regression test.",
            "I first clarify the task, build a small example, test edge cases and ask for review of the result.",
        ]
        revision = saved["revision"]
        for index, answer in enumerate(answers):
            status, item = call("POST", path + f"/answers/{index}", {"revision": revision, "text": answer})
            assert status == 202
            revision = item["revision"]
            print(f"ANSWER {index + 1}: HTTP 202; grading scheduled after response")
        deadline = time.monotonic() + 15
        while True:
            _, counts = call("GET", path + "/progress")
            if counts["graded"] == 3:
                break
            if counts["rejected"] or time.monotonic() >= deadline:
                raise RuntimeError("Grading incomplete; inspect the interview and re-submit pending/rejected answers")
            time.sleep(0.1)
        print("PROGRESS: 3 answered / 3 graded; evidence quotations checked")
        _, completed = call("POST", path + "/finalize", {"revision": revision})
        _, retry = call("POST", path + "/finalize", {"revision": revision})
        assert completed["status"] == "finalized" and retry["report"] == completed["report"]
        assert completed["report"]["used_fallback"] is True
        print(f'FINALIZE: mock score {completed["report"]["overall_score"]}/10; retry returns same report')
        print("MOCK ONLY: this run proves the backend flow, not real AI quality or cloud integration.")
        return 0
    except HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, OSError, RuntimeError) as exc:
        print(f"Demo did not complete: {exc}")
        print("Start the local API with INTERVIEW_DEMO_ENABLED=1; see docs/interview-api.md.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
