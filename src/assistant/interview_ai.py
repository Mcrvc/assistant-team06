"""Interview provider seam, separate from the AI teammate's existing ai.py."""
from __future__ import annotations

from copy import deepcopy
from importlib import import_module
import math
import os
import sys
from typing import Protocol
from assistant.ai import AiError
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

    Recovery policy for grading (a real grade must never be lost to a strict
    schema): a payload the team schema refuses is first repaired in bounded
    ways (score clamped to 0-10, feedback/evidence/model trimmed to the
    schema's length limits); a provider outage gets one extra attempt before
    the mock, and every fallback is logged with its reason on stderr so the
    Render logs show exactly which path fired.
    """
    def __init__(self, provider: InterviewAI | None = None) -> None:
        self.provider = provider or MockInterviewAI()
        self.fallback = MockInterviewAI()

    def generate_questions(self, job_profile: dict, cv: str | None) -> dict:
        try:
            result = self.provider.generate_questions(deepcopy(job_profile), cv)
            return Generation.model_validate(result).model_dump()
        except Exception as exc:
            # The provider retried per slot; this is the last resort.
            print(f"[interview-ai] generation fell back to mock: "
                  f"{type(exc).__name__}", file=sys.stderr)
            return Generation.model_validate(self.fallback.generate_questions(job_profile, cv)).model_dump()

    @staticmethod
    def _coerce_grade(result: object) -> dict | None:
        """Repair a REAL grade the team schema would refuse, or return None.

        Bounded repairs only: clamp the score to 0-10, trim
        feedback/evidence/model to the schema's length limits, cap the
        evidence list, and drop only truly empty strings (whitespace-only or
        fabricated quotes survive for the service's verbatim check to
        reject). Returns None when nothing usable is left - a non-finite or
        non-numeric score, no feedback, or no evidence - which is the honest
        trigger for the mock fallback.
        """
        if not isinstance(result, dict):
            return None
        repaired = dict(result)
        score = repaired.get("score")
        if (isinstance(score, bool) or not isinstance(score, (int, float))
                or not math.isfinite(float(score))):
            # NaN/inf mean the provider is broken, not a real grade to clamp.
            return None
        repaired["score"] = min(10.0, max(0.0, float(score)))
        feedback = repaired.get("feedback")
        if not isinstance(feedback, str) or not feedback.strip():
            return None
        repaired["feedback"] = feedback.strip()[:8000]
        evidence = repaired.get("evidence")
        if not isinstance(evidence, list):
            return None
        # Only schema limits are repaired here. Evidence CONTENT is left for
        # the service's verbatim check: a whitespace-only or fabricated quote
        # must still reach it so the answer is rejected, not silently dropped
        # (dropping it would turn a rejection into an accepted grade).
        quotes = [str(item)[:2000] for item in evidence
                  if isinstance(item, str) and item != ""][:6]
        if not quotes:
            return None
        repaired["evidence"] = quotes
        repaired["model"] = (str(repaired.get("model") or "").strip()
                             or "team-provider")[:200]
        repaired["used_fallback"] = bool(repaired.get("used_fallback", False))
        return repaired

    def grade_answer(self, job_profile: dict, question: dict, answer: str) -> dict:
        # The provider retried inside itself; this second attempt covers a
        # transient blip between the provider and this seam.
        attempts = 2
        for attempt in range(attempts):
            try:
                result = self.provider.grade_answer(
                    deepcopy(job_profile), deepcopy(question), answer)
            except GradeRejected:
                raise
            except AiError:
                if attempt + 1 < attempts:
                    continue
                print("[interview-ai] grading fell back to mock: provider "
                      "unavailable after a retry", file=sys.stderr)
                break
            except Exception as exc:
                print(f"[interview-ai] grading fell back to mock: "
                      f"{type(exc).__name__}", file=sys.stderr)
                break
            coerced = self._coerce_grade(result)
            if coerced is None:
                print("[interview-ai] grading fell back to mock: real grade "
                      "not usable after coercion", file=sys.stderr)
                break
            try:
                return Grade.model_validate(coerced).model_dump()
            except Exception:
                # Coercion should have made this impossible; fall through.
                print("[interview-ai] grading fell back to mock: coerced "
                      "grade still refused", file=sys.stderr)
                break
        return Grade.model_validate(
            self.fallback.grade_answer(job_profile, question, answer)).model_dump()
