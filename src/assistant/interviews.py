"""Persistent lifecycle with per-answer grading, evidence checks and ownership."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Callable, Protocol
from uuid import uuid4
from assistant.interview_ai import GradeRejected, InterviewAI, SafeInterviewAI, configured_ai
from assistant.interview_schemas import CreateInterview, FinalizeInterview, SaveProgress, SubmitAnswer
from assistant.interview_store import StoreConflict

logger = logging.getLogger(__name__)


class InterviewError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class InterviewRepository(Protocol):
    def create(self, interview: dict) -> None: ...
    def get(self, interview_id: str, owner_id: str) -> dict | None: ...
    def save(self, interview: dict, expected_version: int) -> None: ...
    def delete(self, interview_id: str, owner_id: str) -> None: ...
    def list_for_owner(self, owner_id: str) -> list[dict]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _answer(text: str = "") -> dict:
    return {"text": text, "grading_status": "draft" if text.strip() else "unanswered",
            "grading_id": None, "grade": None, "error_code": None}


def progress(interview: dict) -> dict:
    answers = interview["answers"]
    return {"total": 3, "answered": sum(bool(a["text"].strip()) for a in answers),
            **{status: sum(a["grading_status"] == status for a in answers)
               for status in ("graded", "pending", "rejected")}}


def public_view(interview: dict) -> dict:
    return {**{k: v for k, v in interview.items() if k not in ("owner_id", "version")},
            "progress": progress(interview)}


class InterviewService:
    def __init__(self, repository: InterviewRepository, ai: InterviewAI | None = None) -> None:
        self.repository = repository
        self.ai = SafeInterviewAI(ai if ai is not None else configured_ai())

    def create(self, owner_id: str, request: CreateInterview) -> dict:
        generated = self.ai.generate_questions(request.job_profile.model_dump(), request.cv)
        now = _now()
        interview = {
            "id": str(uuid4()), "owner_id": owner_id, "name": request.name,
            "job_profile": request.job_profile.model_dump(), "cv": request.cv,
            "questions": generated["questions"],
            "question_generation": {k: generated[k] for k in ("model", "used_fallback")},
            "answers": [_answer() for _ in range(3)], "current_question": 0,
            "status": "in_progress", "report": None, "revision": 0, "version": 0,
            "created_at": now, "updated_at": now,
        }
        self.repository.create(interview)
        return interview

    def get(self, owner_id: str, interview_id: str) -> dict:
        interview = self.repository.get(interview_id, owner_id)
        if interview is None:
            raise InterviewError(404, "not_found", "Interview not found")
        return interview

    def list(self, owner_id: str) -> list[dict]:
        """Shared storage seam for Trương's history router; no history route here."""
        return self.repository.list_for_owner(owner_id)

    def _change(self, owner_id: str, interview_id: str, revision: int,
                change: Callable[[dict], None]) -> dict:
        # Background grades change internal version, but not client revision.
        for _ in range(10):
            interview = self.get(owner_id, interview_id)
            if interview["status"] == "finalized":
                raise InterviewError(409, "already_finalized", "A finalized interview cannot be edited")
            if interview["revision"] != revision:
                raise InterviewError(409, "revision_conflict", "Interview changed; reload before saving")
            change(interview)
            expected = interview["version"]
            interview.update(revision=revision + 1, version=expected + 1, updated_at=_now())
            try:
                self.repository.save(interview, expected)
                return interview
            except StoreConflict:
                continue
        raise InterviewError(409, "revision_conflict", "Interview is busy; reload before saving")

    def save_progress(self, owner_id: str, interview_id: str, request: SaveProgress) -> dict:
        def change(interview: dict) -> None:
            if request.answers is not None:
                for i, text in enumerate(request.answers):
                    if text != interview["answers"][i]["text"]:
                        interview["answers"][i] = _answer(text)
            interview.update(current_question=request.current_question, status=request.status)
        return self._change(owner_id, interview_id, request.revision, change)

    def submit_answer(self, owner_id: str, interview_id: str, index: int,
                      request: SubmitAnswer) -> tuple[dict, str]:
        if index not in range(3):
            raise InterviewError(400, "invalid_question", "Question index must be 0, 1 or 2")
        grading_id = str(uuid4())

        def change(interview: dict) -> None:
            interview["answers"][index] = {
                **_answer(request.text), "grading_status": "pending", "grading_id": grading_id,
            }
            interview.update(current_question=min(index + 1, 2), status="in_progress")
        result = self._change(owner_id, interview_id, request.revision, change)
        return result, grading_id

    def grade_answer(self, owner_id: str, interview_id: str, index: int, grading_id: str) -> None:
        """Background task; never applies results to an edited/superseded answer."""
        try:
            self._grade_answer(owner_id, interview_id, index, grading_id)
        except Exception:
            # A process crash/DB outage leaves a durable pending answer. Re-submit
            # to retry; BackgroundTasks is not a durable job queue.
            logger.error("Interview grading did not finish; re-submit pending answer to retry")

    def _grade_answer(self, owner_id: str, interview_id: str, index: int, grading_id: str) -> None:
        interview = self.get(owner_id, interview_id)
        answer = interview["answers"][index]
        if answer["grading_id"] != grading_id or answer["grading_status"] != "pending":
            return
        try:
            grade = self.ai.grade_answer(interview["job_profile"], interview["questions"][index], answer["text"])
            grounded = all(quote.strip() and quote in answer["text"] for quote in grade["evidence"])
            rejection_code = "evidence_not_found"
        except GradeRejected as exc:
            grade, grounded, rejection_code = None, False, exc.code
        for _ in range(10):
            current = self.get(owner_id, interview_id)
            target = current["answers"][index]
            if (current["status"] == "finalized" or target["grading_id"] != grading_id
                    or target["grading_status"] != "pending"):
                return
            target.update(grading_status="graded" if grounded else "rejected",
                          grade=grade if grounded else None,
                          error_code=None if grounded else rejection_code)
            expected = current["version"]
            current.update(version=expected + 1, updated_at=_now())
            try:
                self.repository.save(current, expected)
                return
            except StoreConflict:
                continue
        logger.error("Interview grading update was busy; re-submit pending answer to retry")

    def finalize(self, owner_id: str, interview_id: str, request: FinalizeInterview) -> dict:
        current = self.get(owner_id, interview_id)
        if current["status"] == "finalized":
            if request.name is not None and request.name != current["name"]:
                raise InterviewError(409, "already_finalized", "A finalized interview cannot be renamed here")
            return current

        def change(interview: dict) -> None:
            counts = progress(interview)
            if counts["answered"] != 3:
                raise InterviewError(400, "answers_required", "All 3 answers are required")
            if counts["graded"] != 3:
                raise InterviewError(409, "grading_incomplete", "Wait for grading or re-submit draft/rejected/pending answers")
            items = []
            for i, answer in enumerate(interview["answers"]):
                grade = answer["grade"]
                items.append({"question_index": i, "question": interview["questions"][i],
                              "answer": answer["text"], **grade,
                              "label": "Good" if grade["score"] >= 6 else "Needs Improvement"})
            overall = round(sum(item["score"] for item in items) / 3, 2)
            used_fallback = (interview["question_generation"]["used_fallback"]
                             or any(item["used_fallback"] for item in items))
            interview.update(
                name=request.name or interview["name"], status="finalized", current_question=2,
                report={"overall_score": overall, "items": items, "used_fallback": used_fallback,
                        "label": "Good" if overall >= 6 else "Needs Improvement",
                        "notice": "Contains mock/fallback output; not a real AI assessment."
                        if used_fallback else "Evidence quotations passed exact text matching."},
            )
        return self._change(owner_id, interview_id, request.revision, change)
