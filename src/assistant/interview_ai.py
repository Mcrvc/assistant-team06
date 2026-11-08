"""Interview provider seam, separate from the AI teammate's existing ai.py."""
from __future__ import annotations

from copy import deepcopy
from typing import Protocol
from assistant.interview_schemas import Generation, Grade


class InterviewAI(Protocol):
    """Providers enforce their own network timeout and return plain dictionaries.

    generate_questions may use a question bank or an LLM. Return exactly 3
    questions with source labels and criteria. grade_answer grades one answer.
    """
    def generate_questions(self, job_profile: dict, cv: str | None) -> dict: ...
    def grade_answer(self, job_profile: dict, question: dict, answer: str) -> dict: ...


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
        except Exception:
            return Grade.model_validate(self.fallback.grade_answer(job_profile, question, answer)).model_dump()
