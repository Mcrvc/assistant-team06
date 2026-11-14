# AI Service — Interface for the future LLM

Status: **draft / interface only**
Scope: this document defines *how the rest of the app will talk to an LLM*.
No real LLM call is implemented yet — the function below is a stub that uses the
existing rule-based fallback in `src/assistant/rules.py`.

Component: `ai-service` · Issue: *"AI service: define the interface for the future LLM"*

## 1. Why this interface exists

Today the assistant answers with rules (`rules.reply`). Later we want an LLM to
answer open questions, but the UI and backend must not depend on *which* provider
we use. So we fix one small contract now:

- one entry point, `answer(...)`;
- typed inputs, typed output, an explicit error type;
- a guaranteed, deterministic fallback when the LLM is missing or fails.

Callers only ever import `answer` and the dataclasses. They never touch a provider
SDK directly. Swapping provider (or the stub) must not change the caller.

## 2. Function signature

```python
# src/assistant/ai.py  (planned module — not created in this task)

class AiError(Exception):
    """Base class for every error raised by the AI service."""

class AiConfigError(AiError): ...
class AiTimeoutError(AiError): ...
class AiUnavailableError(AiError): ...

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
```

Design rules:

- **One public function.** No provider classes leak out.
- **Keyword-only options** so callers can add options later without breaking.
- **Returns a value object**, never a bare string — we need sources and metadata.
- **Fails soft**: a missing key or a network error must not crash the chat.

## 3. Inputs

| Name        | Type                     | Required | Default | Rules / meaning |
|-------------|--------------------------|----------|---------|-----------------|
| `question`  | `str`                    | yes      | —       | The user's message. `.strip()` must be non-empty, else raise `ValueError`. |
| `context`   | `list[ContextChunk]`     | no       | `None`  | Retrieved passages (office rows, notes) the LLM must ground on. |
| `history`   | `list[Message]`          | no       | `None`  | Prior turns, oldest → newest, for follow-up questions. |
| `max_tokens`| `int`                    | no       | `256`   | Upper bound on the generated answer length. Must be `> 0`. |
| `timeout_s` | `float`                  | no       | `10.0`  | Wall-clock budget for the whole call. Must be `> 0`. |

Supporting input types:

```python
@dataclass(frozen=True)
class ContextChunk:
    text: str            # the passage the model may quote
    source: str          # e.g. "data/offices.csv:training office"
    score: float = 0.0   # retrieval relevance, 0..1

@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str
```

## 4. Outputs

```python
@dataclass(frozen=True)
class AiAnswer:
    text: str                      # the answer to show the user
    sources: list[str]             # source ids actually used, may be empty
    model: str                     # e.g. "stub-rules" or "gpt-4o-mini"
    used_fallback: bool            # True when the rule-based path answered
    usage: Usage | None = None     # token counts when a real LLM answered

@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
```

Guarantees:

- `text` is always a non-empty, user-safe string (fallback guarantees this).
- `sources` are copied from the `context` entries the answer relies on; empty
  when the fallback answered without context.
- `model` names what actually produced the text, so logs and the UI stay honest.
- The result is immutable (`frozen=True`) — callers cannot mutate shared state.

## 5. Errors

All service errors derive from `AiError`. The public `answer()` catches every
`AiError` and converts it into a fallback answer, so normal callers see no
exception. The table describes what the *provider layer* raises internally.

| Error              | Raised when                                             | Recoverable? |
|--------------------|---------------------------------------------------------|--------------|
| `AiConfigError`    | Missing/invalid API key or base URL                     | No — fallback |
| `AiTimeoutError`   | Call exceeds `timeout_s`                                | Yes — retry once, then fallback |
| `AiUnavailableError`| Network error, 5xx, rate limit (429)                   | Yes — retry once, then fallback |
| `AiResponseError`  | Model returns empty or malformed output                 | No — fallback |
| `ValueError`       | Bad arguments (empty `question`, `max_tokens <= 0`)      | No — caller bug, **not** caught |

Constructor/argument validation is the one case that *does* propagate: a bad
argument is a programming error, not a runtime outage, and must be fixed in code.

## 6. Fallback

Fallback is a first-class feature, not an afterthought. Order of resolution:

1. **LLM path** (future): if configured and the call succeeds → return `AiAnswer`
   with `used_fallback=False`.
2. **Rule path** (today's behavior): call `rules.reply(question)` → wrap the
   string in `AiAnswer(model="stub-rules", used_fallback=True)`.
3. **Safe default**: if even the rules raise (e.g. `data/offices.csv` missing),
   return
   `"I don't know that yet. Try asking about an office, e.g. 'training office'."`
   with `used_fallback=True` and `sources=[]`.

Rules that keep fallback trustworthy:

- Fallback output is **deterministic** — same input, same answer.
- It never raises; the chat loop can always print `answer.text`.
- `used_fallback=True` is always set so we can measure how often the LLM is used.
- A failure of the LLM is logged (once) but never shown as a stack trace to the user.

### Current stub (no LLM call yet)

```python
def answer(question, *, context=None, history=None, max_tokens=256, timeout_s=10.0):
    question = (question or "").strip()
    if not question:
        raise ValueError("question must be a non-empty string")
    if max_tokens <= 0 or timeout_s <= 0:
        raise ValueError("max_tokens and timeout_s must be > 0")

    # TODO(week 4): call the LLM here. No provider call exists yet.
    try:
        text = reply(question)                      # from assistant.rules
    except Exception:                               # noqa: BLE001 - fallback must not crash
        text = "I don't know that yet. Try asking about an office, e.g. 'training office'."
    return AiAnswer(
        text=text,
        sources=[],
        model="stub-rules",
        used_fallback=True,
    )
```

## 7. Usage examples

```python
from assistant.ai import answer, ContextChunk

# Rule-only path (today)
res = answer("hi")
assert res.used_fallback is True
assert res.model == "stub-rules"

# With retrieval context (once the data layer exists)
res = answer(
    "when does the training office open?",
    context=[ContextChunk(text="Training Office, room 1, open 8:00-17:00",
                          source="data/offices.csv:training office", score=0.9)],
)
print(res.text, res.sources)

# Follow-up using history
res = answer("and on Saturday?", history=[
    Message("user", "where is the training office?"),
    Message("assistant", "Training Office: room 1, open 8:00-17:00."),
])
```

## 8. Non-goals (for this issue)

- No provider SDK, no API key, no network call — signature and contract only.
- No streaming, tools/function-calling, or embeddings in v1.
- No change to `src/assistant/rules.py`; it stays the fallback.

## 9. Interview AI worker (aiworker.py) — what the interview lifecycle gets

The chat `answer()` contract above is unchanged. The interview feature uses the
same `ai.py` transport through three worker functions in
`src/assistant/aiworker.py` (imported via `TeamInterviewAI` in
`src/assistant/interview_ai.py`). Status: implemented and covered by tests.

### 9.1 `generate_questions(job_profile, cv, notes, sources, *, timeout_s)`

Returns exactly `{"source", "questions", "research_notes", "sources"}`. Each
question carries `{"question", "category", "why", "rubric": {max_score: 10,
criteria: [3 x {name, points, good}]}}` — points sum to exactly 10, matching the
team's strict `Generation` schema.

- **Self-research (HM3).** When the caller passes no research (`notes` blank
  AND `sources` empty — the adapter always does), the worker runs one internal
  `plan_research` + `research_notes` round first. A caller that already has
  notes never triggers a second research pass. Research failure degrades to
  writing from the JD/CV alone; the stage never hard-fails on it.
- **Research bounds.** The research loop is limited by the knobs documented in
  `.env.example`: `AI_RESEARCH_TURNS` caps the model turns (default 6) and
  `AI_MAX_TOOL_CALLS` caps the total SEARCH + FETCH executions across those
  turns (default 10); either bound makes the loop reply FINAL early.
- **JD/CV grounding check (HM3).** Every generated question must share at
  least one significant token (4+ chars, diacritics-stripped) with the JD/CV
  text the writer saw. A total-overlap miss is refused as a generic question
  and retried inside the writer stage.
- **PII masking (HM6).** The CV text only ever enters a prompt through
  `mask_cv_pii` — emails become `[email]`, Vietnamese phone numbers become
  `[phone]`. Years/counts are untouched (the phone pattern needs 9+ digits).
  Policy: `docs/ai-cv-policy.md`.

### 9.2 `grade_answer_with_evidence(question, answer, rubric, *, timeout_s)`

Returns exactly the five keys the team's `Grade` schema accepts:
`{"score", "feedback", "evidence", "model", "used_fallback"}`.

- **Calibration (HM2).** The system prompt pins score bands: 9-10 reserved for
  measured outcomes, 7-8.5 strong/specific, 5.5-6.5 correct-but-generic,
  3-5 vague, 0-2.5 wrong/off-topic, plus two worked examples (8.5 and 5.5).
  `GOOD_THRESHOLD = 6.0` is the shared Good/Needs-Improvement line; the eval
  harness imports the same constant so service and eval cannot drift.
  Good>=6 stays the agreed temporary rule; grades.level and the rubric bank
  are not changed by us.
- **Verbatim evidence.** Every string in `evidence` must be an exact substring
  of the answer, and every quoted span in `feedback` must appear in
  `evidence`. Nothing is fabricated; a refused grade stays refused.
- **One repair turn (HM2).** On the first refusal the same conversation is
  continued with the exact offending item (`_repair_instruction`), which
  recovers most `feedback_ungrounded` / `evidence_not_found` cases without
  weakening the guard. A payload that still fails raises `EvidenceRejected`
  (codes: `bad_score`, `no_feedback`, `no_evidence`, `evidence_not_found`,
  `feedback_ungrounded`, `bad_json`) carrying the candidate-facing reply;
  the adapter converts it to `GradeRejected` and the answer is stored
  rejected with no score.
- Non-JSON replies surface as `bad_json` instead of a `JSONDecodeError`
  crash, and get the same one repair turn.

### 9.3 `summarize_interview(items, *, timeout_s=None)` (HM4) — wiring needed

Returns `{"summary", "model", "used_fallback"}`: one Vietnamese paragraph
(strengths by question, improvements, one next-round recommendation) built
from graded items only — raw answers and CV text are never forwarded. On
`AiError` it falls back to a deterministic rule-based summary
(`model="rule-fallback"`). **The team's finalize/report path does not call
this yet**; wiring it in finalize (or the report route) is a one-line change
on their side, and the output maps naturally onto
`sessions.ai_overall_comment`.

### 9.4 Latency budget (HM5) — measured 2026-11-15

Live NVIDIA probe after the `.env.example`-aligned research bounds
(`eval/timing_probe.py`, report `data/private/eval/timing.json`):
`generate_questions` p50 **25.0s** / p95 **28.5s** (3 runs, includes the
self-research round; the `AI_RESEARCH_TURNS=6` cap cut this from ~43s),
`grade_answer` p50 **3.4s** / p95 **4.5s** (5 runs, the p95 includes one
self-repair turn). Both stages fit a 45s budget with headroom: set
`INTERVIEW_AI_TIMEOUT_S=30`-`45` (seam caps 1-60, default 20). Note the retry
budget: `ai.py` retries up to 3x per request with 5s gaps, so worst-case wall
time is roughly 3x the measured p95 — the finalize timeout should assume
that, not the p95.

### 9.5 Question bank import (information_technology)

`it.json` was imported into the shared Supabase project: `domains` 1 row,
`rubrics` 70 rows (14 competencies x 5 levels), `questions` 69 rows. The
bank's `positions` / `criteria_research` / `meta` sections have no matching
tables in the current schema and were **not** imported — drawing runtime
questions from `questions` (instead of generating every session) needs
either new tables or a team-side reader; noted in
`docs/interview-handoff.md` follow-ups.
