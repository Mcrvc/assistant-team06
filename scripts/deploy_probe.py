"""Timing probe: is the deployed Render AI provider actually being called?"""
from __future__ import annotations

import json
import os
import time
import urllib.request

API_BASE = os.environ.get("PROBE_API_BASE", "https://assistant-team06.onrender.com")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qutiahnegjzgbxjopsqe.supabase.co")
PUBLISHABLE = os.environ.get("PROBE_PUBLISHABLE_KEY", "sb_publishable_3CaHUdWGntAdBjsyxxVE0g_rFt9oWz7")


def http(url, method="GET", body=None, headers=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    if data:
        request.add_header("Content-Type", "application/json")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), time.monotonic() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), time.monotonic() - started


def main() -> int:
    status, payload, seconds = http(f"{API_BASE}/api/health")
    print(f"health ({seconds:.2f}s): {payload.decode(errors='replace')}")

    status, payload, _ = http(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        method="POST",
        body={"email": os.environ["PROBE_EMAIL"], "password": os.environ["PROBE_PASSWORD"]},
        headers={"apikey": PUBLISHABLE},
    )
    token = json.loads(payload)["access_token"]
    print("signed in")

    for attempt in range(3):
        body = {
            "job_profile": {
                "title": "Backend Engineer",
                "domain": "fintech",
                "company": "Yourin",
                "level": "junior",
                "description": "Build payment APIs with Python and FastAPI, write tests, mentor interns.",
            },
            "cv": "Backend intern with FastAPI and PostgreSQL experience; built a payment service.",
            "name": f"timing probe {attempt}",
        }
        status, payload, seconds = http(
            f"{API_BASE}/api/interviews",
            method="POST",
            body=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        created = json.loads(payload)
        print(f"create #{attempt}: http {status} in {seconds:.2f}s -> "
              f"questions={created.get('total_questions')} "
              f"generation={created.get('question_generation')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())