"""AI Service: NVIDIA LLM host + TinyFish web search, with rule-based fallback.

This is the *only* module in the project allowed to talk to an external AI
provider. It finishes the stub described in ``docs/ai-interface.md``:

    LLM host   : NVIDIA   -> https://integrate.api.nvidia.com/v1/chat/completions
    Search tool: TinyFish -> https://api.search.tinyfish.ai   (retrieval only)

The CLI (``src/assistant/__main__.py``), the HTTP layer (``src/assistant/web.py``)
and the interview harness (``aiworker.py``) all import from here. Swapping the
provider or the model must not change any caller.

Credentials
-----------
Read from the process environment, or from a git-ignored ``.env`` file next to
the repository root (``.env`` and ``.venv/`` are both ignored - see
``.gitignore``). Values starting with ``fake_``/``faeke_``/``insert_``/
``_insert_``/``your_``/``changeme`` are treated as unset, matching
``.env.example``. A key is only ever used as a request header: it is never
logged, never returned, and never written to disk by this module.

Retry policy
------------
``call_with_retry`` wraps every service call. Recoverable failures
(``AiTimeoutError``, ``AiUnavailableError``, ``AiResponseError`` and
``ValueError`` from a bad payload) are retried up to ``AI_RETRIES`` times
(default 2) with ``AI_RETRY_DELAY_S`` (default 5) seconds in between, so a
transient provider blip is retried twice and only then surfaced.
``AiConfigError`` is never retried - a missing key cannot fix itself.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from assistant.rules import reply

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_CANDIDATES = (REPO_ROOT / ".env", REPO_ROOT / ".venv" / ".env")

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
TINYFISH_SEARCH_URL = "https://api.search.tinyfish.ai"
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"

SAFE_DEFAULT_TEXT = (
    "I don't know that yet. Try asking about an office, e.g. 'training office'."
)

PLACEHOLDER_PREFIXES = ("fake_", "faeke_", "insert_", "_insert_", "your_", "changeme")

RETRY_ATTEMPTS = 2          # extra attempts after the first failure
RETRY_DELAY_S = 5.0         # seconds to wait between attempts


def _retry_int(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name) or "").strip() or default)
    except ValueError:
        return default


def _retry_float(name: str, default: float) -> float:
    try:
        return float((os.environ.get(name) or "").strip() or default)
    except ValueError:
        return default


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Value objects
# --------------------------------------------------------------------------
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
    # Extension (not in the original spec): carries the reason a fallback was
    # used, so callers can log it instead of guessing. None when the LLM path
    # answered, so existing callers are unaffected.
    error: str | None = None


@dataclass(frozen=True)
class Completion:
    """One provider response, returned by :func:`complete`."""

    text: str
    model: str
    usage: Usage | None = None
    finish_reason: str = ""
    # Hidden thinking tokens of a reasoning model. Kept for debugging only:
    # when ``content`` is empty this is usually where the budget went.
    reasoning: str = ""


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
def _is_real_value(value: str) -> bool:
    cleaned = (value or "").strip()
    if not cleaned:
        return False
    lower = cleaned.lower()
    return not any(lower.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def _load_env_file(path: Path) -> None:
    """Load ``key=value`` pairs from ``path`` into ``os.environ`` (never overriding)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class ServiceConfig:
    """Everything the provider layer needs to make a call."""

    nvidia_api_key: str
    tinyfish_api_key: str
    model: str
    max_tokens: int
    timeout_s: float
    temperature: float
    search_limit: int
    search_timeout_s: float
    fetch_timeout_s: float
    fetch_max_chars: int
    base_url: str
    search_url: str

    @property
    def llm_ready(self) -> bool:
        return _is_real_value(self.nvidia_api_key)

    @property
    def search_ready(self) -> bool:
        return _is_real_value(self.tinyfish_api_key)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or "").strip() or default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


@lru_cache(maxsize=1)
def get_config() -> ServiceConfig:
    """Load the local ``.env`` once (if present) and freeze the configuration."""
    for candidate in ENV_CANDIDATES:
        if candidate.is_file():
            _load_env_file(candidate)
            break
    key = (
        _env("NVIDIA_API_KEY")
        or _env("NVAPI_KEY")
        or _env("NVIDIA_KEY")
        or _env("LLM_API_KEY")
    )
    search_key = (
        _env("TINYFISH_API_KEY")
        or _env("TINYFISH_KEY")
        or _env("TINYFISH_SEARCH_KEY")
    )
    return ServiceConfig(
        nvidia_api_key=key,
        tinyfish_api_key=search_key,
        model=_env("NVIDIA_MODEL", DEFAULT_MODEL),
        # The published default is 4, but this host is a *reasoning* model: it
        # spends tokens thinking before it speaks, and a small budget returns
        # content=None. 4096 leaves room for a real answer.
        max_tokens=max(256, _env_int("NVIDIA_MAX_TOKENS", 4096)),
        timeout_s=max(1.0, _env_float("NVIDIA_TIMEOUT_S", 120.0)),
        temperature=min(2.0, max(0.0, _env_float("NVIDIA_TEMPERATURE", 0.2))),
        search_limit=max(1, _env_int("TINYFISH_LIMIT", 8)),
        search_timeout_s=_env_float("TINYFISH_TIMEOUT_S", 60.0),
        fetch_timeout_s=_env_float("FETCH_TIMEOUT_S", 30.0),
        fetch_max_chars=_env_int("FETCH_MAX_CHARS", 6000),
        base_url=_env("NVIDIA_URL", NVIDIA_URL),
        search_url=_env("TINYFISH_SEARCH_URL", TINYFISH_SEARCH_URL),
    )


def reset_config_cache() -> None:
    """Drop the cached configuration (tests only)."""
    get_config.cache_clear()


# --------------------------------------------------------------------------
# Retry policy
# --------------------------------------------------------------------------
RETRYABLE_ERRORS = (AiTimeoutError, AiUnavailableError, AiResponseError, ValueError)


def _retry_settings() -> tuple[int, float]:
    """Retry budget and delay, from the environment or the module defaults."""
    return (
        max(0, _retry_int("AI_RETRIES", RETRY_ATTEMPTS)),
        max(0.0, _retry_float("AI_RETRY_DELAY_S", RETRY_DELAY_S)),
    )


def _log(message: str) -> None:
    print(f"[ai] {message}", flush=True)


def call_with_retry(
    fn: Callable[[], Any],
    *,
    label: str = "AI call",
    attempts: int | None = None,
    delay_s: float | None = None,
    retryable: tuple[type[BaseException], ...] = RETRYABLE_ERRORS,
) -> Any:
    """Run ``fn`` and retry recoverable failures.

    Retries up to ``attempts`` times (default 2) waiting ``delay_s`` seconds
    (default 5) between tries. ``AiConfigError`` is never retried: a missing
    key is a setup problem, not a blip.
    """
    tries, delay = _retry_settings()
    if attempts is not None:
        tries = max(0, attempts)
    if delay_s is not None:
        delay = delay_s
    last_error: BaseException | None = None

    for attempt in range(1, tries + 2):
        try:
            return fn()
        except AiConfigError:
            raise
        except retryable as exc:
            last_error = exc
            if attempt > tries:
                break
            _log(f"{label} failed ({type(exc).__name__}: {exc}); "
                 f"retry {attempt}/{tries} in {delay:g}s")
            time.sleep(delay)
        except Exception as exc:  # noqa: BLE001 - re-raise non-retryable faults
            raise exc

    assert last_error is not None
    raise last_error


def _http_json(
    url: str,
    *,
    method: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout_s: float = 120.0,
) -> tuple[int, dict[str, Any]]:
    """POST/GET JSON and return ``(status, body_dict)``. Raises Ai* errors."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={**headers, "Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"_raw": raw[:2000]}
        if exc.code == 429:
            raise AiUnavailableError(f"rate limited by {url}: {_short(body)}") from exc
        if 500 <= exc.code < 600:
            raise AiUnavailableError(f"server error {exc.code} from {url}: {_short(body)}") from exc
        raise AiResponseError(f"HTTP {exc.code} from {url}: {_short(body)}") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError) or "timed out" in str(exc.reason).lower():
            raise AiTimeoutError(f"{method} {url} timed out after {timeout_s:g}s") from exc
        raise AiUnavailableError(f"cannot reach {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AiTimeoutError(f"{method} {url} timed out after {timeout_s:g}s") from exc
    except json.JSONDecodeError as exc:
        raise AiResponseError(f"{url} returned non-JSON output") from exc


def _short(body: dict[str, Any], limit: int = 300) -> str:
    text = json.dumps(body)[:limit]
    return text


# --------------------------------------------------------------------------
# NVIDIA LLM host
# --------------------------------------------------------------------------
def _as_message(item: Message | dict[str, Any]) -> dict[str, str]:
    if isinstance(item, Message):
        return {"role": item.role, "content": item.content}
    role = str(item.get("role", "user"))
    content = str(item.get("content", ""))
    return {"role": role, "content": content}


def _chat_completion(
    cfg: ServiceConfig,
    messages: Sequence[Message | dict[str, Any]],
    *,
    max_tokens: int,
    temperature: float,
    timeout_s: float,
) -> Completion:
    """One provider round-trip. Raises ``AiError`` subclasses on failure."""
    payload = {
        "model": cfg.model,
        "messages": [_as_message(m) for m in messages],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
        "chat_template_kwargs": {"thinking": False},
    }
    status, body = _http_json(
        cfg.base_url,
        method="POST",
        headers={"Authorization": f"Bearer {cfg.nvidia_api_key}"},
        payload=payload,
        timeout_s=timeout_s,
    )

    try:
        choice = body["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AiResponseError(f"unexpected response shape from {cfg.base_url}") from exc

    text = (message.get("content") or "").strip()
    finish = choice.get("finish_reason") or ""
    reasoning = (message.get("reasoning_content") or message.get("reasoning") or "").strip()
    if not text:
        raise AiResponseError(f"empty completion (finish_reason={finish!r})")

    usage_raw = body.get("usage") or {}
    usage = Usage(
        prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
        completion_tokens=int(usage_raw.get("completion_tokens", 0)),
    )
    return Completion(
        text=text,
        model=body.get("model", cfg.model),
        usage=usage,
        finish_reason=finish,
        reasoning=reasoning,
    )


def complete(
    messages: Sequence[Message | dict[str, Any]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout_s: float | None = None,
) -> Completion:
    """One raw LLM call, retried per the module policy. Raises on failure."""
    cfg = get_config()
    if not cfg.llm_ready:
        raise AiConfigError(
            "NVIDIA_API_KEY is not configured (expected in .env or the environment)"
        )
    return call_with_retry(
        lambda: _chat_completion(
            cfg,
            messages,
            max_tokens=cfg.max_tokens if max_tokens is None else max_tokens,
            temperature=cfg.temperature if temperature is None else temperature,
            timeout_s=cfg.timeout_s if timeout_s is None else timeout_s,
        ),
        label="LLM completion",
    )


# --------------------------------------------------------------------------
# TinyFish web search (tool only - no TinyFish research model involved)
# --------------------------------------------------------------------------
def _search(
    cfg: ServiceConfig, query: str, purpose: str | None
) -> list[ContextChunk]:
    params = {"query": query}
    if purpose:
        params["purpose"] = purpose
    url = f"{cfg.search_url}?{urllib.parse.urlencode(params)}"

    _status, body = _http_json(
        url,
        method="GET",
        headers={"X-API-Key": cfg.tinyfish_api_key},
        timeout_s=cfg.search_timeout_s,
    )

    results = body.get("results") or []
    chunks: list[ContextChunk] = []
    for index, item in enumerate(results[: cfg.search_limit]):
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or item.get("content") or "").strip()
        link = (item.get("url") or "").strip()
        if not (link or snippet):
            continue
        text = f"{title}\n{snippet}" if title else snippet
        # TinyFish gives no numeric relevance, so score = rank position.
        chunks.append(ContextChunk(text=text, source=link, score=1.0 - index * 0.1))
    return chunks


def search_web(query: str, *, purpose: str | None = None) -> list[ContextChunk]:
    """Search the web with TinyFish. Returns ranked chunks (empty on no hits)."""
    cfg = get_config()
    if not cfg.search_ready:
        raise AiConfigError(
            "TINYFISH_API_KEY is not configured (expected in .env or the environment)"
        )
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    return call_with_retry(
        lambda: _search(cfg, query.strip(), purpose),
        label=f"search {query.strip()[:40]!r}",
    )


class _TextExtractor(HTMLParser):
    """Pull readable text out of an HTML document, skipping non-content tags."""

    SKIP = {"script", "style", "noscript", "template", "svg", "head", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag in {"p", "div", "br", "li", "tr", "section", "article", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data)

    def text(self) -> str:
        joined = "".join(self.parts)
        joined = re.sub(r"[ \t\r\f\v]+", " ", joined)
        joined = re.sub(r"\n\s*\n+", "\n\n", joined)
        return joined.strip()


def _readable_text(html: str, limit: int) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.text()
    return text[:limit]


def _fetch(cfg: ServiceConfig, url: str, timeout_s: float) -> ContextChunk:
    if not re.match(r"^https?://", url):
        raise AiResponseError(f"fetch_page only supports http(s) URLs, got {url!r}")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "assistant-team06-bot/1.0 (+study assistant research)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            content_type = response.headers.get("Content-Type", "")
            if not any(k in content_type for k in ("text", "html", "xml", "json")):
                raise AiResponseError(f"{url} returned {content_type or 'unknown'} - not a text page")
            html = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise AiUnavailableError(f"fetch {url} failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise AiUnavailableError(f"fetch {url} failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AiTimeoutError(f"fetch {url} timed out") from exc

    text = _readable_text(html, cfg.fetch_max_chars)
    if len(text) < 40:
        raise AiResponseError(f"{url} produced no readable text")
    return ContextChunk(text=text, source=url, score=1.0)


def fetch_page(url: str, *, timeout_s: float | None = None) -> ContextChunk:
    """Fetch one URL and return its readable text as a single chunk."""
    cfg = get_config()
    return call_with_retry(
        lambda: _fetch(
            cfg, url, cfg.fetch_timeout_s if timeout_s is None else timeout_s
        ),
        label=f"fetch {url[:60]}",
    )


def _fallback_answer(question: str, error: BaseException | None) -> AiAnswer:
    """Never raises: rules first, then the safe default."""
    try:
        text = reply(question)
    except Exception:  # noqa: BLE001 - the fallback must never crash the caller
        text = SAFE_DEFAULT_TEXT
    return AiAnswer(
        text=text,
        sources=[],
        model="stub-rules",
        used_fallback=True,
        usage=None,
        error=(f"{type(error).__name__}: {error}" if error else None),
    )


# --------------------------------------------------------------------------
# Public contract (docs/ai-interface.md)
# --------------------------------------------------------------------------
def answer(
    question: str,
    *,
    context: list[ContextChunk] | None = None,
    history: list[Message] | None = None,
    max_tokens: int | None = None,
    timeout_s: float | None = None,
) -> AiAnswer:
    """Answer ``question``, using the LLM when available.

    Never raises for a normal failure: on any ``AiError`` the rule-based
    fallback is returned with ``used_fallback=True`` and ``error`` set to the
    reason. Only programmer errors (empty ``question``) raise.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")

    cfg = get_config()
    if not cfg.llm_ready:
        return _fallback_answer(question, AiConfigError("NVIDIA_API_KEY is not configured"))

    chunks = context or []
    if chunks:
        lines = ["You may ground your answer on these retrieved passages:"]
        for i, chunk in enumerate(chunks, 1):
            lines.append(f"[{i}] ({chunk.source})\n{chunk.text}")
        context_block = "\n\n".join(lines)
        guidance = (
            "Ground your answer in the passages when they are relevant and cite "
            "them by number. If they do not cover the question, say so and then "
            "answer from your own knowledge briefly."
        )
    else:
        context_block = ""
        guidance = (
            "No passages were supplied, so answer from your own knowledge. If "
            "you are not confident, say you do not know rather than guessing."
        )

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a concise study assistant for a university. "
                "Answer in at most three sentences. " + guidance
            ),
        },
    ]
    for turn in history or []:
        messages.append(_as_message(turn))
    messages.append(
        {"role": "user", "content": f"{context_block}\n\nQuestion: {question.strip()}"}
        if chunks
        else {"role": "user", "content": question.strip()}
    )

    try:
        completion = complete(messages, max_tokens=max_tokens, timeout_s=timeout_s)
    except AiError as exc:
        return _fallback_answer(question, exc)

    return AiAnswer(
        text=completion.text,
        sources=[chunk.source for chunk in chunks],
        model=completion.model,
        used_fallback=False,
        usage=completion.usage,
        error=None,
    )


__all__ = [
    "AiAnswer",
    "AiConfigError",
    "AiError",
    "AiResponseError",
    "AiTimeoutError",
    "AiUnavailableError",
    "Completion",
    "ContextChunk",
    "Message",
    "Usage",
    "answer",
    "call_with_retry",
    "complete",
    "fetch_page",
    "get_config",
    "reset_config_cache",
    "search_web",
]
