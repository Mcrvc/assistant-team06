"""Pydantic contracts for HTTP requests, responses and the AI provider."""
from __future__ import annotations

from typing import Annotated, Literal
import math
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
AnswerText = Annotated[str, Field(max_length=20000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class JobProfile(Contract):
    title: str = Field(default="", max_length=200)
    domain: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    level: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=20000)

    @model_validator(mode="after")
    def has_role(self) -> JobProfile:
        if not self.title.strip() and not self.description.strip():
            raise ValueError("Job profile needs a title or description")
        return self


class CreateInterview(Contract):
    job_profile: JobProfile
    cv: str | None = Field(default=None, max_length=40000)
    name: ShortText = "New Interview"


class Reference(Contract):
    title: ShortText
    locator: str = Field(min_length=1, max_length=2000)
    excerpt: str = Field(min_length=1, max_length=8000)


class RubricCriterion(Contract):
    name: ShortText
    points: float = Field(gt=0, le=10, allow_inf_nan=False)
    good: str = Field(min_length=1, max_length=2000)


class Rubric(Contract):
    max_score: float = Field(default=10.0, ge=10, le=10)
    criteria: list[RubricCriterion] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def total_matches(self) -> Rubric:
        if not math.isclose(sum(c.points for c in self.criteria), self.max_score):
            raise ValueError("Rubric criteria points must sum to 10")
        return self


class Question(Contract):
    text: str = Field(min_length=1, max_length=4000)
    source_type: Literal["open", "reference"]
    reference: Reference | None = None
    criteria: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(min_length=1, max_length=6)
    rubric: Rubric | None = None

    @model_validator(mode="after")
    def source_matches(self) -> Question:
        if (self.source_type == "reference") != (self.reference is not None):
            raise ValueError("A reference question needs reference metadata; an open question has none")
        if not self.text.strip() or any(not c.strip() for c in self.criteria):
            raise ValueError("Question and criteria must not be blank")
        return self


class Generation(Contract):
    questions: list[Question] = Field(min_length=3, max_length=3)
    model: ShortText
    used_fallback: bool


class Grade(Contract):
    score: float = Field(ge=0, le=10, allow_inf_nan=False)
    feedback: str = Field(min_length=1, max_length=8000)
    evidence: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(min_length=1, max_length=6)
    model: ShortText
    used_fallback: bool


class VersionedRequest(Contract):
    revision: int = Field(ge=0)


class SaveProgress(VersionedRequest):
    current_question: int = Field(ge=0, le=2)
    status: Literal["in_progress", "interrupted"] = "in_progress"
    answers: list[AnswerText] | None = Field(default=None, min_length=3, max_length=3)


class SubmitAnswer(VersionedRequest):
    text: AnswerText

    @model_validator(mode="after")
    def nonempty(self) -> SubmitAnswer:
        if not self.text.strip():
            raise ValueError("Answer must not be blank")
        return self


class FinalizeInterview(VersionedRequest):
    name: ShortText | None = None


class AnswerState(Contract):
    text: AnswerText
    grading_status: Literal["unanswered", "draft", "pending", "graded", "rejected"]
    grading_id: str | None = None
    grade: Grade | None = None
    error_code: str | None = None


class Progress(Contract):
    total: int
    answered: int
    graded: int
    pending: int
    rejected: int


class ReportItem(Contract):
    question_index: int
    question: Question
    answer: str
    score: float
    feedback: str
    evidence: list[str]
    label: Literal["Good", "Needs Improvement"]
    model: str
    used_fallback: bool


class Report(Contract):
    overall_score: float
    label: Literal["Good", "Needs Improvement"]
    items: list[ReportItem]
    used_fallback: bool
    notice: str


class InterviewView(Contract):
    id: str
    name: str
    job_profile: JobProfile
    cv: str | None
    questions: list[Question]
    question_generation: dict[str, str | bool]
    answers: list[AnswerState]
    current_question: int
    status: Literal["in_progress", "interrupted", "finalized"]
    report: Report | None
    revision: int
    created_at: str
    updated_at: str
    progress: Progress


class CreatedInterview(Contract):
    id: str
    revision: int
    status: str
    total_questions: int
    current_question: int
    question: Question
    question_generation: dict[str, str | bool]
