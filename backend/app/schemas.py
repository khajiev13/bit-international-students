from typing import Literal

from pydantic import BaseModel, Field


class ProfessorSummary(BaseModel):
    slug: str
    profile_id: str
    professor_slug: str
    department_slug: str
    department_name: str
    name: str
    title: str | None = None
    school: str | None = None
    research_interests: list[str] = Field(default_factory=list)
    summary: str | None = None
    detail_url: str | None = None


class ProfessorProfile(ProfessorSummary):
    aliases: list[str] = Field(default_factory=list)
    email: str | None = None
    phone: str | None = None
    sections: dict[str, list[str]] = Field(default_factory=dict)
    content: str

    def to_summary(self) -> ProfessorSummary:
        return ProfessorSummary(
            slug=self.slug,
            profile_id=self.profile_id,
            professor_slug=self.professor_slug,
            department_slug=self.department_slug,
            department_name=self.department_name,
            name=self.name,
            title=self.title,
            school=self.school,
            research_interests=self.research_interests,
            summary=self.summary,
            detail_url=self.detail_url,
        )


class DepartmentSummary(BaseModel):
    slug: str
    name: str
    professor_count: int
    index_path: str
    good_for: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    department_count: int
    professor_count: int
    model_configured: bool


class CreateSessionResponse(BaseModel):
    thread_id: str


class ResetSessionResponse(BaseModel):
    thread_id: str
    reset: bool


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class RunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[HistoryMessage] = Field(default_factory=list)


class StreamEvent(BaseModel):
    type: Literal["run_started", "message_delta", "activity", "run_finished", "error"]
    run_id: str | None = None
    thread_id: str | None = None
    delta: str | None = None
    message: str | None = None
    activity: str | None = None
    finish_reason: str | None = None


class QuestionAnswerLogEntry(BaseModel):
    id: int
    thread_id: str
    run_id: str
    question: str
    answer: str
    status: str
    created_at: str
    finished_at: str


class QuestionAnswerLogStats(BaseModel):
    total: int
    completed: int
    error: int
    configuration_error: int


class QuestionAnswerLogResponse(BaseModel):
    stats: QuestionAnswerLogStats
    entries: list[QuestionAnswerLogEntry]
