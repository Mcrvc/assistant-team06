"""Local HTTP server for the Yourin Web UI (`ui/`) and `/api/answer` endpoint."""
from __future__ import annotations

from dataclasses import asdict
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
import webbrowser

from assistant.ai import answer

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_DIR = REPO_ROOT / "ui"


def handle_api_answer(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Process a JSON payload for `/api/answer` and return `(status_code, body)`."""
    question = payload.get("question", "")
    if not isinstance(question, str) or not question.strip():
        return HTTPStatus.BAD_REQUEST, {"error": "question must be a non-empty string"}

    result = answer(question)
    return HTTPStatus.OK, asdict(result)


class AssistantUIRequestHandler(SimpleHTTPRequestHandler):
    """Serves static files from `ui/` and handles `/api/*` JSON requests."""

    def __init__(self, *args: Any, directory: str | Path = UI_DIR, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(directory), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "ui_dir": str(UI_DIR.name)})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/answer":
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON body must be an object")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            status, response_body = handle_api_answer(payload)
            self._send_json(status, response_body)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_ui(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    open_browser: bool = True,
    ui_dir: Path = UI_DIR,
) -> int:
    """Start the local web server serving `ui/`."""
    if not ui_dir.exists():
        raise FileNotFoundError(f"UI directory not found: {ui_dir}")

    handler = partial(AssistantUIRequestHandler, directory=ui_dir)
    with ThreadingHTTPServer((host, port), handler) as httpd:
        url = f"http://{host}:{port}/"
        print(f"Serving Yourin UI from {ui_dir} at {url}")
        print("Press Ctrl+C to stop.")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down UI server.")
    return 0
