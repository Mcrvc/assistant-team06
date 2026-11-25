"""Opt-in reader for the team's pre-written Supabase interview question bank.

The bank is a shared Supabase project whose table and column names are not
documented, so every row is read defensively: unknown column shapes, empty
rubrics or partial payloads make ``draw`` return ``None`` and callers fall back
to generating questions. The secret key is only used as a request header and is
never logged or echoed.
"""
from __future__ import annotations

import json
import math
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener

from assistant.auth import _NoAuthRedirect
from assistant.db import _is_real_value, get_env_config
from assistant.interview_schemas import Question

TRUTHY_VALUES = ("1", "on", "true", "auto")
DEFAULT_DOMAIN = "information_technology"
DEFAULT_COUNT = 3
COUNT_RANGE = (1, 10)
MAX_CRITERIA = 6
MAX_BODY_BYTES = 16 * 1024 * 1024
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_STOPWORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "are", "you", "your",
    "have", "will", "about", "into", "our", "role", "job", "work", "experience",
})


class QuestionBankError(Exception):
    """The question bank could not be opened, or its rows are not questions."""


def _env_flag(name: str) -> str:
    return os.environ.get(name, "0").strip().lower()


def bank_enabled() -> bool:
    """True only for an explicit opt-in; anything else keeps the bank off."""
    return _env_flag("INTERVIEW_QUESTION_BANK") in TRUTHY_VALUES


def bank_domain() -> str:
    return os.environ.get("INTERVIEW_BANK_DOMAIN", DEFAULT_DOMAIN).strip() or DEFAULT_DOMAIN


def _bank_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)).strip())
    except ValueError:
        return default
    return max(low, min(high, value))


def bank_count() -> int:
    return _bank_int("INTERVIEW_BANK_LIMIT", DEFAULT_COUNT, *COUNT_RANGE)


def _first_text(row: dict, keys: tuple[str, ...], limit: int) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:limit]
    return None


def _positive_points(entry: dict) -> float | None:
    for key in ("points", "weight", "max_score"):
        value = entry.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        points = float(value)
        if math.isfinite(points) and points > 0:
            return points
    return None


def _rubric_rows(row: dict) -> list:
    # PostgREST embeds the rubrics of a question under an aliased key.
    for key in ("rubrics", "rubric"):
        value = row.get(key)
        if isinstance(value, list) and value:
            return value
    fallback = row.get("criteria")
    return fallback if isinstance(fallback, list) else []


def _criterion(entry: dict, category: str | None) -> dict | None:
    good = _first_text(entry, ("good", "excellent", "description"), 1000)
    if not good:
        return None
    name = _first_text(entry, ("name", "title", "competency"), 200) or category or "Criterion"
    # Missing weights are derived equally before the shared sum-to-10 scaling.
    return {"name": name, "points": _positive_points(entry) or 1.0, "good": good}


def _scale_to_ten(criteria: list[dict]) -> bool:
    total = sum(criterion["points"] for criterion in criteria)
    if math.isclose(total, 10.0):
        return True
    if total <= 0:
        return False
    scaled = [round(criterion["points"] * 10.0 / total, 2) for criterion in criteria[:-1]]
    # The last criterion absorbs the rounding remainder of the others.
    scaled.append(round(10.0 - sum(scaled), 2))
    if any(points <= 0 for points in scaled):
        return False
    for criterion, points in zip(criteria, scaled):
        criterion["points"] = points
    return True


def _question_from_row(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    text = _first_text(row, ("question", "text", "prompt", "title"), 4000)
    if not text:
        return None
    category = _first_text(row, ("category", "competency", "domain"), 200)
    criteria = []
    for entry in _rubric_rows(row):
        if isinstance(entry, dict):
            criterion = _criterion(entry, category)
            if criterion is not None:
                criteria.append(criterion)
    if not criteria:
        return None
    criteria = criteria[:MAX_CRITERIA]
    if not _scale_to_ten(criteria):
        return None
    question = {"text": text, "source_type": "open", "reference": None,
                "criteria": [criterion["good"] for criterion in criteria],
                "rubric": {"max_score": 10.0, "criteria": criteria}}
    try:
        return Question.model_validate(question).model_dump()
    except Exception:
        return None


def _normalize_domain(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or None


def _tokens(value: Any) -> set[str]:
    if isinstance(value, str):
        return {tok for tok in _TOKEN_RE.findall(value.lower()) if tok not in _STOPWORDS}
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_tokens(item))
        return result
    return set()


def _row_relevance(row: dict, question: dict, job_profile: dict) -> int:
    """Score how well a bank row matches the candidate's job profile."""
    if not isinstance(job_profile, dict) or not job_profile:
        return 0
    title_tokens = _tokens(job_profile.get("title"))
    level_tokens = _tokens(job_profile.get("level"))
    other_tokens = _tokens(job_profile.get("domain")) | _tokens(job_profile.get("description"))
    if not (title_tokens or level_tokens or other_tokens):
        return 0
    row_tokens: set[str] = set()
    for key in ("category", "competency", "domain", "role", "position",
                "level", "seniority", "difficulty", "tags"):
        row_tokens.update(_tokens(row.get(key)))
    row_tokens.update(_tokens(question.get("text")))
    row_tokens.update(_tokens(question.get("criteria")))
    return (3 * len(title_tokens & row_tokens)
            + 2 * len(level_tokens & row_tokens)
            + len(other_tokens & row_tokens))


class SupabaseQuestionBank:
    """Reads questions from a shared Supabase project over PostgREST."""

    def __init__(self, project_url: str, secret_key: str, *,
                 domain: str = DEFAULT_DOMAIN, timeout_s: float = 10.0) -> None:
        # Same origin rules as SupabaseInterviewRepository: HTTPS, no userinfo,
        # no query/fragment and an empty or "/" path only.
        url = urlsplit(project_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/")):
            raise QuestionBankError("Question bank requires a trusted HTTPS project origin")
        if not _is_real_value(secret_key) or secret_key.startswith("sb_publishable_"):
            raise QuestionBankError("Question bank requires a backend secret key")
        self._questions_url = project_url.rstrip("/") + "/rest/v1/questions"
        self._secret_key = secret_key
        self._domain = (domain or "").strip() or DEFAULT_DOMAIN
        self._timeout_s = timeout_s
        self._opener = build_opener(_NoAuthRedirect())

    def _fetch(self, count: int, domain: str | None = None) -> list | None:
        target_domain = (domain or "").strip() or self._domain
        limit = min(max(count * 3, 15), 50)
        url = (self._questions_url + "?select=*,rubric:rubrics(*)&domain=eq."
               + quote(target_domain, safe="") + f"&limit={limit}")
        headers = {"apikey": self._secret_key, "Accept": "application/json"}
        # Modern secret API keys are not JWTs and must not be sent as Bearer JWTs.
        if not self._secret_key.startswith("sb_secret_"):
            headers["Authorization"] = "Bearer " + self._secret_key
        request = Request(url, headers=headers)
        try:
            with self._opener.open(request, timeout=self._timeout_s) as response:
                if response.status != 200:
                    return None
                raw = response.read(MAX_BODY_BYTES + 1)
                if len(raw) > MAX_BODY_BYTES:
                    return None
        except (HTTPError, URLError, OSError, ValueError, TypeError):
            return None
        try:
            rows = json.loads(raw)
        except ValueError:
            return None
        return rows if isinstance(rows, list) else None

    def draw(self, job_profile: dict, count: int) -> list[dict] | None:
        """Draw ``count`` questions, or ``None`` so the caller generates instead."""
        if count < 1:
            return None
        requested_domain = (_normalize_domain(job_profile.get("domain"))
                            if isinstance(job_profile, dict) else None)
        if requested_domain and requested_domain != self._domain:
            rows = self._fetch(count, domain=requested_domain)
        else:
            rows = self._fetch(count)
        if rows is None:
            return None
        try:
            candidates: list[tuple[int, int, dict]] = []
            for index, row in enumerate(rows):
                question = _question_from_row(row)
                if question is not None:
                    score = _row_relevance(row, question, job_profile)
                    candidates.append((score, index, question))
        except (AttributeError, KeyError, TypeError, ValueError):
            raise QuestionBankError("Question bank rows are not readable") from None
        if len(candidates) < count:
            return None
        candidates.sort(key=lambda entry: (-entry[0], entry[1]))
        return [question for _, _, question in candidates[:count]]


def draw_questions(job_profile: dict, count: int | None = None) -> list[dict] | None:
    """Draw from the bank when enabled and configured, otherwise ``None``."""
    if not bank_enabled():
        return None
    try:
        config = get_env_config()
        if not _is_real_value(config.supabase_url) or not _is_real_value(config.supabase_secret_key):
            return None
        bank = SupabaseQuestionBank(config.supabase_url, config.supabase_secret_key,
                                    domain=bank_domain())
        return bank.draw(job_profile, count or bank_count())
    except Exception:
        # A bank problem must never block interview creation.
        return None