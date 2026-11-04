"""HTTP Server for Render backend & local Yourin Web UI (`ui/`).

Only handles server startup (`0.0.0.0:$PORT` on Render, `127.0.0.1:8000` locally),
CORS headers for Vercel, `/api/health`, `/api/config`, and `/api/answer`.
No database schema or tables are assumed yet.
"""
from __future__ import annotations

from dataclasses import asdict
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import webbrowser

from assistant.ai import answer
from assistant.db import get_env_config, get_public_config

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
    """Serves static files from `ui/` and handles `/api/*` JSON requests with CORS."""

    def __init__(self, *args: Any, directory: str | Path = UI_DIR, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(directory), **kwargs)

    def end_headers(self) -> None:
        cors_origin = os.environ.get("CORS_ORIGIN", "*")
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            cfg = get_env_config()
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "supabase_configured": cfg.supabase_configured,
                    "jwks_configured": cfg.jwks_configured,
                    "llm_configured": cfg.llm_configured,
                },
            )
            return

        if parsed.path == "/api/config":
            self._send_json(HTTPStatus.OK, get_public_config())
            return

        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/answer":
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

    def _send_json(self, status: int, data: Any) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_ui(
    host: str | None = None,
    port: int | None = None,
    *,
    open_browser: bool | None = None,
    ui_dir: Path = UI_DIR,
) -> int:
    """Start the HTTP server for Render (`0.0.0.0:$PORT`) or local development."""
    is_render = bool(os.environ.get("RENDER") or os.environ.get("PORT"))
    resolved_host = host or os.environ.get("HOST", "0.0.0.0" if is_render else "127.0.0.1")
    resolved_port = port or int(os.environ.get("PORT", "8000"))
    should_open_browser = (not is_render) if open_browser is None else open_browser

    if not ui_dir.exists():
        raise FileNotFoundError(f"UI directory not found: {ui_dir}")

    handler = partial(AssistantUIRequestHandler, directory=ui_dir)
    with ThreadingHTTPServer((resolved_host, resolved_port), handler) as httpd:
        display_host = "127.0.0.1" if resolved_host == "0.0.0.0" else resolved_host
        url = f"http://{display_host}:{resolved_port}/"
        print(f"Serving Yourin API & UI from {ui_dir} on {resolved_host}:{resolved_port} ({url})")
        print("Press Ctrl+C to stop.")
        if should_open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(serve_ui())
