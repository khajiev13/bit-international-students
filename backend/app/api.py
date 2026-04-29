from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.corpus import DepartmentNotFoundError, ProfessorNotFoundError
from app.schemas import (
    CreateSessionResponse,
    HealthResponse,
    QuestionAnswerLogResponse,
    ReadyResponse,
    ResetSessionResponse,
    RunRequest,
)


security = HTTPBasic(auto_error=False)


def require_admin(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> None:
    settings = request.app.state.settings
    if not settings.admin_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin credentials are not configured.",
        )
    if credentials is None:
        raise _admin_auth_error()

    expected_username = settings.admin_username or ""
    expected_password = settings.admin_password.get_secret_value() if settings.admin_password else ""
    username_matches = secrets.compare_digest(credentials.username, expected_username)
    password_matches = secrets.compare_digest(credentials.password, expected_password)
    if not (username_matches and password_matches):
        raise _admin_auth_error()


def _admin_auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin credentials are required.",
        headers={"WWW-Authenticate": "Basic"},
    )


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.get("/readyz", response_model=ReadyResponse)
    def readyz(request: Request) -> ReadyResponse:
        return ReadyResponse(
            status="ready",
            department_count=request.app.state.corpus.department_count,
            professor_count=request.app.state.corpus.count,
            model_configured=request.app.state.settings.model_configured,
        )

    @router.get("/api/departments")
    def list_departments(request: Request) -> list[dict]:
        return [department.model_dump() for department in request.app.state.corpus.list_departments()]

    @router.get("/api/departments/{department_slug}/index")
    def get_department_index(department_slug: str, request: Request) -> dict:
        try:
            return request.app.state.corpus.get_department_index(department_slug)
        except DepartmentNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Department not found.") from exc

    @router.get("/api/professors")
    def list_professors(request: Request, department_slug: str | None = None) -> list[dict]:
        try:
            summaries = request.app.state.corpus.list_professors(department_slug=department_slug)
        except DepartmentNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Department not found.") from exc
        return [summary.model_dump() for summary in summaries]

    @router.get("/api/professors/{profile_id:path}")
    def get_professor(profile_id: str, request: Request) -> dict:
        try:
            return request.app.state.corpus.get_profile(profile_id).model_dump()
        except ProfessorNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Professor profile not found.") from exc

    @router.post("/api/sessions", response_model=CreateSessionResponse)
    def create_session(request: Request) -> CreateSessionResponse:
        thread_id = request.app.state.agent_service.sessions.create()
        return CreateSessionResponse(thread_id=thread_id)

    @router.post("/api/sessions/{thread_id}/runs/stream")
    def stream_run(thread_id: str, payload: RunRequest, request: Request) -> StreamingResponse:
        if len(payload.message) > request.app.state.settings.max_prompt_chars:
            raise HTTPException(status_code=413, detail="Prompt is too long.")
        request.app.state.agent_service.sessions.ensure(thread_id)
        events = request.app.state.agent_service.stream_run(
            thread_id=thread_id,
            message=payload.message,
            history=payload.history,
        )
        return StreamingResponse(events, media_type="application/x-ndjson")

    @router.post("/api/sessions/{thread_id}/reset", response_model=ResetSessionResponse)
    def reset_session(thread_id: str, request: Request) -> ResetSessionResponse:
        request.app.state.agent_service.sessions.reset(thread_id)
        return ResetSessionResponse(thread_id=thread_id, reset=True)

    @router.get("/api/admin/question-answer-log", response_model=QuestionAnswerLogResponse)
    def get_question_answer_log(
        request: Request,
        _: Annotated[None, Depends(require_admin)],
        limit: int = Query(default=50, ge=1, le=500),
    ) -> QuestionAnswerLogResponse:
        return QuestionAnswerLogResponse(
            stats=request.app.state.question_answer_log.summary(),
            entries=request.app.state.question_answer_log.list_recent(limit=limit),
        )

    return router
