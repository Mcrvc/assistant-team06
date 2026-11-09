"""Supabase access-token verification for the team's existing browser Auth flow."""
from __future__ import annotations

from urllib.parse import urlsplit
from uuid import UUID
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from assistant.db import AppEnvConfig, _is_real_value
from assistant.interviews import InterviewError


class _NoAuthRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SupabaseUserAuth:
    """Ask Supabase to validate the browser's existing access token.

    No passwords, login endpoints, token issuance or browser session changes.
    Identity comes only from GET /auth/v1/user, never from browser user JSON.
    """

    def __init__(self, project_url: str, publishable_key: str) -> None:
        url = urlsplit(project_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/")):
            raise ValueError("Supabase project must be a trusted HTTPS origin")
        self.user_url = project_url.rstrip("/") + "/auth/v1/user"
        self._publishable_key = publishable_key
        self._opener = build_opener(_NoAuthRedirect())

    @classmethod
    def from_config(cls, config: AppEnvConfig) -> SupabaseUserAuth | None:
        if not (_is_real_value(config.supabase_url)
                and _is_real_value(config.supabase_publishable_key)):
            return None
        return cls(config.supabase_url, config.supabase_publishable_key)

    def authenticate(self, authorization: str) -> str:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or len(parts[1]) > 16000:
            raise InterviewError(401, "authentication_required", "Sign in first")
        if any(ord(c) < 33 or ord(c) > 126 for c in parts[1]):
            raise InterviewError(401, "invalid_access_token", "Sign in again")
        request = Request(self.user_url, headers={
            "Authorization": "Bearer " + parts[1],
            "apikey": self._publishable_key,
            "Accept": "application/json",
        })
        try:
            with self._opener.open(request, timeout=5) as response:
                if response.status != 200:
                    raise ValueError("Unexpected Auth response")
                payload = json.loads(response.read(65537))
            if (not isinstance(payload, dict) or payload.get("role") != "authenticated"
                    or not isinstance(payload.get("id"), str)):
                raise ValueError("Invalid Auth user")
            return str(UUID(payload["id"]))
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if status in (401, 403):
                raise InterviewError(401, "invalid_access_token", "Sign in again") from None
            raise InterviewError(503, "authentication_unavailable", "Cannot check sign-in; retry later") from None
        except (URLError, OSError, ValueError, TypeError):
            raise InterviewError(503, "authentication_unavailable", "Cannot check sign-in; retry later") from None
