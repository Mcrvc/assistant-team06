#!/usr/bin/env python3
"""Miniature research harness built on the ``assistant.ai`` framework.

Two commands, both driven by the same NVIDIA host that powers ``answer()``:

  generate  Job Profile + CV (JSON objects or plain strings)
            -> a subagent decides what it still needs to know, researches the
               web with TinyFish (search + page fetch), then writes mock
               interview questions with a scoring rubric for each.

  grade     Question + Scoring Rubric + the candidate's Answer
            -> "Good. ..." or "Needs Improvement. ...". The grader may do one
               round of web research before scoring when the question is
               technical/factual, so it can check the answer instead of
               vibes.

Failure policy: every LLM/web call goes through the retry wrapper in
``assistant.ai`` (2 retries, 5 s apart). If a stage still fails the harness
prints the error and returns deterministic mock data, so a run always produces
a usable artifact.

Usage (from the repository root, virtualenv active):
    python -m assistant.aiworker generate --job job.json --cv cv.txt --out run.json
    python -m assistant.aiworker grade --question "..." --answer "..." --rubric rubric.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from .ai import (
    AiError,
    ContextChunk,
    complete,
    fetch_page,
    search_web,
)


# ==========================================================================
# 1. Mock data - the deterministic safety net
# ==========================================================================
def _mock_questions(job_profile: str = "", cv: str = "") -> dict[str, Any]:
    """Deterministic fallback questions, shaped exactly like the real output.

    ``job_profile``/``cv`` are accepted for call symmetry but are not echoed:
    a payload that could not be produced is not worth repeating back.
    """
    return {
        "source": "mock",
        "questions": [
            {
                "question": "Tell me about a production incident you debugged end to end.",
                "category": "behavioral",
                "why": "MOCK fallback: no LLM available.",
                "rubric": {
                    "max_score": 10,
                    "criteria": [
                        {"name": "situation", "points": 3,
                         "good": "Concrete context: system, users, blast radius."},
                        {"name": "actions", "points": 4,
                         "good": "Own debugging steps, tools used, root cause found."},
                        {"name": "result", "points": 3,
                         "good": "Measurable outcome and what changed afterwards."},
                    ],
                },
            },
            {
                "question": "How would you design a rate limiter for this API?",
                "category": "technical",
                "why": "MOCK fallback: no LLM available.",
                "rubric": {
                    "max_score": 10,
                    "criteria": [
                        {"name": "algorithm", "points": 4,
                         "good": "Names a strategy (token bucket / sliding window) and trade-offs."},
                        {"name": "state", "points": 3,
                         "good": "Where counters live, fail-open vs fail-closed behaviour."},
                        {"name": "operability", "points": 3,
                         "good": "Metrics, per-key limits, abuse handling."},
                    ],
                },
            },
        ],
        "research_notes": "MOCK fallback: research was skipped because no LLM was available.",
        "sources": [],
    }


def _mock_grade(rubric: dict[str, Any]) -> dict[str, Any]:
    """Deterministic fallback grade, shaped exactly like the real output."""
    feedback = (
        "This rubric was scored by the mock fallback because the LLM was "
        "unavailable, so treat it as a placeholder only. Re-run once the "
        "service is healthy to get a real evaluation against your rubric."
    )
    return {
        "source": "mock",
        "verdict": "Needs Improvement.",
        "feedback": feedback,
        "rendered": f"Needs Improvement. {feedback}",
        "score": None,
        "rubric_max": rubric.get("max_score") if isinstance(rubric, dict) else None,
        "research_notes": [],
    }


# ==========================================================================
# 2. Inputs - accept JSON objects, JSON files, or plain strings
# ==========================================================================
def load_text(value: str) -> str:
    """Resolve a CLI argument into text: inline text, or a path to a file."""
    path = Path(value)
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    return value


def parse_profile(raw: str) -> dict[str, Any]:
    """Turn a job profile / CV argument into a dict when it looks like JSON."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"raw": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"raw": parsed}


def profile_summary(profile: dict[str, Any], max_chars: int = 4000) -> str:
    """Flatten a profile dict into a compact, loggable text block."""
    text = json.dumps(profile, indent=2, ensure_ascii=False)
    return text[:max_chars]


# ==========================================================================
# 3. Stage A - subagent: what do we still need to know?
# ==========================================================================
PLANNER_SYSTEM = (
    "You are the research planner for an interview preparation tool.\n"
    "You are given a candidate CV and a Job Profile.\n"
    "Decide what facts are worth researching before writing mock interview "
    "questions for this candidate, so the questions and the rubric are "
    "grounded in the real role rather than generic.\n\n"
    "Reply with EXACTLY one line:\n"
    "    RESEARCH: <comma-separated search queries>\n"
    "or\n"
    "    READY: <why no research is needed>\n\n"
    "Use 2 to 4 short, specific queries (<= 12 words each). No preamble."
)


def plan_research(job_profile: dict[str, Any], cv: dict[str, Any]) -> list[str]:
    """Ask the LLM which research topics this specific job + CV needs."""
    prompt = (
        "JOB PROFILE:\n" + profile_summary(job_profile) +
        "\n\nCV:\n" + profile_summary(cv) + "\n\nWhat should be researched?"
    )
    completion = complete(
        [{"role": "system", "content": PLANNER_SYSTEM},
         {"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.3,
    )
    queries: list[str] = []
    for line in completion.text.splitlines():
        if line.strip().upper().startswith("RESEARCH:"):
            blob = line.split(":", 1)[1]
            queries = [q.strip(" -•\t") for q in blob.split(",") if q.strip(" -•\t")]
            break
    return queries[:4]


# ==========================================================================
# 4. Stage B - research loop (TinyFish search + webfetch, via assistant.ai)
# ==========================================================================
RESEARCHER_SYSTEM = (
    "You are a meticulous technical researcher preparing interview questions.\n"
    "You have exactly two tools:\n"
    "    SEARCH: <query>     -> ranked web results (TinyFish)\n"
    "    FETCH: <url>        -> full readable text of one of those results\n\n"
    "Rules for every reply:\n"
    "- Emit ONE tool line and nothing else. Never write URLs you were not given.\n"
    "- After 3 to 6 tool calls, reply with exactly:\n"
    "      FINAL:\n"
    "      <a bullet list of the facts that matter for this interview>\n\n"
    "  Cite each fact with the source URL in parentheses. No markdown headings."
)


def do_research(
    topic: str, queries: list[str], callback=None
) -> tuple[list[ContextChunk], str]:
    """Run the retrieval loop.

    Returns ``(chunks, summary)``: every passage gathered by SEARCH and FETCH,
    plus the model's own final summary when it produced one (otherwise a
    compression of the passages).
    """
    report = callback or (lambda _msg: None)
    chunks: list[ContextChunk] = []
    sources: set[str] = set()
    seen: set[str] = set()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": RESEARCHER_SYSTEM},
        {"role": "user", "content": f"Interview preparation brief:\n{topic}\n\nBegin with SEARCH."},
    ]
    max_steps = 10
    summary = ""

    for step in range(1, max_steps + 1):
        try:
            completion = complete(messages, max_tokens=4096, temperature=0.3)
        except AiError as exc:
            # Retries already happened inside complete(); stop the loop.
            print(f"[research] stopping early: {exc}", file=sys.stderr)
            break
        reply = completion.text.strip()
        report(reply)

        line = reply.splitlines()[0].strip() if reply else ""
        upper = line.upper()

        if upper.startswith("SEARCH:"):
            query = line.split(":", 1)[1].strip()
            if not query:
                messages.append({"role": "user",
                                 "content": "SEARCH needs a query. Try again."})
                continue
            results = search_web(query, purpose=topic[:2000])
            for chunk in results:
                if chunk.source and chunk.source not in sources:
                    sources.add(chunk.source)
                    chunks.append(chunk)
            body = "\n".join(
                f"- {c.text.splitlines()[0] if c.text else ''} <{c.source}>"
                for c in results[:6]
            ) or "(no results)"
            messages.append({"role": "assistant", "content": reply})
            messages.append({
                "role": "user",
                "content": f"RESULTS for {query!r}:\n{body}\n\n"
                           "Use SEARCH again, FETCH a URL, or reply FINAL.",
            })
        elif upper.startswith("FETCH:"):
            url = line.split(":", 1)[1].strip()
            if not url:
                messages.append({"role": "user", "content": "FETCH needs a URL. Try again."})
                continue
            if url in seen:
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user",
                                 "content": "Already fetched that page. Use a different "
                                            "source or reply FINAL."})
                continue
            seen.add(url)
            try:
                chunk = fetch_page(url)
            except AiError as exc:
                messages.append({"role": "user",
                                 "content": f"That fetch failed: {exc}. Use another source."})
                continue
            sources.add(url)
            chunks.append(chunk)
            messages.append({"role": "assistant", "content": reply})
            messages.append({
                "role": "user",
                "content": f"PAGE TEXT ({url}):\n{chunk.text[:3000]}\n\n"
                           "Use SEARCH again, FETCH a URL, or reply FINAL.",
            })
        elif upper.startswith("FINAL:"):
            summary = reply.split(":", 1)[1].strip()
            break
        else:
            # No tool line and no FINAL marker - treat the whole reply as the
            # closing summary.
            summary = reply
            break

        if step >= max_steps - 2:
            messages.append({
                "role": "user",
                "content": f"You have used {step} of {max_steps} steps. "
                           "Reply FINAL: now with the facts you have.",
            })

    if not summary:
        summary = _summarise_chunks(chunks)
    return chunks, summary


def _summarise_chunks(chunks: list[ContextChunk]) -> str:
    """Compress the gathered passages into a fact list through the LLM."""
    if not chunks:
        return ""
    brief = "\n\n".join(
        f"SOURCE {i}: {c.source}\n{c.text[:1200]}" for i, c in enumerate(chunks, 1)
    )
    try:
        completion = complete(
            [
                {"role": "system",
                 "content": "Summarise the research for an interviewer. Reply with a "
                            "bullet list of facts, each with its source URL in "
                            "parentheses. No markdown headings."},
                {"role": "user", "content": brief},
            ],
            max_tokens=1024,
            temperature=0.3,
        )
    except AiError as exc:
        print(f"[research] summary unavailable: {exc}", file=sys.stderr)
        return "\n".join(f"- {c.text[:200]} ({c.source})" for c in chunks[:8])
    return completion.text.strip()


def research_notes(topic: str, queries: list[str]) -> tuple[str, list[str]]:
    """Run the research loop and return the summary plus the source URLs used."""
    chunks, summary = do_research(topic, queries)
    sources: list[str] = []
    for chunk in chunks:
        if chunk.source and chunk.source not in sources:
            sources.append(chunk.source)
    return (summary or ""), sources


# ==========================================================================
# 5. Stage C - generate questions + rubrics
# ==========================================================================
WRITER_SYSTEM = (
    "You are a senior technical interviewer writing mock interview questions.\n\n"
    "You are given: a Job Profile, a CV, and research notes.\n\n"
    "Write 3 questions that fit THIS candidate and THIS role. Mix behavioral "
    "and technical. Each question needs a rubric with 3 criteria and explicit "
    "points summing to max_score (use 10).\n\n"
    "Reply with ONLY a JSON object, no markdown fence, no commentary:\n"
    "{\"questions\": [{\"question\": \"...\", \"category\": \"behavioral|technical\",\n"
    "  \"why\": \"...\", \"rubric\": {\"max_score\": 10, \"criteria\":\n"
    "  [{\"name\": \"...\", \"points\": 3, \"good\": \"what a strong answer covers\"}]}}]}"
)


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object in the reply")
    candidate = text[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Common failure: trailing commas.
        cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
        return json.loads(cleaned)


def generate_questions(job_profile: dict[str, Any], cv: dict[str, Any],
                       notes: str, sources: list[str]) -> dict[str, Any]:
    """Write the mock interview questions (plus a rubric for each)."""
    prompt = (
        "JOB PROFILE:\n" + profile_summary(job_profile) +
        "\n\nCV:\n" + profile_summary(cv) +
        "\n\nRESEARCH NOTES:\n" + (notes or "(none available)") +
        (("\n\nSOURCES YOU MAY CITE:\n" + "\n".join(sources)) if sources else "")
    )
    completion = complete(
        [
            {"role": "system", "content": WRITER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2048,
        temperature=0.6,
    )
    payload = _extract_json(completion.text)
    questions = payload.get("questions") or []
    if not questions:
        raise ValueError("writer returned no questions")
    return {"source": "nvidia", "questions": questions, "research_notes": notes,
            "sources": sources}


# ==========================================================================
# 6. Stage D - grader (turn-1 answer, or research first, then answer)
# ==========================================================================
GRADER_SYSTEM = (
    "You are a strict but encouraging interview grader.\n\n"
    "You are given: a question, a scoring rubric, and the candidate's answer.\n\n"
    "Rules:\n"
    "1. Decide whether you can grade this correctly as-is.\n"
    "2. If the answer is a knowledge claim you cannot verify from the rubric "
    "alone (a factual, technical, or current-events question), you MAY research "
    "first. To do so reply with EXACTLY one line:\n"
    "       NEEDS_RESEARCH: <one search query>\n"
    "   and nothing else. You will get the results and then grade.\n"
    "3. Otherwise, grade immediately. Format:\n"
    "       Good. {feedback}\n"
    "   or\n"
    "       Needs Improvement. {feedback}\n"
    "   The first word must be 'Good' only when the answer clearly meets the "
    "rubric; otherwise 'Needs Improvement'. Then give 2-4 sentences of specific "
    "feedback referencing the rubric criteria, and end with one line:\n"
    "       SCORE: <0-max_score> <short justification>\n"
    "Never invent facts. Never output markdown."
)

SCORING_HELP = (
    "Grade the answer against this rubric. Be concise, and start your reply "
    "with either 'Good.' or 'Needs Improvement.'\n\n"
    "QUESTION: {question}\n\n"
    "RUBRIC: {rubric}\n\n"
    "ANSWER: {answer}"
)


class _NeedsResearch(Exception):
    """Raised when the grader decides it must look something up first."""

    def __init__(self, query: str) -> None:
        super().__init__(query)
        self.query = query


def _grade_now(question: str, answer: str, rubric: dict[str, Any],
               notes: list[ContextChunk], first: bool) -> dict[str, Any]:
    """Ask the model to grade, possibly deciding that it needs research first."""
    system = GRADER_SYSTEM if first else GRADER_SYSTEM + (
        "\n\nYou already asked for research. Grade with what you have now."
    )
    body = SCORING_HELP.format(question=question, rubric=json.dumps(rubric), answer=answer)
    if notes:
        body += "\n\nRESEARCH:\n" + "\n".join(f"- {c.text[:600]} <{c.source}>" for c in notes[-3:])
    completion = complete(
        [{"role": "system", "content": system},
         {"role": "user", "content": body}],
        max_tokens=1024,
        temperature=0.2,
    )
    reply = completion.text.strip()
    if first and "NEEDS_RESEARCH:" in reply.upper():
        query = reply.split(":", 1)[1].splitlines()[0].strip()
        if query:
            raise _NeedsResearch(query)
    return {"raw": reply, "model": completion.model}


def grade_answer(question: str, answer: str, rubric: dict[str, Any]) -> dict[str, Any]:
    """Grade one answer, researching first when the grader asks for it."""
    result: dict[str, Any]
    try:
        first = _grade_now(question, answer, rubric, [], True)
    except _NeedsResearch as need:
        notes: list[ContextChunk] = []
        if need.query:
            notes = _research_for_grading(need.query)
        second = _grade_now(question, answer, rubric, notes, False)
        result = _parse_grade(second["raw"], rubric)
        result["research_notes"] = [n.source for n in notes]
        result["research_query"] = need.query
        return result
    return _parse_grade(first["raw"], rubric)


def _research_for_grading(query: str) -> list[ContextChunk]:
    """One small research round used by the grader."""
    return search_web(query, purpose=query)


_VERDICTS = ("needs improvement.", "good.")
_SCORE_RE = re.compile(r"SCORE:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
# Matches the whole trailing score phrase, e.g. "SCORE: 10 Because ..." up to
# the end of the text, wherever the model put it.
_SCORE_PHRASE_RE = re.compile(
    r"\s*SCORE:\s*[0-9.]+[\s\S]*$", re.IGNORECASE
)


def _parse_grade(reply: str, rubric: dict[str, Any]) -> dict[str, Any]:
    """Normalise the grader's reply into verdict / score / feedback.

    Output contract: ``Good.`` or ``Needs Improvement.`` followed by the
    feedback text, with the machine-readable ``SCORE:`` line removed.
    """
    text = reply.strip()

    verdict = "Needs Improvement."
    body = text
    lowered = text.lower()
    for candidate in _VERDICTS:
        if lowered.startswith(candidate):
            verdict = candidate.capitalize() if candidate == "good." else "Needs Improvement."
            body = text[len(candidate):]
            break

    score_match = _SCORE_RE.search(text)
    score = None
    if score_match:
        try:
            score = int(float(score_match.group(1)))
        except ValueError:
            score = None
        body = _SCORE_PHRASE_RE.sub("", body)

    body = body.strip()
    if not body:
        body = text
    rendered = f"{verdict} {body}".strip()
    return {
        "source": "nvidia",
        "verdict": verdict,
        "feedback": body,
        "rendered": rendered,
        "score": score,
        "rubric_max": rubric.get("max_score") if isinstance(rubric, dict) else None,
        "research_notes": [],
    }


# ==========================================================================
# 7. Commands
# ==========================================================================
def run_fallback(stage: str, error: BaseException, **context: Any) -> dict[str, Any]:
    """Report the failure and hand back mock data.

    ``context`` carries the inputs of the failing stage so the mock can still
    reflect what it was asked about.
    """
    print(f"[fallback] {stage}: {type(error).__name__}: {error}", file=sys.stderr)
    if stage == "generate":
        return _mock_questions(context.get("job_profile", ""),
                               context.get("cv", ""))
    return _mock_grade(context.get("rubric", {}))


def cmd_generate(args: argparse.Namespace) -> int:
    started = time.time()
    job_profile = parse_profile(load_text(args.job))
    cv = parse_profile(load_text(args.cv))

    try:
        queries = plan_research(job_profile, cv)
        print(f"[plan] research topics: {queries or '(none)'}")
        if queries:
            brief = (
                "JOB PROFILE:\n" + profile_summary(job_profile) +
                "\n\nCV:\n" + profile_summary(cv)
            )
            notes, sources = research_notes(brief, queries)
        else:
            notes, sources = "", []
        payload = generate_questions(job_profile, cv, notes, sources)
    except (AiError, ValueError) as exc:
        payload = run_fallback("generate", exc, job_profile=args.job, cv=args.cv)
    payload["elapsed_s"] = round(time.time() - started, 1)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"[saved] {args.out}")
    print(text)
    return 0


def cmd_grade(args: argparse.Namespace) -> int:
    started = time.time()
    rubric_text = load_text(args.rubric)
    try:
        rubric = json.loads(rubric_text)
    except json.JSONDecodeError:
        rubric = {"max_score": 10, "criteria": [{"name": "general", "points": 10,
                                                 "good": rubric_text[:500]}]}
    try:
        payload = grade_answer(args.question, args.answer, rubric)
    except (AiError, ValueError) as exc:
        payload = run_fallback("grade", exc, question=args.question,
                               answer=args.answer, rubric=rubric)

    payload["elapsed_s"] = round(time.time() - started, 1)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"[saved] {args.out}")
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Job Profile + CV -> questions + rubrics")
    gen.add_argument("--job", required=True, help="job profile: JSON, a .json path, or text")
    gen.add_argument("--cv", required=True, help="CV: JSON, a .json path, or text")
    gen.add_argument("--out", help="write the JSON result here too")
    gen.set_defaults(func=cmd_generate)

    gr = sub.add_parser("grade", help="Question + rubric + answer -> verdict + feedback")
    gr.add_argument("--question", required=True)
    gr.add_argument("--answer", required=True)
    gr.add_argument("--rubric", required=True, help="rubric: JSON, a .json path, or text")
    gr.add_argument("--out", help="write the JSON result here too")
    gr.set_defaults(func=cmd_grade)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
