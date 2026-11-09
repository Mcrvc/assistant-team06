"""Explicit Supabase API storage; local SQLite is an opt-in test facility."""
from __future__ import annotations

import os
from pathlib import Path

from assistant.db import get_env_config
from assistant.interview_store import SQLAlchemyInterviewRepository

ROOT = Path(__file__).resolve().parents[2]


def configured_repository():
    storage = os.environ.get("INTERVIEW_STORAGE", "auto").strip().lower()
    if storage not in ("auto", "supabase"):
        raise ValueError("INTERVIEW_STORAGE must be auto or supabase")
    if storage == "supabase":
        from assistant.interview_supabase import SupabaseInterviewRepository
        return SupabaseInterviewRepository.connect(get_env_config())
    if os.environ.get("INTERVIEW_LOCAL_STORAGE") == "1":
        path = Path(os.environ.get("INTERVIEW_DB_PATH", "data/private/interviews.sqlite"))
        return SQLAlchemyInterviewRepository.local(path if path.is_absolute() else ROOT / path)
    return None
