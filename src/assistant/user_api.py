"""Profile/CV, interview history, report and system-feedback APIs.

Owner: Trương Bảo Anh (tbanh2516-dot). Routes (all need a verified user):

- `GET  /api/cv`                      -> `{cv, cvMode, cvPdf}`; 404 if no CV saved yet
- `PUT  /api/cv`                      -> `{ok: true}`
- `GET  /api/interviews`              -> `{interviews: [summary, ...]}` newest first
- `GET  /api/interviews/{id}/report`  -> `{id, name, report}`; 409 until finalized
- `POST /api/feedback`                -> `{ok: true}` (201)

`build_router(current_user, get_service)` receives the shared dependencies from
`assistant.api.create_app`, so the token check is the team's verified
`get_current_user` and history/report read the same interview store as the
interview lifecycle. Nothing is imported from `assistant.api` (no circular import).

CV and feedback are kept in `InMemoryProfileStore` until the Supabase schema has
columns for them (see PR notes); data is lost on restart.

No `from __future__ import annotations` here: FastAPI must resolve the
`Annotated[..., Depends(...)]` aliases created inside `build_router` at runtime.
"""
from datetime import datetime, timezone
import threading
from typing import Annotated, Any, Callable, Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StringConstraints, model_validator

from assistant.interview_schemas import Contract
from assistant.interviews import InterviewError, InterviewService, progress

CV_FIELDS = 4
# Proposed range; the team still has to confirm it with the survey UI (Khang).
RATING_MIN, RATING_MAX = 1, 5

CvField = Annotated[str, Field(max_length=5000)]
Rating = Annotated[int, Field(ge=RATING_MIN, le=RATING_MAX)]


class CvPdf(Contract):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    # The UI sends a display string such as "120 KB"; a byte count is also accepted.
    size: Annotated[int, Field(ge=0)] | Annotated[str, Field(min_length=1, max_length=50)]
    date: Annotated[str, Field(max_length=100)]


class SaveCv(Contract):
    cv: Annotated[list[CvField], Field(min_length=CV_FIELDS, max_length=CV_FIELDS)]
    cvMode: Literal["text", "pdf"] = "text"
    cvPdf: CvPdf | None = None

    @model_validator(mode="after")
    def pdf_needs_file(self) -> "SaveCv":
        if self.cvMode == "pdf" and self.cvPdf is None:
            raise ValueError("cvPdf is required when cvMode is 'pdf'")
        return self


class SendFeedback(Contract):
    grade_rating: Rating
    quality_rating: Rating
    difficulty: Literal["too_easy", "just_right", "too_hard"] | None = None
    comments: Annotated[str, Field(max_length=2000)] = ""
    would_recommend: bool | None = None
    session_id: Annotated[str, Field(min_length=1, max_length=100)] | None = None


class ProfileStore(Protocol):
    def get_cv(self, user_id: str) -> dict | None: ...
    def save_cv(self, user_id: str, cv: dict) -> None: ...
    def add_feedback(self, user_id: str, feedback: dict) -> None: ...


class InMemoryProfileStore:
    """Thread-safe temporary store for CV and feedback (until Supabase is ready)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.cvs: dict[str, dict] = {}
        self.feedback: list[dict] = []

    def get_cv(self, user_id: str) -> dict | None:
        with self._lock:
            cv = self.cvs.get(user_id)
            return dict(cv) if cv else None

    def save_cv(self, user_id: str, cv: dict) -> None:
        with self._lock:
            self.cvs[user_id] = dict(cv)

    def add_feedback(self, user_id: str, feedback: dict) -> None:
        with self._lock:
            self.feedback.append({**feedback, "user_id": user_id})


def get_profile_store(request: Request) -> ProfileStore:
    store = getattr(request.app.state, "profile_store", None)
    if store is None:
        store = request.app.state.profile_store = InMemoryProfileStore()
    return store


def history_item(interview: dict) -> dict[str, Any]:
    """Short summary for the history list: no questions, answers, CV or report body."""
    return {
        "id": interview["id"],
        "name": interview["name"],
        "status": interview["status"],
        "finished": interview["status"] == "finalized",
        "job_profile": interview["job_profile"],
        "created_at": interview["created_at"],
        "updated_at": interview["updated_at"],
        "progress": progress(interview),
        "has_report": interview.get("report") is not None,
    }


def build_router(current_user: Callable[..., str],
                 get_service: Callable[..., InterviewService]) -> APIRouter:
    router = APIRouter(tags=["Profile & history"])
    User = Annotated[str, Depends(current_user)]
    Service = Annotated[InterviewService, Depends(get_service)]
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

    @router.get("/api/interviews")
    def list_interviews(user: User, service: Service):
        return {"interviews": [history_item(item) for item in service.list(user)]}

    @router.get("/api/interviews/{interview_id}/report")
    def read_report(interview_id: UUID, user: User, service: Service):
        interview = service.get(user, str(interview_id))  # 404 for unknown/other users
        if interview["status"] != "finalized" or interview.get("report") is None:
            raise InterviewError(409, "report_not_ready", "Finish the interview to see its report")
        return {"id": interview["id"], "name": interview["name"], "report": interview["report"]}

    @router.post("/api/feedback", status_code=201)
    def send_feedback(payload: SendFeedback, user: User, store: Store):
        record = {**payload.model_dump(), "created": datetime.now(timezone.utc).isoformat()}
        store.add_feedback(user, record)
        return JSONResponse(status_code=201, content={"ok": True})

    return router
