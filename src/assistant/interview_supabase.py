"""Interview persistence over Supabase Data API, without a direct DB connection.

The reviewed RPC proposal performs each multi-table write in one transaction.
No runtime DDL, retries of ambiguous writes, or silent local fallback.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from assistant.auth import _NoAuthRedirect
from assistant.db import AppEnvConfig, _is_real_value
from assistant.interview_store import StoreConflict


class SupabaseInterviewRepository:
    def __init__(self, project_url: str, secret_key: str) -> None:
        url = urlsplit(project_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/")):
            raise ValueError("Supabase storage requires a trusted HTTPS project origin")
        if not _is_real_value(secret_key) or secret_key.startswith("sb_publishable_"):
            raise ValueError("Supabase storage requires a backend secret key")
        self._url = project_url.rstrip("/") + "/rest/v1/rpc/yourin_interview_v1"
        self._secret_key = secret_key
        self._opener = build_opener(_NoAuthRedirect())

    @classmethod
    def connect(cls, config: AppEnvConfig) -> SupabaseInterviewRepository:
        if not _is_real_value(config.supabase_url):
            raise ValueError("SUPABASE_URL is required for Supabase interview storage")
        repo = cls(config.supabase_url, config.supabase_secret_key)
        if repo._call("check") != {"schema_version": 1}:
            raise SQLAlchemyError("Supabase interview API schema is not ready")
        return repo

    def _call(self, operation: str, owner: str | None = None, interview_id: str | None = None,
              item: dict | None = None, expected_version: int | None = None):
        headers = {"apikey": self._secret_key, "Content-Type": "application/json"}
        # Modern secret API keys are not JWTs and must not be sent as Bearer JWTs.
        if not self._secret_key.startswith("sb_secret_"):
            headers["Authorization"] = "Bearer " + self._secret_key
        body = {"p_operation": operation, "p_owner": owner, "p_id": interview_id,
                "p_item": item, "p_expected_version": expected_version}
        request = Request(self._url, data=json.dumps(body, allow_nan=False).encode(), headers=headers)
        try:
            with self._opener.open(request, timeout=10) as response:
                if response.status != 200:
                    raise ValueError("Unexpected storage response")
                raw = response.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise ValueError("Storage response too large")
                return json.loads(raw)
        except HTTPError as exc:
            # Inspect only bounded error codes; never expose cloud response bodies.
            try:
                error = json.loads(exc.read(4096))
            except (ValueError, OSError):
                error = {}
            status = exc.code
            exc.close()
            if status == 409 and isinstance(error, dict) and error.get("code") == "PT409":
                raise StoreConflict() from None
            raise SQLAlchemyError("Supabase interview storage unavailable or RPC not installed") from None
        except (URLError, OSError, ValueError, TypeError):
            raise SQLAlchemyError("Supabase interview storage unavailable") from None

    def create(self, interview: dict) -> None:
        self._call("create", str(UUID(interview["owner_id"])), interview["id"], interview)

    def get(self, interview_id: str, owner_id: str) -> dict | None:
        result = self._call("get", str(UUID(owner_id)), interview_id)
        if result is not None and (not isinstance(result, dict)
                or result.get("owner_id") != owner_id or result.get("id") != interview_id):
            raise SQLAlchemyError("Invalid Supabase interview response")
        return result

    def list_for_owner(self, owner_id: str) -> list[dict]:
        result = self._call("list", str(UUID(owner_id)))
        if not isinstance(result, list) or any(not isinstance(item, dict)
                or item.get("owner_id") != owner_id for item in result):
            raise SQLAlchemyError("Invalid Supabase interview history response")
        return result

    def save(self, interview: dict, expected_version: int) -> None:
        self._call("save", str(UUID(interview["owner_id"])), interview["id"], interview, expected_version)

    def delete(self, interview_id: str, owner_id: str) -> None:
        self._call("delete", str(UUID(owner_id)), interview_id)

    def close(self) -> None:
        pass
