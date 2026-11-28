"""Persistent lifecycle with per-answer grading, evidence checks and ownership."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Callable, Protocol
from uuid import uuid4
from assistant.interview_ai import (
    GradeRejected, InterviewAI, InvalidJobProfile, SafeInterviewAI, configured_ai,
)
from assistant.interview_schemas import (
    CreateInterview, FinalizeInterview, Question, SaveProgress, SubmitAnswer,
    StartFollowUp, FollowUpAction, FollowUpAnswer,
)
from assistant.interview_store import StoreConflict
from assistant import interview_follow_up

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
    return {"total": len(answers), "answered": sum(bool(a["text"].strip()) for a in answers),
            **{status: sum(a["grading_status"] == status for a in answers)
               for status in ("graded", "pending", "rejected")}}


def public_view(interview: dict) -> dict:
    return {**{k: v for k, v in interview.items() if k not in ("owner_id", "version")},
            "progress": progress(interview)}


def follow_ups(item: dict) -> list[dict]:
    if "follow_ups" not in item:
        legacy = item.get("follow_up")
        item["follow_ups"] = [legacy] if legacy else []
    return item["follow_ups"]


def invalidate_follow_up(item: dict, index: int) -> None:
    for follow in follow_ups(item):
        if follow["parent_index"] == index and follow["status"] != "invalidated":
            follow["selected"] = bool(follow.get("selected") or follow["status"] in ("ready", "answered"))
            follow["status"] = "invalidated"
    item["follow_up"] = next((f for f in reversed(follow_ups(item))
                               if f["status"] != "invalidated"), None)


def selected_follow_up_count(item: dict) -> int:
    return sum(bool(f.get("selected") or f["status"] in ("ready", "answered"))
               for f in follow_ups(item))


def new_follow_up(item: dict, index: int, *, automatic: bool) -> dict:
    selected = selected_follow_up_count(item)
    already_selected = any(f["parent_index"] == index and f.get("selected") for f in follow_ups(item))
    follow = {"parent_index": index, "parent_grading_id": item["answers"][index]["grading_id"],
              "request_id": str(uuid4()), "started_at": _now(), "automatic": automatic,
              "selected": False, "status": "generating" if selected < 2 and not already_selected else "not_needed",
              "quote": "", "question": "", "answer": ""}
    follow_ups(item).append(follow)
    item["follow_up"] = follow
    return follow


class InterviewService:
    def __init__(self, repository: InterviewRepository, ai: InterviewAI | None = None) -> None:
        self.repository = repository
        self.ai = SafeInterviewAI(ai if ai is not None else configured_ai())

    def create(self, owner_id: str, request: CreateInterview) -> dict:
        from assistant.parsing import parse_job_profile
        parsed_job = parse_job_profile(request.job_profile)
        job_profile = parsed_job.model_dump()
        try:
            generated = self._questions_for(job_profile, request.cv)
        except InvalidJobProfile as exc:
            # A refusal is not a server error: tell the candidate to retry
            # with a different job description and do not store anything.
            raise InterviewError(422, exc.code, exc.message) from None
        now = _now()
        interview = {
            "id": str(uuid4()), "owner_id": owner_id, "name": request.name,
            "job_profile": job_profile, "cv": request.cv,
            "questions": generated["questions"], "follow_ups": [], "follow_up": None,
            "question_generation": {k: generated[k] for k in ("model", "used_fallback")},
            "answers": [_answer() for _ in generated["questions"]], "current_question": 0,
            "status": "in_progress", "report": None, "revision": 0, "version": 0,
            "created_at": now, "updated_at": now,
        }
        self.repository.create(interview)
        return interview

    def _questions_for(self, job_profile: dict, cv: str | None) -> dict:
        """Questions for one interview: bank first when enabled, provider otherwise.

        The bank is opt-in and optional. Any problem reading it falls back to
        the provider, so an interview always gets its questions. When the bank
        supplies questions, the provider's job-validity gate still runs so
        invalid or illegal job profiles are refused consistently.
        """
        bank_questions = self._bank_questions(job_profile)
        if bank_questions is not None:
            self.ai.validate_job_profile(job_profile)
            return {"questions": bank_questions, "model": "question-bank", "used_fallback": False}
        return self.ai.generate_questions(job_profile, cv)

    @staticmethod
    def _bank_questions(job_profile: dict) -> list[dict] | None:
        try:
            from assistant.question_bank import draw_questions
            questions = draw_questions(job_profile)
        except Exception:
            return None
        # The bank decides how many questions it can serve (INTERVIEW_BANK_LIMIT),
        # the same way the provider decides how many it plans.
        if not questions:
            return None
        try:
            return [Question.model_validate(question).model_dump() for question in questions]
        except Exception:
            return None

    def get(self, owner_id: str, interview_id: str) -> dict:
        interview = self.repository.get(interview_id, owner_id)
        if interview is None:
            raise InterviewError(404, "not_found", "Interview not found")
        entries = follow_ups(interview)
        changed = False
        if interview["status"] != "finalized":
            for follow in entries:
                if follow["status"] == "generating" and interview_follow_up.expired(follow):
                    follow["status"] = "unavailable"
                    changed = True
        interview["follow_up"] = next((f for f in reversed(entries) if f["status"] != "invalidated"), None)
        if changed:
            version = interview["version"]
            interview.update(version=version + 1, updated_at=_now())
            try:
                self.repository.save(interview, version)
            except StoreConflict:
                fresh = self.repository.get(interview_id, owner_id)
                if fresh is None:
                    raise InterviewError(404, "not_found", "Interview not found")
                return fresh
        return interview

    def list(self, owner_id: str) -> list[dict]:
        """Shared storage seam for Trương's history router; no history route here."""
        return self.repository.list_for_owner(owner_id)

    def delete(self, owner_id: str, interview_id: str) -> None:
        self.get(owner_id, interview_id)
        self.repository.delete(interview_id, owner_id)

    def start_follow_up(self, owner_id: str, interview_id: str,
                        request: StartFollowUp) -> tuple[dict, str | None]:
        request_id = str(uuid4())

        def already_applied(item):
            follow = next((f for f in reversed(follow_ups(item))
                           if f["parent_grading_id"] == request.parent_grading_id
                           and f["parent_index"] == request.parent_index
                           and f["status"] != "invalidated"), None)
            return bool(follow and follow["parent_grading_id"] == request.parent_grading_id
                        and follow["status"] != "unavailable"
                        and not (follow["status"] == "generating" and interview_follow_up.expired(follow)))

        def change(item):
            index = request.parent_index
            if index >= len(item["answers"]):
                raise InterviewError(400, "invalid_question", "Question index is outside this interview")
            parent = item["answers"][index]
            if not parent["grading_id"] or parent["grading_id"] != request.parent_grading_id:
                raise InterviewError(409, "parent_changed", "Submit this answer before continuing")
            if already_applied(item):
                raise InterviewError(409, "follow_up_exists", "This follow-up decision already exists")
            invalidate_follow_up(item, index)
            follow = new_follow_up(item, index, automatic=True)
            follow["request_id"] = request_id

        # A current-revision replay also reuses the existing question.
        current = self.get(owner_id, interview_id)
        if current["status"] != "finalized" and current["revision"] == request.revision and already_applied(current):
            return current, None
        item = self._change(owner_id, interview_id, request.revision, change, already_applied=already_applied)
        return item, request_id if item["follow_up"]["request_id"] == request_id else None

    def generate_follow_up(self, owner_id: str, interview_id: str, request_id: str) -> None:
        try:
            item = self.get(owner_id, interview_id)
            follow = next((f for f in follow_ups(item) if f["request_id"] == request_id), None)
            if not follow or follow["request_id"] != request_id or follow["status"] != "generating":
                return
            try:
                index = follow["parent_index"]
                previous = [{"question": f["question"], "answer": f["answer"]}
                            for f in follow_ups(item) if f.get("selected")]
                result = interview_follow_up.generate(item["questions"][index], item["answers"][index]["text"], previous)
                outcome = "ready" if result else "not_needed"
            except Exception:
                result, outcome = None, "unavailable"
            for _ in range(10):
                current = self.get(owner_id, interview_id)
                target = next((f for f in follow_ups(current) if f["request_id"] == request_id), None)
                if (current["status"] == "finalized" or not target or target["request_id"] != request_id
                        or target["status"] != "generating"
                        or current["answers"][target["parent_index"]]["grading_id"] != target["parent_grading_id"]):
                    return
                selected = selected_follow_up_count(current)
                if outcome == "ready" and selected >= 2:
                    result, outcome = None, "not_needed"
                target.update(result or {})
                target["status"] = outcome
                target["selected"] = outcome == "ready"
                if outcome != "ready" and current["current_question"] == target["parent_index"]:
                    current["current_question"] = min(target["parent_index"] + 1, len(current["questions"]) - 1)
                current["follow_up"] = next((f for f in reversed(follow_ups(current)) if f["status"] != "invalidated"), None)
                version = current["version"]
                current.update(version=version + 1, updated_at=_now())
                try:
                    self.repository.save(current, version)
                    return
                except StoreConflict:
                    continue
        except Exception:
            logger.error("Follow-up generation did not finish; retry after the request expires")

    def finish_follow_up(self, owner_id: str, interview_id: str,
                         request: FollowUpAction | FollowUpAnswer, *, skip: bool = False) -> tuple[dict, str | None]:
        status = "skipped" if skip else "answered"
        grading_id = str(uuid4())

        def already_applied(item):
            follow = next((f for f in follow_ups(item) if f["request_id"] == request.request_id), None)
            return bool(follow and follow["request_id"] == request.request_id
                        and follow["status"] == status
                        and (skip or follow["answer"] == request.text))

        def change(item):
            follow = next((f for f in follow_ups(item) if f["request_id"] == request.request_id), None)
            if skip and follow and follow.get("automatic") and follow["status"] == "ready":
                raise InterviewError(409, "follow_up_required", "Answer the follow-up before continuing")
            allowed = ("generating", "ready", "unavailable") if skip else ("ready",)
            if not follow or follow["request_id"] != request.request_id or follow["status"] not in allowed:
                raise InterviewError(409, "follow_up_changed", "Reload the practice question before saving")
            follow["status"] = status
            if item["current_question"] == follow["parent_index"]:
                item["current_question"] = min(follow["parent_index"] + 1, len(item["questions"]) - 1)
            if not skip:
                follow["answer"] = request.text
                # Supersede the original grading job atomically with saving the
                # clarification. Keep the main text and rubric unchanged.
                follow["parent_grading_id"] = grading_id
                item["answers"][follow["parent_index"]].update(
                    grading_id=grading_id, grading_status="pending", grade=None, error_code=None)
            item["follow_up"] = next((f for f in reversed(follow_ups(item)) if f["status"] != "invalidated"), None)

        current = self.get(owner_id, interview_id)
        if current["revision"] == request.revision and already_applied(current):
            return current, None
        result = self._change(owner_id, interview_id, request.revision, change, already_applied=already_applied)
        follow = next(f for f in follow_ups(result) if f["request_id"] == request.request_id)
        return result, grading_id if not skip and follow["parent_grading_id"] == grading_id else None

    def retry_follow_up_grade(self, owner_id: str, interview_id: str,
                              request: FollowUpAction) -> tuple[dict, str | None]:
        grading_id = str(uuid4())

        def find(item):
            return next((f for f in follow_ups(item) if f["request_id"] == request.request_id
                         and f["status"] == "answered"), None)

        def already_applied(item):
            follow = find(item)
            return bool(follow and follow.get("grading_retry_revision") == request.revision)

        def change(item):
            follow = find(item)
            if not follow or item["answers"][follow["parent_index"]]["grading_status"] not in ("pending", "rejected"):
                raise InterviewError(409, "follow_up_changed", "Reload before retrying grading")
            follow.update(parent_grading_id=grading_id, grading_retry_revision=request.revision)
            item["answers"][follow["parent_index"]].update(
                grading_id=grading_id, grading_status="pending", grade=None, error_code=None)

        result = self._change(owner_id, interview_id, request.revision, change, already_applied=already_applied)
        return result, grading_id if find(result)["parent_grading_id"] == grading_id else None

    def _change(self, owner_id: str, interview_id: str, revision: int,
                change: Callable[[dict], None], *,
                already_applied: Callable[[dict], bool] | None = None) -> dict:
        # Background grades change internal version, but not client revision.
        for _ in range(10):
            interview = self.get(owner_id, interview_id)
            # A lost HTTP response/double click can repeat the immediately
            # preceding edit. Return its current state without writing again.
            # Different or older edits must still pass the revision guard.
            if (interview["revision"] == revision + 1 and already_applied is not None
                    and already_applied(interview)):
                return interview
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
        def already_applied(interview: dict) -> bool:
            return (interview["current_question"] == request.current_question
                    and interview["status"] == request.status
                    and (request.answers is None or request.answers == [
                        answer["text"] for answer in interview["answers"]]))

        def change(interview: dict) -> None:
            if request.current_question >= len(interview["questions"]):
                raise InterviewError(400, "invalid_question",
                                     "Current question index is outside this interview")
            if request.answers is not None:
                # A client may send fewer answers than the interview has
                # questions (an older cached page, a partial draft); apply what
                # it sent and never let extra answers index past the interview.
                if len(request.answers) > len(interview["questions"]):
                    raise InterviewError(400, "invalid_request",
                                         "More answers than the interview has questions")
                for i, text in enumerate(request.answers):
                    if text != interview["answers"][i]["text"]:
                        invalidate_follow_up(interview, i)
                        interview["answers"][i] = _answer(text)
            interview.update(current_question=request.current_question, status=request.status)
        return self._change(owner_id, interview_id, request.revision, change,
                            already_applied=already_applied)

    def submit_answer(self, owner_id: str, interview_id: str, index: int,
                      request: SubmitAnswer) -> tuple[dict, str | None]:
        grading_id = str(uuid4())

        def already_applied(interview: dict) -> bool:
            answer = interview["answers"][index]
            return (interview["status"] != "finalized" and answer["text"] == request.text
                    and answer["grading_status"] in ("pending", "graded")
                    and bool(answer["grading_id"]))

        def change(interview: dict) -> None:
            if index >= len(interview["questions"]):
                raise InterviewError(400, "invalid_question",
                                     "Question index is outside this interview")
            if any(f["status"] == "ready" and f.get("automatic") and f["parent_index"] != index
                   for f in follow_ups(interview)):
                raise InterviewError(409, "follow_up_required", "Answer the follow-up before continuing")
            interview["answers"][index] = {
                **_answer(request.text), "grading_status": "pending", "grading_id": grading_id,
            }
            invalidate_follow_up(interview, index)
            new_follow_up(interview, index, automatic=True)
            destination = index
            if interview["follow_up"]["status"] != "generating":
                destination = min(index + 1, len(interview["questions"]) - 1)
            interview.update(current_question=destination, status="in_progress")
        result = self._change(owner_id, interview_id, request.revision, change,
                              already_applied=already_applied)
        # A replay must not schedule a second AI call for the same job. A fresh
        # revision can still explicitly re-submit a pending/rejected answer.
        return result, grading_id if result["answers"][index]["grading_id"] == grading_id else None

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
        clarification = next((f for f in follow_ups(interview) if f["parent_index"] == index
                              and f["parent_grading_id"] == grading_id and f["status"] == "answered"), None)
        text = answer["text"]
        question = dict(interview["questions"][index])
        if clarification:
            text += "\n\n" + clarification["answer"]
            question["text"] += ("\n\nFollow-up: " + clarification["question"]
                                 + "\nAssess the original answer and clarification together using the original rubric. "
                                 "Return one score. Quote evidence only from the supplied answer text.")
        try:
            grade = self.ai.grade_answer(interview["job_profile"], question, text)
            grounded = all(quote.strip() and quote in text for quote in grade["evidence"])
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

        target_name = (request.name or current["name"]).strip()
        if target_name:
            for existing in self.list(owner_id):
                if (existing.get("id") != interview_id
                        and (existing.get("name") or "").strip().casefold() == target_name.casefold()):
                    raise InterviewError(
                        409,
                        "duplicate_name",
                        "An interview with this name already exists. Please choose a different name.",
                    )

        def change(interview: dict) -> None:
            counts = progress(interview)
            if any(f["status"] == "ready" and f.get("automatic") for f in follow_ups(interview)):
                raise InterviewError(409, "follow_up_required", "Answer the follow-up before finishing")
            if counts["pending"] > 0:
                raise InterviewError(409, "grading_incomplete", "Wait for pending grading to finish")
            items = []
            rejected_count = 0
            unanswered_count = 0
            for i, answer in enumerate(interview["answers"]):
                status = answer.get("grading_status")
                grade = answer.get("grade")
                if status == "graded" and isinstance(grade, dict):
                    items.append({"question_index": i, "question": interview["questions"][i],
                                  "answer": answer["text"], **grade,
                                  "includes_follow_up": any(f["parent_index"] == i and f["status"] == "answered"
                                                            for f in follow_ups(interview)),
                                  "label": "Good" if grade["score"] >= 6 else "Needs Improvement"})
                elif status == "rejected":
                    rejected_count += 1
                    reason = answer.get("error_code") or "evidence_rejected"
                    items.append({
                        "question_index": i, "question": interview["questions"][i],
                        "answer": answer["text"], "score": None,
                        "feedback": f"Grading was rejected ({reason}); no score was assigned.",
                        "evidence": [], "label": "Rejected", "model": "none", "used_fallback": False,
                    })
                else:
                    unanswered_count += 1
                    items.append({
                        "question_index": i, "question": interview["questions"][i],
                        "answer": answer["text"], "score": None,
                        "feedback": "No answer was submitted for this question.",
                        "evidence": [], "label": "Unanswered", "model": "none", "used_fallback": False,
                    })
            graded_scores = [item["score"] for item in items if item["score"] is not None]
            overall = round(sum(graded_scores) / len(graded_scores), 2) if graded_scores else None
            used_fallback = (interview["question_generation"]["used_fallback"]
                             or any(item["used_fallback"] for item in items))
            notices = []
            if rejected_count:
                notices.append(f"{rejected_count} answer(s) were rejected during evidence verification and excluded from scoring.")
            if unanswered_count:
                notices.append(f"{unanswered_count} question(s) were left unanswered.")
            report = {"overall_score": overall, "items": items,
                      "label": ("Good" if overall >= 6 else "Needs Improvement") if overall is not None else "Incomplete"}
            answered_follow_ups = [dict(f) for f in follow_ups(interview) if f["status"] == "answered"]
            report["follow_ups"] = answered_follow_ups
            if answered_follow_ups:
                report["follow_up"] = answered_follow_ups[-1]
            # One provider-written paragraph about the whole interview. Only
            # question, label, score and feedback leave this function - raw
            # answers and the CV are never forwarded - and a summary failure
            # must never block finalizing an otherwise complete interview.
            try:
                summary = self.ai.summarize_interview([
                    {"question": item["question"]["text"], "verdict": item["label"],
                     "score": item["score"], "feedback": item["feedback"]}
                    for item in items if item["score"] is not None
                ])
            except Exception:
                logger.error("Interview summary did not finish; report stays without a summary")
                summary = None
            if summary:
                report["overall_comment"] = summary["summary"]
                report["summary_model"] = summary["model"]
                if summary["used_fallback"]:
                    # The comment is extra commentary, not the assessment: a
                    # fallback summary must not relabel a real grade as mock.
                    notices.append("The overall comment was written by the offline "
                                   "fallback, not by the AI.")
            notices.append("Contains mock/fallback output; not a real AI assessment."
                           if used_fallback else "Evidence quotations passed exact text matching.")
            report.update(used_fallback=used_fallback, notice=" ".join(notices))
            interview.update(
                name=request.name or interview["name"], status="finalized",
                current_question=len(interview["questions"]) - 1,
                report=report,
            )
        return self._change(owner_id, interview_id, request.revision, change,
            already_applied=lambda item: item["status"] == "finalized" and (
                request.name is None or request.name == item["name"]))
