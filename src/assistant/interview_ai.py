"""Interview provider seam, separate from the AI teammate's existing ai.py."""
from __future__ import annotations

from copy import deepcopy
from importlib import import_module
import os
from typing import Protocol
from assistant.interview_schemas import Generation, Grade


class InterviewAI(Protocol):
    """Providers enforce their own network timeout and return plain dictionaries.

    generate_questions may use a question bank or an LLM. Return exactly 3
    questions with source labels and criteria. grade_answer grades one answer.
    """
    def generate_questions(self, job_profile: dict, cv: str | None) -> dict: ...
    def grade_answer(self, job_profile: dict, question: dict, answer: str) -> dict: ...


class GradeRejected(Exception):
    """A provider refused its own grade; never replace it with a scored mock."""
    def __init__(self, code: str) -> None:
        self.code = code if code in {
            "evidence_not_found", "feedback_ungrounded", "bad_score", "no_feedback", "no_evidence"
        } else "evidence_not_found"
        super().__init__(self.code)


class MockInterviewAI:
    def generate_questions(self, job_profile: dict, cv: str | None) -> dict:
        title = job_profile.get("title", "").strip() or "this role"
        return {
            "questions": [
                {"text": text, "source_type": "open", "reference": None,
                 "criteria": ["Relevant example", "Clear personal actions", "Outcome and reflection"]}
                for text in (
                    f"Why are you interested in {title}, and what experience prepares you for it?",
                    f"Describe a challenging project relevant to {title}. What did you do and learn?",
                    "How would you handle an unfamiliar task and check the result?",
                )
            ],
            "model": "local-mock", "used_fallback": True,
        }

    def grade_answer(self, job_profile: dict, question: dict, answer: str) -> dict:
        # Word count exercises the flow; it does not assess professional ability.
        words = len(answer.split())
        return {
            "score": 8.0 if words >= 30 else 6.0 if words >= 12 else 3.0,
            "feedback": "Demo only: word-count rubric. Add a specific example, your actions and a result.",
            "evidence": [answer.strip()[:120]], "model": "local-mock", "used_fallback": True,
        }


class TeamInterviewAI:
    """Adapter for origin/AI. Web research and raw CV forwarding are off by default."""

    def __init__(self, *, allow_cv: bool = False, timeout_s: float = 20.0,
                 worker=None, model: str | None = None) -> None:
        if not 1 <= timeout_s <= 60:
            raise ValueError("INTERVIEW_AI_TIMEOUT_S must be between 1 and 60")
        self.allow_cv, self.timeout_s = allow_cv, timeout_s
        if worker is None:
            try:
                worker = import_module("assistant.aiworker")
                ai = import_module("assistant.ai")
                if not callable(getattr(worker, "generate_questions", None)) or not callable(
                        getattr(worker, "grade_answer_with_evidence", None)):
                    raise AttributeError("Missing AI entry point")
                model = ai.get_config().model
            except (ImportError, AttributeError):
                raise ValueError("Real AI requires Duy's reviewed ai.py and aiworker.py; see docs/interview-handoff.md") from None
        self.worker, self.model = worker, model or "team-provider"

    def generate_questions(self, job_profile: dict, cv: str | None) -> dict:
        generated = self.worker.generate_questions(
            job_profile, {"raw": cv} if self.allow_cv and cv else {}, "", [],
            timeout_s=self.timeout_s,
        )
        questions = []
        for item in generated["questions"]:
            rubric = item["rubric"]
            questions.append({
                "text": item["question"], "source_type": "open", "reference": None,
                "criteria": [c["good"] for c in rubric["criteria"]], "rubric": rubric,
            })
        return {"questions": questions, "model": self.model,
                "used_fallback": generated.get("source") != "nvidia"}

    def grade_answer(self, job_profile: dict, question: dict, answer: str) -> dict:
        if not question.get("rubric"):
            raise ValueError("A provider rubric is required for real grading")
        try:
            return self.worker.grade_answer_with_evidence(
                question["text"], answer, question["rubric"], timeout_s=self.timeout_s,
            )
        except self.worker.EvidenceRejected as exc:
            # Do not forward provider messages, which may quote private answers.
            raise GradeRejected(exc.code) from None


def configured_ai() -> InterviewAI:
    provider = os.environ.get("INTERVIEW_AI_PROVIDER", "mock")
    if provider == "mock":
        return MockInterviewAI()
    if provider != "nvidia":
        raise ValueError("INTERVIEW_AI_PROVIDER must be mock or nvidia")
    return TeamInterviewAI(
        allow_cv=os.environ.get("INTERVIEW_ALLOW_CV_TO_AI") == "1",
        timeout_s=float(os.environ.get("INTERVIEW_AI_TIMEOUT_S", "20")),
    )


class SafeInterviewAI:
    """Validate output and fall back on provider errors or malformed output.

    Evidence is checked separately. A well-shaped grade with fabricated evidence
    is rejected, never silently accepted. No provider exception data is logged.
    """
    def __init__(self, provider: InterviewAI | None = None) -> None:
        self.provider = provider or MockInterviewAI()
        self.fallback = MockInterviewAI()

    def generate_questions(self, job_profile: dict, cv: str | None) -> dict:
        try:
            result = self.provider.generate_questions(deepcopy(job_profile), cv)
            return Generation.model_validate(result).model_dump()
        except Exception:
            return Generation.model_validate(self.fallback.generate_questions(job_profile, cv)).model_dump()

    def grade_answer(self, job_profile: dict, question: dict, answer: str) -> dict:
        try:
            result = self.provider.grade_answer(deepcopy(job_profile), deepcopy(question), answer)
            return Grade.model_validate(result).model_dump()
        except GradeRejected:
            raise
        except Exception:
            return Grade.model_validate(self.fallback.grade_answer(job_profile, question, answer)).model_dump()
