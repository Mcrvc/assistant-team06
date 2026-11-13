"""Tests run without developer credentials or external network access."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import OpenerDirector

import pytest

DEFAULTS = {
    "SUPABASE_URL": "", "SUPABASE_PUBLISHABLE_KEY": "", "SUPABASE_SECRET_KEY": "",
    "INTERVIEW_STORAGE": "auto", "INTERVIEW_LOCAL_STORAGE": "0",
    "INTERVIEW_AI_PROVIDER": "mock", "INTERVIEW_ALLOW_CV_TO_AI": "0",
    "NVIDIA_API_KEY": "", "LLM_API_KEY": "", "TINYFISH_API_KEY": "",
}
os.environ.update(DEFAULTS)


@pytest.fixture(autouse=True)
def isolate_environment_and_network(monkeypatch):
    import assistant
    assert Path(assistant.__file__).resolve().is_relative_to(Path(__file__).resolve().parents[1] / "src")
    for key, value in DEFAULTS.items():
        monkeypatch.setenv(key, value)
    # Tests may delete an env var to test the unconfigured case. Do not let
    # create_app/get_env_config restore it from the developer's real .env.
    from assistant import db, web
    monkeypatch.setattr(db, "load_env_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(web, "load_env_file", lambda *args, **kwargs: None)
    original = OpenerDirector.open
    def local_only(self, fullurl, *args, **kwargs):
        url = fullurl.full_url if hasattr(fullurl, "full_url") else fullurl
        if urlsplit(url).hostname not in ("127.0.0.1", "localhost", "::1"):
            raise AssertionError("Backend tests must not contact external services")
        return original(self, fullurl, *args, **kwargs)
    monkeypatch.setattr(OpenerDirector, "open", local_only)
