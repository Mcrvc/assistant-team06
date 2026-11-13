"""Profile CV and system-feedback APIs (Trương Bảo Anh, tbanh2516-dot).

Routes, all behind the team's verified `get_current_user`:

- `GET  /api/cv`        -> `{cv, cvMode, cvPdf}`; 404 `cv_not_found` if nothing saved
- `PUT  /api/cv`        -> `{ok: true}`; writes `accounts.cv / cv_mode / cv_pdf`
- `POST /api/feedback`  -> 201 `{ok: true}`; inserts one row into `feedback`

Feedback contract agreed with Frontend (Khang, 09/11): `grade_rating` and
`quality_rating` 1–5, `difficulty` easy/medium/hard, `comments` text,
`would_recommend` true/false. Ratings are required; the other fields are optional.

Storage follows the interview storage switch in `interview_runtime.py`:
`INTERVIEW_STORAGE=supabase` -> Supabase Data API with the server-side secret key;
`INTERVIEW_LOCAL_STORAGE=1` -> in-memory (local runs/tests); otherwise 503.
History and reports are already served by the interview routes in `web.py`.

No `from __future__ import annotations`: FastAPI must resolve the
`Annotated[..., Depends(...)]` aliases created inside `build_router` at runtime.
"""
import json
import os
import threading
from typing import Annotated, Any, Callable, Literal, Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request as UrlRequest, build_opener
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import Field, StringConstraints, model_validator

from assistant.auth import _NoAuthRedirect
from assistant.db import AppEnvConfig, _is_real_value, get_env_config
from assistant.interview_schemas import Contract
from assistant.interviews import InterviewError
from assistant.parsing import MAX_PDF_BYTES, extract_pdf_text

CV_FIELDS = 4
RATING_MIN, RATING_MAX = 1, 5

CvField = Annotated[str, Field(max_length=5000)]
Rating = Annotated[int, Field(ge=RATING_MIN, le=RATING_MAX)]


# ---------------------------------------------------------------- request bodies


class CvPdf(Contract):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    # The UI sends a display string such as "120 KB"; a byte count is also accepted.
    size: Annotated[int, Field(ge=0)] | Annotated[str, Field(min_length=1, max_length=50)]
    date: Annotated[str, Field(max_length=100)]


class SaveCv(Contract):
    cv: Annotated[list[CvField], Field(min_length=CV_FIELDS, max_length=CV_FIELDS)]
    cvMode: Literal["text", "pdf"] = "text"
    cvPdf: Optional[CvPdf] = None

    @model_validator(mode="after")
    def pdf_needs_file(self) -> "SaveCv":
        if self.cvMode == "pdf" and self.cvPdf is None:
            raise ValueError("cvPdf is required when cvMode is 'pdf'")
        return self


class SendFeedback(Contract):
    grade_rating: Rating
    quality_rating: Rating
    difficulty: Optional[Literal["easy", "medium", "hard"]] = None
    comments: Annotated[str, Field(max_length=2000)] = ""
    would_recommend: Optional[bool] = None


# ---------------------------------------------------------------- storage


class ProfileStore(Protocol):
    def get_cv(self, user_id: str) -> Optional[dict]: ...
    def save_cv(self, user_id: str, cv: dict) -> None: ...
    def add_feedback(self, user_id: str, feedback: dict) -> None: ...


class InMemoryProfileStore:
    """Thread-safe store for local runs and tests; data is lost on restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.cvs: dict[str, dict] = {}
        self.feedback: list[dict] = []

    def get_cv(self, user_id: str) -> Optional[dict]:
        with self._lock:
            cv = self.cvs.get(user_id)
            return dict(cv) if cv else None

    def save_cv(self, user_id: str, cv: dict) -> None:
        with self._lock:
            self.cvs[user_id] = dict(cv)

    def add_feedback(self, user_id: str, feedback: dict) -> None:
        with self._lock:
            self.feedback.append({**feedback, "user_id": user_id})


def _storage_error() -> InterviewError:
    # Never echo Supabase response bodies (they may contain CV text).
    return InterviewError(503, "storage_unavailable", "Profile storage is unavailable; retry later")


class SupabaseProfileStore:
    """`accounts` (CV columns) and `feedback` through the Supabase Data API.

    Uses the server-only secret key, so every query filters by the verified
    user id itself. Never creates accounts: the Auth flow owns that row.
    """

    def __init__(self, project_url: str, secret_key: str, *, opener: Any = None) -> None:
        url = urlsplit(project_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/")):
            raise ValueError("Supabase storage requires a trusted HTTPS project origin")
        if not _is_real_value(secret_key) or secret_key.startswith("sb_publishable_"):
            raise ValueError("Supabase storage requires a backend secret key")
        self._rest = project_url.rstrip("/") + "/rest/v1/"
        self._secret_key = secret_key
        self._opener = opener or build_opener(_NoAuthRedirect())

    @classmethod
    def connect(cls, config: AppEnvConfig) -> "SupabaseProfileStore":
        return cls(config.supabase_url, config.supabase_secret_key)

    def _send(self, method: str, path: str, body: Optional[dict] = None,
              prefer: Optional[str] = None) -> Any:
        headers = {"apikey": self._secret_key, "Accept": "application/json"}
        # Modern secret API keys are not JWTs and must not be sent as Bearer JWTs.
        if not self._secret_key.startswith("sb_secret_"):
            headers["Authorization"] = "Bearer " + self._secret_key
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, allow_nan=False).encode()
        if prefer:
            headers["Prefer"] = prefer
        request = UrlRequest(self._rest + path, data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=10) as response:
                if response.status not in (200, 201, 204):
                    raise ValueError("Unexpected storage response")
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("Storage response too large")
            return json.loads(raw) if raw.strip() else None
        except HTTPError as exc:
            exc.close()
            raise _storage_error() from None
        except (URLError, OSError, ValueError, TypeError):
            raise _storage_error() from None

    @staticmethod
    def _account_filter(user_id: str) -> str:
        return "accounts?id=eq." + quote(str(UUID(user_id)), safe="")

    def get_cv(self, user_id: str) -> Optional[dict]:
        rows = self._send("GET", self._account_filter(user_id) + "&select=cv,cv_mode,cv_pdf")
        if not isinstance(rows, list) or len(rows) > 1:
            raise _storage_error()
        if not rows or rows[0].get("cv") is None:
            return None
        row = rows[0]
        return {"cv": row["cv"], "cvMode": row.get("cv_mode") or "text", "cvPdf": row.get("cv_pdf")}

    def save_cv(self, user_id: str, cv: dict) -> None:
        rows = self._send("PATCH", self._account_filter(user_id) + "&select=id",
                          {"cv": cv["cv"], "cv_mode": cv["cvMode"], "cv_pdf": cv["cvPdf"]},
                          prefer="return=representation")
        if not isinstance(rows, list):
            raise _storage_error()
        if not rows:
            # Sign-up did not create the accounts row; do not invent one here.
            raise InterviewError(409, "account_not_found", "Account profile is not set up yet")

    def add_feedback(self, user_id: str, feedback: dict) -> None:
        self._send("POST", "feedback", {**feedback, "user_id": str(UUID(user_id))},
                   prefer="return=minimal")


def configured_profile_store() -> Optional[ProfileStore]:
    """Same switch as the interview storage, so both always use one backend."""
    storage = os.environ.get("INTERVIEW_STORAGE", "auto").strip().lower()
    if storage == "supabase":
        return SupabaseProfileStore.connect(get_env_config())
    if os.environ.get("INTERVIEW_LOCAL_STORAGE") == "1":
        return InMemoryProfileStore()
    return None


def get_profile_store(request: Request) -> ProfileStore:
    store = getattr(request.app.state, "profile_store", None)
    if store is None:
        raise InterviewError(503, "backend_not_configured", "Profile storage is not configured")
    return store


# ---------------------------------------------------------------- routes


def build_router(current_user: Callable[..., str]) -> APIRouter:
    router = APIRouter(tags=["Profile & feedback"])
    User = Annotated[str, Depends(current_user)]
    Store = Annotated[ProfileStore, Depends(get_profile_store)]

    @router.get("/api/cv")
    def read_cv(user: User, store: Store):
        cv = store.get_cv(user)
        if cv is None:
            raise InterviewError(404, "cv_not_found", "No CV saved yet")
        return cv

    @router.put("/api/cv")
    def save_cv(payload: SaveCv, user: User, store: Store):
        store.save_cv(user, payload.model_dump())
        return {"ok": True}

    @router.post("/api/cv/parse-pdf")
    async def parse_cv_pdf(user: User, file: UploadFile = File(...)):
        _ = user
        data = await file.read(MAX_PDF_BYTES + 1)
        text, truncated = extract_pdf_text(data, max_bytes=MAX_PDF_BYTES)
        return {"text": text, "chars": len(text), "truncated": truncated}

    @router.post("/api/feedback", status_code=201)
    def send_feedback(payload: SendFeedback, user: User, store: Store):
        store.add_feedback(user, payload.model_dump())
        return JSONResponse(status_code=201, content={"ok": True})

    return router
