"""AI Service interface and rule-based fallback implementation.

Implements the contract specified in ``docs/ai-interface.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from assistant.rules import reply


class AiError(Exception):
    """Base class for every error raised by the AI service."""


class AiConfigError(AiError):
    """Missing or invalid API key or base URL."""


class AiTimeoutError(AiError):
    """LLM call exceeded ``timeout_s``."""


class AiUnavailableError(AiError):
    """Network error, 5xx, or rate limit (429)."""


class AiResponseError(AiError):
    """Model returned empty or malformed output."""


@dataclass(frozen=True)
class ContextChunk:
    """Retrieved passage that the model may ground its answer on."""

    text: str
    source: str
    score: float = 0.0


@dataclass(frozen=True)
class Message:
    """Single conversation turn for multi-turn history."""

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class Usage:
    """Token counts when a real LLM answered."""

    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class AiAnswer:
    """Immutable value object returned by :func:`answer`."""

    text: str
    sources: list[str] = field(default_factory=list)
    model: str = "stub-rules"
    used_fallback: bool = True
    usage: Usage | None = None


SAFE_DEFAULT_TEXT = (
    "I don't know that yet. Try asking about an office, e.g. 'training office'."
)


def answer(
    question: str,
    *,
    context: list[ContextChunk] | None = None,
    history: list[Message] | None = None,
    max_tokens: int = 256,
    timeout_s: float = 10.0,
) -> AiAnswer:
    """Return an answer to ``question``, using the LLM when available.

    Never raises for a normal failure: on any ``AiError`` it returns the
    rule-based fallback with ``used_fallback=True``. Raises only for
    programmer errors (empty question, bad arguments).
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if max_tokens <= 0 or timeout_s <= 0:
        raise ValueError("max_tokens and timeout_s must be > 0")

    _ = (context, history)  # Reserved for LLM provider integration

    try:
        text = reply(question.strip())
    except Exception:  # noqa: BLE001 - fallback must never crash the caller
        text = SAFE_DEFAULT_TEXT

    return AiAnswer(
        text=text,
        sources=[],
        model="stub-rules",
        used_fallback=True,
        usage=None,
    )
