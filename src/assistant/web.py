"""Canonical Yourin web/API entry point, serving ui/ with FastAPI/Uvicorn."""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from http import HTTPStatus
import os
from pathlib import Path
import threading
import time
import webbrowser
from typing import Annotated, Callable
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, Path as ApiPath, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from assistant.db import get_env_config, get_public_config, load_env_file
from assistant.auth import SupabaseUserAuth
from assistant.interview_schemas import (
    CreatedInterview, CreateInterview, FinalizeInterview, InterviewView,
    Progress, SaveProgress, SubmitAnswer,
)
from assistant.interview_runtime import configured_repository
from assistant.interviews import InterviewError, InterviewService, progress, public_view
from assistant.user_api import ProfileStore, build_router as build_user_router, configured_profile_store
from assistant.ai import answer

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_DIR = REPO_ROOT / "ui"


def handle_api_answer(payload: dict) -> tuple[int, dict]:
    """Preserve the original office-assistant endpoint on the shared server."""
    question = payload.get("question", "")
    if not isinstance(question, str) or not question.strip():
        return HTTPStatus.BAD_REQUEST, {"error": "question must be a non-empty string"}
    return HTTPStatus.OK, asdict(answer(question))


def get_current_user(request: Request) -> str:
    """Resolve identity through Supabase Auth or an injected trusted resolver.

    Never accept owner_id/user_id from request JSON or an unverified token.
    Password verification belongs to the Auth provider, not interview routes.
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
    raise InterviewError(503, "auth_not_configured", "Configure Supabase sign-in before using interviews")


def get_service(request: Request) -> InterviewService:
    service = request.app.state.interview_service
    if service is None:
        raise InterviewError(503, "backend_not_configured", "Interview storage is not configured")
    return service


User = Annotated[str, Depends(get_current_user)]
Service = Annotated[InterviewService, Depends(get_service)]
QuestionIndex = Annotated[int, ApiPath(ge=0, le=2)]


def create_app(*, service: InterviewService | None = None,
               auth_resolver: Callable[[Request], str] | None = None,
               token_auth: SupabaseUserAuth | None = None,
               ui_dir: Path | None = None,
               profile_store: ProfileStore | None = None) -> FastAPI:
    load_env_file()
    ui_root = Path(ui_dir) if ui_dir is not None else UI_DIR

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned_store = None
        owned_profile = False
        try:
            if app.state.interview_service is None:
                owned_store = configured_repository()
                if owned_store is not None:
                    app.state.interview_service = InterviewService(owned_store)
            if app.state.profile_store is None:
                app.state.profile_store = configured_profile_store()
                owned_profile = True
            yield
        finally:
            if owned_store:
                owned_store.close()
                app.state.interview_service = None
            if owned_profile:
                app.state.profile_store = None

    app = FastAPI(title="Yourin Interview Backend", version="0.1.0", lifespan=lifespan)
    app.state.interview_service = service
    app.state.profile_store = profile_store
    app.state.auth_resolver = auth_resolver
    app.state.token_auth = (token_auth or SupabaseUserAuth.from_config(get_env_config())
                           if auth_resolver is None else None)
    origins = [origin.strip() for origin in os.environ.get("CORS_ORIGIN", "").split(",")
               if origin.strip() and origin.strip() != "*"]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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

    @app.get("/api/health", tags=["Existing API"])
    def health():
        cfg = get_env_config()
        return {"status": "ok", "supabase_configured": cfg.supabase_configured,
                "jwks_configured": cfg.jwks_configured, "llm_configured": cfg.llm_configured,
                "interview_storage": os.environ.get("INTERVIEW_STORAGE", "auto")}

    @app.get("/api/config", tags=["Existing API"])
    def config():
        return {**get_public_config(), "interviewDemoEnabled": False,
                "interviewAuthMode": "supabase",
                "interviewCvEnabled": os.environ.get("INTERVIEW_ALLOW_CV_TO_AI") == "1"}

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

    @app.get("/api/interviews", response_model=list[InterviewView], tags=["Interviews"])
    def list_interviews(user: User, service: Service):
        return [public_view(item) for item in service.list(user)]

    @app.get("/api/interviews/{interview_id}", response_model=InterviewView, tags=["Interviews"])
    def resume_interview(interview_id: UUID, user: User, service: Service):
        return public_view(service.get(user, str(interview_id)))

    @app.delete("/api/interviews/{interview_id}", status_code=204, tags=["Interviews"])
    def delete_interview(interview_id: UUID, user: User, service: Service):
        service.delete(user, str(interview_id))
        return None

    @app.post("/api/interviews/{interview_id}/progress", response_model=InterviewView, tags=["Interviews"])
    def save_progress(interview_id: UUID, payload: SaveProgress, user: User, service: Service):
        return public_view(service.save_progress(user, str(interview_id), payload))

    @app.post("/api/interviews/{interview_id}/answers/{index}", response_model=InterviewView,
              status_code=202, tags=["Interviews"])
    def submit_answer(interview_id: UUID, index: QuestionIndex, payload: SubmitAnswer,
                      tasks: BackgroundTasks, user: User, service: Service):
        item, grading_id = service.submit_answer(user, str(interview_id), index, payload)
        if grading_id is not None:
            tasks.add_task(service.grade_answer, user, str(interview_id), index, grading_id)
        return public_view(item)

    @app.get("/api/interviews/{interview_id}/progress", response_model=Progress, tags=["Interviews"])
    def read_progress(interview_id: UUID, user: User, service: Service):
        return progress(service.get(user, str(interview_id)))

    @app.post("/api/interviews/{interview_id}/finalize", response_model=InterviewView, tags=["Interviews"])
    def finalize_interview(interview_id: UUID, payload: FinalizeInterview, user: User, service: Service):
        return public_view(service.finalize(user, str(interview_id), payload))

    # Profile CV + system feedback (Trương Bảo Anh); before the catch-all and static mounts.
    app.include_router(build_user_router(get_current_user))

    # API paths must never fall through to a static HTML error page.
    @app.api_route("/api/{unknown:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
    def unknown_api(unknown: str):
        raise InterviewError(404, "not_found", "API endpoint not found")

    app.mount("/app", StaticFiles(directory=ui_root, html=True), name="team_frontend")
    app.mount("/prototype", StaticFiles(directory=ui_root, html=True), name="prototype")
    app.mount("/", StaticFiles(directory=ui_root, html=True), name="ui")
    return app


def serve_ui(
    host: str | None = None,
    port: int | None = None,
    *,
    open_browser: bool | None = None,
    ui_dir: Path = UI_DIR,
) -> int:
    """Run the complete API and ui/ through the team's existing web command."""
    import uvicorn

    load_env_file()
    is_render = bool(os.environ.get("RENDER") or os.environ.get("PORT"))
    resolved_host = host or os.environ.get("HOST") or ("0.0.0.0" if is_render else "127.0.0.1")
    resolved_port = port if port is not None else int(os.environ.get("PORT", "8000"))
    if not Path(ui_dir).is_dir():
        raise FileNotFoundError(f"UI directory not found: {ui_dir}")

    server = uvicorn.Server(uvicorn.Config(
        create_app(ui_dir=ui_dir), host=resolved_host, port=resolved_port, proxy_headers=False,
    ))
    should_open = not is_render if open_browser is None else open_browser
    finished = threading.Event()
    if should_open and resolved_port != 0:
        display_host = "127.0.0.1" if resolved_host in ("0.0.0.0", "::") else resolved_host
        if ":" in display_host:
            display_host = f"[{display_host}]"
        url = f"http://{display_host}:{resolved_port}/"

        def open_when_ready() -> None:
            deadline = time.monotonic() + 10
            while not server.started:
                if finished.wait(0.05) or time.monotonic() >= deadline:
                    return
            if not finished.is_set():
                webbrowser.open(url)

        threading.Thread(target=open_when_ready, daemon=True).start()
    try:
        server.run()
    finally:
        finished.set()
    return 0 if server.started else 1


def serve_api(port: int | None = None) -> int:
    """Compatibility alias; there is only one web server implementation."""
    return serve_ui(port=port, open_browser=False)


app = create_app()


if __name__ == "__main__":
    raise SystemExit(serve_ui())
