"""Compatibility entry point: both launch commands use the same Yourin ASGI app.

From backend/: uvicorn app.main:app --host 127.0.0.1 --port 8000
From repo root: python -m assistant --interview-api
"""
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from assistant.api import app  # noqa: E402,F401
