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
    summarize_interview turns graded items into one report paragraph.
    """
    def generate_questions(self, job_profile: dict, cv: str | None) -> dict: ...
    def grade_answer(self, job_profile: dict, question: dict, answer: str) -> dict: ...
    def summarize_interview(self, items: list[dict]) -> dict: ...


class GradeRejected(Exception):
    """A provider refused its own grade; never replace it with a scored mock."""
    def __init__(self, code: str) -> None:
        self.code = code if code in {
            "evidence_not_found", "feedback_ungrounded", "bad_score", "no_feedback", "no_evidence"
        } else "evidence_not_found"
        super().__init__(self.code)


INVALID_JOB_CODES = frozenset({"invalid_job", "invalid_domain",
                               "illegal_job", "illegal_domain"})
INVALID_JOB_MESSAGE = (
    "This job description does not describe a valid, legal role. "
    "Please retry with a different job description."
)


class InvalidJobProfile(Exception):
    """The provider refused the Job Profile as invalid or illegal.

    This is a user-facing refusal, not a provider outage: SafeInterviewAI
    re-raises it instead of falling back to a mock interview, and the service
    maps it to a 422 response telling the candidate to retry with a different
    job description.
    """
    def __init__(self, code: str = "invalid_job") -> None:
        self.code = code if code in INVALID_JOB_CODES else "invalid_job"
        self.message = INVALID_JOB_MESSAGE
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

    def summarize_interview(self, items: list[dict]) -> dict:
        # Deterministic and offline: every number below comes from the items
        # themselves, so the same report always produces the same summary.
        scored = [(index, item) for index, item in enumerate(items)
                  if isinstance(item, dict) and isinstance(item.get("score"), (int, float))
                  and not isinstance(item.get("score"), bool)]
        if not scored:
            return {"summary": "No answer was graded, so there is no summary yet.",
                    "model": "local-mock", "used_fallback": True}
        position = lambda pair: f"Q{pair[0] + 1} ({pair[1]['score']:.1f}/10)"
        strong = [position(pair) for pair in sorted(scored, key=lambda p: -p[1]["score"])[:2]]
        weak = [position(pair) for pair in sorted(scored, key=lambda p: p[1]["score"])[:2]]
        summary = (f"Strengths: {', '.join(strong)}. "
                   f"Improvements: {', '.join(weak)}. "
                   "Next round: retry the weakest questions with a concrete example "
                   "and a measurable result.")
        return {"summary": summary, "model": "local-mock", "used_fallback": True}


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
        try:
            generated = self.worker.generate_questions(
                job_profile, {"raw": cv} if self.allow_cv and cv else {}, "", [],
                timeout_s=self.timeout_s,
            )
        except Exception as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code in INVALID_JOB_CODES:
                # The planner refused the job profile. This is not a provider
                # outage, so never let SafeInterviewAI replace it with a mock.
                raise InvalidJobProfile(code) from None
            raise
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

    def summarize_interview(self, items: list[dict]) -> dict:
        # The worker itself forwards only question/verdict/score/feedback and
        # never raises for a provider failure, but a missing entry point on an
        # older worker must still degrade through SafeInterviewAI.
        return self.worker.summarize_interview(items, timeout_s=self.timeout_s)

    def validate_job_profile(self, job_profile: dict) -> None:
        """Run the planner's job-validity gate without writing questions."""
        planner = getattr(self.worker, "plan_interview", None)
        if not callable(planner):
            return
        try:
            planner(job_profile, {}, "", timeout_s=self.timeout_s)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code in INVALID_JOB_CODES:
                raise InvalidJobProfile(code) from None
            raise


def configured_ai() -> InterviewAI:
    """The provider for this process.

    ``auto`` (or an unset variable) picks the real provider as soon as an
    NVIDIA key is configured - so filling the key into ``.env`` is enough to
    make the product live - and the offline mock otherwise. ``mock`` and
    ``nvidia`` pin the choice.
    """
    provider = (os.environ.get("INTERVIEW_AI_PROVIDER") or "").strip().lower()
    if provider in ("", "auto"):
        provider = "nvidia" if _llm_ready() else "mock"
    if provider == "mock":
        return MockInterviewAI()
    if provider != "nvidia":
        raise ValueError("INTERVIEW_AI_PROVIDER must be mock, auto or nvidia")
    return TeamInterviewAI(
        allow_cv=os.environ.get("INTERVIEW_ALLOW_CV_TO_AI") == "1",
        timeout_s=float(os.environ.get("INTERVIEW_AI_TIMEOUT_S", "20")),
    )


def _llm_ready() -> bool:
    """True when a real NVIDIA key is configured (reads ``.env`` once)."""
    try:
        from assistant.ai import get_config
        return get_config().llm_ready
    except Exception:
        return False


class SafeInterviewAI:
    """Validate output and fall back on provider errors or malformed output.

    Evidence is checked separately. A well-shaped grade with fabricated evidence
    is rejected, never silently accepted. No provider exception data is logged.

    Recovery policy (a real result must never be lost to a strict schema): a
    payload the team schema refuses is first repaired in bounded ways - see
    :meth:`_coerce_generation` and :meth:`_coerce_grade`; a provider outage
    gets one extra attempt before the mock, and every fallback is logged with
    its reason on stderr so the Render logs show exactly which path fired.
    """

    # The team schema's limits for a generated interview.
    QUESTION_TEXT_LIMIT = 4000
    CRITERION_TEXT_LIMIT = 1000
    MAX_CRITERIA = 6
    MAX_QUESTIONS = 15
    RUBRIC_NAME_LIMIT = 200
    RUBRIC_GOOD_LIMIT = 2000
    REFERENCE_LIMITS = {"title": 200, "locator": 2000, "excerpt": 8000}

    def __init__(self, provider: InterviewAI | None = None) -> None:
        self.provider = provider or MockInterviewAI()
        self.fallback = MockInterviewAI()

    def generate_questions(self, job_profile: dict, cv: str | None) -> dict:
        try:
            result = self.provider.generate_questions(
                deepcopy(job_profile), cv)
        except InvalidJobProfile:
            # A refusal is a user-facing answer, not a provider outage.
            raise
        except Exception as exc:
            # The provider retried per slot; this is the last resort.
            print(f"[interview-ai] generation fell back to mock: "
                  f"{type(exc).__name__}", file=sys.stderr)
            return Generation.model_validate(
                self.fallback.generate_questions(job_profile, cv)).model_dump()

        try:
            return Generation.model_validate(result).model_dump()
        except Exception:
            pass

        # A REAL generation the team schema refuses is repaired question by
        # question: ONE unusable question (a 300-character criterion name, an
        # extra rubric field, seven criteria) must not throw away the five
        # good ones and hand the candidate a mock interview instead.
        coerced = self._coerce_generation(result)
        if coerced is None:
            print("[interview-ai] generation fell back to mock: real "
                  "generation unusable after coercion", file=sys.stderr)
        else:
            try:
                return Generation.model_validate(coerced).model_dump()
            except Exception:  # pragma: no cover - coercion is bounded
                print("[interview-ai] generation fell back to mock: coerced "
                      "generation still refused", file=sys.stderr)
        return Generation.model_validate(
            self.fallback.generate_questions(job_profile, cv)).model_dump()

    @classmethod
    def _coerce_rubric_criterion(cls, item: object) -> dict | None:
        """Keep one rubric criterion if it carries a usable score and text."""
        if not isinstance(item, dict):
            return None
        name, points, good = item.get("name"), item.get("points"), item.get("good")
        if not isinstance(name, str) or not name.strip():
            return None
        if (isinstance(points, bool) or not isinstance(points, (int, float))
                or not math.isfinite(float(points))):
            return None
        if not isinstance(good, str) or not good.strip():
            return None
        return {"name": name.strip()[:cls.RUBRIC_NAME_LIMIT],
                "points": min(10.0, max(0.01, float(points))),
                "good": good.strip()[:cls.RUBRIC_GOOD_LIMIT]}

    @classmethod
    def _coerce_rubric(cls, rubric: object) -> dict | None:
        """Repair one rubric: drop junk criteria, cap at six, re-sum to 10."""
        if not isinstance(rubric, dict):
            return None
        criteria = rubric.get("criteria")
        if not isinstance(criteria, list):
            return None
        kept = [criterion for criterion in
                (cls._coerce_rubric_criterion(item) for item in criteria)
                if criterion][:cls.MAX_CRITERIA]
        if not kept:
            return None
        total = sum(criterion["points"] for criterion in kept)
        if total <= 0:  # pragma: no cover - points are clamped above 0
            return None
        kept = [{**criterion, "points": criterion["points"] * 10.0 / total}
                for criterion in kept]
        # Absorb the rounding drift on the heaviest criterion so the points
        # still sum to exactly 10 (the team schema requires it).
        heaviest = max(range(len(kept)), key=lambda index: kept[index]["points"])
        drift = 10.0 - sum(criterion["points"] for criterion in kept)
        kept[heaviest]["points"] = min(10.0, max(
            0.01, kept[heaviest]["points"] + drift))
        return {"max_score": 10.0, "criteria": kept}

    @classmethod
    def _coerce_question(cls, item: object) -> dict | None:
        """Repair one generated question, or drop it when nothing is left.

        The rubric is what grading needs; a question whose rubric cannot be
        repaired is still asked, but with ``rubric: None`` so the answer is
        graded through the honest fallback instead of silently.
        """
        if not isinstance(item, dict):
            return None
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        criteria = item.get("criteria")
        quotes: list[str] = []
        if isinstance(criteria, list):
            for entry in criteria:
                if isinstance(entry, str) and entry.strip():
                    quotes.append(entry.strip()[:cls.CRITERION_TEXT_LIMIT])
                if len(quotes) == cls.MAX_CRITERIA:
                    break
        if not quotes:
            return None
        source_type = item.get("source_type")
        reference = item.get("reference")
        if source_type != "reference":
            source_type, reference = "open", None
        elif not isinstance(reference, dict):
            source_type, reference = "open", None
        else:
            repaired = {}
            for field, limit in cls.REFERENCE_LIMITS.items():
                value = reference.get(field)
                if not isinstance(value, str) or not value.strip():
                    repaired = None
                    break
                repaired[field] = value.strip()[:limit]
            if repaired is None:
                source_type, reference = "open", None
            else:
                reference = repaired
        return {"text": text.strip()[:cls.QUESTION_TEXT_LIMIT],
                "source_type": source_type, "reference": reference,
                "criteria": quotes, "rubric": cls._coerce_rubric(item.get("rubric"))}

    @classmethod
    def _coerce_generation(cls, result: object) -> dict | None:
        """Repair a REAL generation the team schema would refuse.

        Bounded repairs only: trim question/criterion text to the schema's
        limits, drop unusable questions and criteria, cap both lists, drop
        extra fields, and re-sum the rubric points to 10. Questions that
        cannot be repaired are dropped, never faked. Returns None when no
        usable question is left, which is the honest trigger for the mock.
        """
        if not isinstance(result, dict):
            return None
        questions = result.get("questions")
        if not isinstance(questions, list):
            return None
        kept = [question for question in
                (cls._coerce_question(item) for item in questions)
                if question][:cls.MAX_QUESTIONS]
        if not kept:
            return None
        dropped = len(questions) - len(kept)
        if dropped:
            print(f"[interview-ai] generation repair: dropped {dropped} of "
                  f"{len(questions)} question(s) the team schema refuses",
                  file=sys.stderr)
        model = str(result.get("model") or "").strip()[:200] or "team-provider"
        return {"questions": kept, "model": model,
                "used_fallback": bool(result.get("used_fallback", False))}

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

    @staticmethod
    def _summary_of(result: dict | object) -> dict | None:
        """Validate the worker summary shape; anything malformed returns None."""
        if not isinstance(result, dict):
            return None
        summary = str(result.get("summary") or "").strip()
        model = str(result.get("model") or "").strip()
        if not summary or not model:
            return None
        return {"summary": summary, "model": model[:200],
                "used_fallback": bool(result.get("used_fallback", True))}

    def summarize_interview(self, items: list[dict]) -> dict | None:
        """One report paragraph, or None when no provider could summarise.

        Never raises: a missing provider, a network failure or a malformed
        payload degrades to the deterministic mock summary instead.
        """
        try:
            summary = self._summary_of(self.provider.summarize_interview(deepcopy(items)))
        except Exception:
            summary = None
        if summary is None:
            try:
                summary = self._summary_of(self.fallback.summarize_interview(items))
            except Exception:
                return None
        return summary

    def validate_job_profile(self, job_profile: dict) -> None:
        """Run the provider's job-validity gate; refusals always propagate."""
        validator = getattr(self.provider, "validate_job_profile", None)
        if not callable(validator):
            return
        try:
            validator(deepcopy(job_profile))
        except InvalidJobProfile:
            raise
        except Exception:
            return
