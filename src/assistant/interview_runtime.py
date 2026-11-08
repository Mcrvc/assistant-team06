"""Select an interview repository without implicit cloud access or schema writes."""
from __future__ import annotations

import os
from pathlib import Path

from assistant.interview_postgres import PostgresInterviewRepository
from assistant.interview_store import SQLAlchemyInterviewRepository

REPO_ROOT = Path(__file__).resolve().parents[2]


def configured_repository(*, demo_enabled: bool):
    storage = os.environ.get("INTERVIEW_STORAGE", "auto").strip().lower()
    if storage not in ("auto", "postgres"):
        raise ValueError("INTERVIEW_STORAGE must be auto or postgres")
    if storage == "postgres":
        if demo_enabled:
            raise ValueError("PostgreSQL requires real authentication; disable interview demo")
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise ValueError("DATABASE_URL is required for PostgreSQL interview storage")
        try:
            return PostgresInterviewRepository.connect(url)
        except ImportError:
            raise ValueError("Install the project's postgres extra before using PostgreSQL") from None
    if demo_enabled or os.environ.get("INTERVIEW_LOCAL_STORAGE") == "1":
        path = Path(os.environ.get("INTERVIEW_DB_PATH", "data/private/interviews.sqlite"))
        if not path.is_absolute():
            path = REPO_ROOT / path
        return SQLAlchemyInterviewRepository.local(path)
    return None
