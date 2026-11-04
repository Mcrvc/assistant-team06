"""Environment configuration and connection check for Supabase + LLM."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"

PLACEHOLDER_PREFIXES = ("fake_", "faeke_", "_insert_", "insert_")


def load_env_file(path: Path = ENV_PATH) -> None:
    """Load key=value pairs from local `.env` into `os.environ` if not already set."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def _is_real_value(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned:
        return False
    lower = cleaned.lower()
    return not any(lower.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


@dataclass(frozen=True)
class AppEnvConfig:
    """Holds the environment variables declared in `.env.example`."""

    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str
    supabase_jwks_url: str
    llm_api_key: str = ""

    @property
    def supabase_configured(self) -> bool:
        return (
            _is_real_value(self.supabase_url)
            and _is_real_value(self.supabase_publishable_key)
            and _is_real_value(self.supabase_secret_key)
        )

    @property
    def jwks_configured(self) -> bool:
        return _is_real_value(self.supabase_jwks_url)

    @property
    def llm_configured(self) -> bool:
        return _is_real_value(self.llm_api_key)


def get_env_config() -> AppEnvConfig:
    """Read environment variables from Render/OS or local `.env`."""
    load_env_file()
    return AppEnvConfig(
        supabase_url=os.environ.get("SUPABASE_URL", "").strip().rstrip("/"),
        supabase_publishable_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip(),
        supabase_secret_key=os.environ.get("SUPABASE_SECRET_KEY", "").strip(),
        supabase_jwks_url=os.environ.get("SUPABASE_JWKS_URL", "").strip(),
        llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
    )


def get_public_config() -> dict[str, Any]:
    """Return only public-safe config for the frontend (never exposes secret keys)."""
    cfg = get_env_config()
    return {
        "supabaseConfigured": cfg.supabase_configured,
        "supabaseUrl": cfg.supabase_url if _is_real_value(cfg.supabase_url) else "",
        "supabasePublishableKey": (
            cfg.supabase_publishable_key
            if _is_real_value(cfg.supabase_publishable_key)
            else ""
        ),
        "jwksConfigured": cfg.jwks_configured,
        "llmConfigured": cfg.llm_configured,
    }
