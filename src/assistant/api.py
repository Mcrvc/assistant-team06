"""FastAPI interview API. Local demo auth is opt-in; production auth is a seam."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hmac
import ipaddress
import os
from pathlib import Path
import secrets
from typing import Annotated, Callable
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, Path as ApiPath, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from assistant.db import get_env_config, get_public_config, load_env_file
from assistant.auth import SupabaseBearerAuth
from assistant.interview_schemas import (
    CreatedInterview, CreateInterview, FinalizeInterview, InterviewView,
    Progress, SaveProgress, SubmitAnswer,
)
from assistant.interview_runtime import configured_repository
from assistant.interviews import InterviewError, InterviewService, progress, public_view
from assistant.web import handle_api_answer

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_COOKIE = "yourin_demo_session"


def _loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _check_local(request: Request) -> None:
    if (not request.client or not _loopback(request.client.host)
            or not _loopback(request.url.hostname or "")):
        raise InterviewError(403, "local_only", "Demo sessions are available only on localhost")
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise InterviewError(403, "origin_denied", "Demo requests must come from the same origin")


def get_current_user(request: Request) -> str:
    """Replace auth_resolver with the Auth teammate's verified cookie lookup.

    Never accept owner_id/user_id from request JSON or an unverified token.
    Argon2id password verification belongs to real sign-in, not interview routes.
    """
    resolver = request.app.state.auth_resolver
    if resolver is not None:
        user = resolver(request)
        if not isinstance(user, str) or not user.strip() or len(user) > 200:
            raise InterviewError(401, "authentication_required", "Sign in first")
        return user
    verifier = request.app.state.token_auth
    if verifier is not None:
        return verifier.authenticate(request.headers.get("authorization", ""))
    if not request.app.state.demo_enabled:
        raise InterviewError(503, "auth_not_integrated", "Real session authentication is not integrated")
    _check_local(request)
    cookie = request.cookies.get(DEMO_COOKIE, "")
    if not hmac.compare_digest(cookie.encode(), request.app.state.demo_token.encode()):
        raise InterviewError(401, "authentication_required", "Create a local demo session first")
    return "local-demo"


def get_service(request: Request) -> InterviewService:
    service = request.app.state.interview_service
    if service is None:
        raise InterviewError(503, "backend_not_configured", "Interview storage is not configured")
    return service


User = Annotated[str, Depends(get_current_user)]
Service = Annotated[InterviewService, Depends(get_service)]
QuestionIndex = Annotated[int, ApiPath(ge=0, le=2)]


def create_app(*, service: InterviewService | None = None,
               demo_enabled: bool | None = None,
               auth_resolver: Callable[[Request], str] | None = None,
               token_auth: SupabaseBearerAuth | None = None) -> FastAPI:
    load_env_file()
    enabled = (os.environ.get("INTERVIEW_DEMO_ENABLED") == "1"
               if demo_enabled is None else demo_enabled)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned_store = None
        try:
            if app.state.interview_service is None:
                owned_store = configured_repository(demo_enabled=enabled)
                if owned_store is not None:
                    app.state.interview_service = InterviewService(owned_store)
            yield
        finally:
            if owned_store:
                owned_store.close()
                app.state.interview_service = None

    app = FastAPI(title="Yourin Interview Backend", version="0.1.0", lifespan=lifespan)
    app.state.interview_service = service
    app.state.demo_enabled = enabled
    app.state.demo_token = secrets.token_urlsafe(32)
    app.state.auth_resolver = auth_resolver
    app.state.token_auth = (token_auth or SupabaseBearerAuth.from_config(get_env_config())
                           if not enabled and auth_resolver is None else None)
    origins = [origin.strip() for origin in os.environ.get("CORS_ORIGIN", "").split(",")
               if origin.strip() and origin.strip() != "*"]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Content-Type", "Authorization"])

    @app.exception_handler(InterviewError)
    async def interview_error(request: Request, exc: InterviewError):
        return JSONResponse(status_code=exc.status, content={
            "error": {"code": exc.code, "message": exc.message},
        })

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Avoid echoing answers, CVs or cookie contents in validation errors.
        details = [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=400, content={
            "error": {"code": "invalid_request", "message": "Invalid request data", "details": details},
        })

    @app.exception_handler(SQLAlchemyError)
    async def storage_error(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content={
            "error": {"code": "storage_unavailable", "message": "Interview storage is unavailable; retry later"},
        })

    @app.post("/api/demo/session", tags=["Local demo"])
    def demo_session(request: Request, response: Response):
        if not enabled:
            raise InterviewError(404, "not_found", "Local demo is disabled")
        _check_local(request)
        response.set_cookie(DEMO_COOKIE, app.state.demo_token, httponly=True,
                            samesite="strict", secure=False, max_age=8 * 60 * 60)
        return {"user": "local-demo", "mode": "local-demo", "real_auth": False}

    @app.get("/api/demo/session", tags=["Local demo"])
    def read_demo_session(request: Request):
        if not enabled:
            raise InterviewError(404, "not_found", "Local demo is disabled")
        get_current_user(request)
        return {"id": "local-demo", "user_metadata": {"username": "Local Demo"}}

    @app.post("/api/demo/logout", tags=["Local demo"])
    def end_demo_session(request: Request, response: Response):
        if not enabled:
            raise InterviewError(404, "not_found", "Local demo is disabled")
        _check_local(request)
        response.delete_cookie(DEMO_COOKIE)
        return {"ok": True}

    @app.get("/api/health", tags=["Existing API"])
    def health():
        cfg = get_env_config()
        return {"status": "ok", "supabase_configured": cfg.supabase_configured,
                "jwks_configured": cfg.jwks_configured, "llm_configured": cfg.llm_configured,
                "interview_demo_enabled": enabled}

    @app.get("/api/config", tags=["Existing API"])
    def config():
        return {**get_public_config(), "interviewDemoEnabled": enabled,
                "interviewAuthMode": "demo" if enabled else "supabase",
                "interviewCvEnabled": enabled or os.environ.get("INTERVIEW_ALLOW_CV_TO_AI") == "1"}

    @app.post("/api/answer", tags=["Existing API"])
    def legacy_answer(payload: dict):
        status, result = handle_api_answer(payload)
        return JSONResponse(status_code=status, content=result)

    @app.post("/api/interviews", response_model=CreatedInterview, status_code=201, tags=["Interviews"])
    def create_interview(payload: CreateInterview, user: User, service: Service):
        item = service.create(user, payload)
        return {"id": item["id"], "revision": item["revision"], "status": item["status"],
                "total_questions": 3, "current_question": 0, "question": item["questions"][0],
                "question_generation": item["question_generation"]}

    @app.get("/api/interviews/{interview_id}", response_model=InterviewView, tags=["Interviews"])
    def resume_interview(interview_id: UUID, user: User, service: Service):
        return public_view(service.get(user, str(interview_id)))

    @app.post("/api/interviews/{interview_id}/progress", response_model=InterviewView, tags=["Interviews"])
    def save_progress(interview_id: UUID, payload: SaveProgress, user: User, service: Service):
        return public_view(service.save_progress(user, str(interview_id), payload))

    @app.post("/api/interviews/{interview_id}/answers/{index}", response_model=InterviewView,
              status_code=202, tags=["Interviews"])
    def submit_answer(interview_id: UUID, index: QuestionIndex, payload: SubmitAnswer,
                      tasks: BackgroundTasks, user: User, service: Service):
        item, grading_id = service.submit_answer(user, str(interview_id), index, payload)
        tasks.add_task(service.grade_answer, user, str(interview_id), index, grading_id)
        return public_view(item)

    @app.get("/api/interviews/{interview_id}/progress", response_model=Progress, tags=["Interviews"])
    def read_progress(interview_id: UUID, user: User, service: Service):
        return progress(service.get(user, str(interview_id)))

    @app.post("/api/interviews/{interview_id}/finalize", response_model=InterviewView, tags=["Interviews"])
    def finalize_interview(interview_id: UUID, payload: FinalizeInterview, user: User, service: Service):
        return public_view(service.finalize(user, str(interview_id), payload))

    # API paths must never fall through to a static HTML error page.
    @app.api_route("/api/{unknown:path}", methods=["GET", "POST"], include_in_schema=False)
    def unknown_api(unknown: str):
        raise InterviewError(404, "not_found", "API endpoint not found")

    app.mount("/app", StaticFiles(directory=REPO_ROOT / "frontend", html=True), name="team_frontend")
    app.mount("/prototype", StaticFiles(directory=REPO_ROOT / "ui", html=True), name="prototype")
    app.mount("/", StaticFiles(directory=REPO_ROOT / "ui", html=True), name="ui")
    return app


def serve_api(port: int | None = None) -> int:
    import uvicorn
    load_env_file()
    enabled = os.environ.get("INTERVIEW_DEMO_ENABLED") == "1"
    host = os.environ.get("HOST", "127.0.0.1")
    if enabled and not _loopback(host):
        raise ValueError("Local demo must bind to localhost; real auth is not integrated")
    uvicorn.run(create_app(), host=host, port=port or int(os.environ.get("PORT", "8000")),
                proxy_headers=False)
    return 0


app = create_app()
