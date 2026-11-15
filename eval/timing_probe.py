#!/usr/bin/env python3
"""Latency probe for the interview AI module (aiworker).

Measures wall-clock latency of the two interview AI stages through the REAL
module so the team can choose ``INTERVIEW_AI_TIMEOUT_S``:

  * generate  -> aiworker.generate_questions(job, {"raw": cv}, "", [])
                 (notes=""/sources=[] so the researcher path stays the
                 module's own business; the probe measures the full call)
  * grade     -> aiworker.grade_answer_with_evidence(question, answer, rubric)

The probe calls ``aiworker`` directly (the module ``TeamInterviewAI`` wraps,
see ``src/assistant/interview_ai.py`` whose seam caps INTERVIEW_AI_TIMEOUT_S
between 1 and 60 seconds; the current default is 20). ``assistant.ai`` reads
config (including the gitignored ``.env``) lazily, so this script never touches
keys itself and never prints config values.

Usage (from the repo root, virtualenv active):
    $env:PYTHONPATH = "src"; python eval/timing_probe.py --dry-run
    $env:PYTHONPATH = "src"; python eval/timing_probe.py --generate 5 --grade 8
    $env:PYTHONPATH = "src"; python eval/timing_probe.py --out data/private/eval/timing.json

Exit codes: 0 = both stages under budget (or dry-run), 3 = a p95 exceeded the
budget, 2 = unexpected setup error (bad fixture, import failure, ...).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
DEFAULT_OUT = REPO_ROOT / "data" / "private" / "eval" / "timing.json"
# Retry policy of assistant.ai: 2 retries, 5 s apart -> up to 3 attempts.
# Seam bounds for INTERVIEW_AI_TIMEOUT_S (src/assistant/interview_ai.py).
TIMEOUT_MIN_S = 1.0
TIMEOUT_MAX_S = 60.0


# ==========================================================================
# Fakes - NO real PII anywhere: invented JD, invented CV, invented answer.
# ==========================================================================
FAKE_JD: dict[str, Any] = {
    "title": "Backend Engineer (Python)",
    "company": "Acme Tech",
    "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "microservices"],
    "description": (
        "We are building a high-throughput API platform. You will own services "
        "that handle thousands of requests per second, so you must design "
        "carefully around rate limiting and caching. Typical work: tuning "
        "PostgreSQL queries, operating Redis clusters, and keeping our "
        "microservices reliable as traffic grows."
    ),
}

FAKE_CV = (
    "Nguyen Van A, ky su phan mem hon 4 nam kinh nghiem. "
    "Tot nghiep Dai hoc Bach Khoa. "
    "Hien tai la backend engineer tai cong ty fintech, xay dung API noi bo cho "
    "he thong thanh toan bang FastAPI va PostgreSQL. "
    "Da toi uu truy van bang index, giam thoi gian phan hoi tu 800ms xuong "
    "200ms nho caching Redis. "
    "Tung thiet ke rate limiter xu ly 5000 yeu cau moi giay. "
    "Thanh thao Docker va giam sat voi Prometheus. "
    "Muon phat trien theo huong microservices va kiem thu tu dong."
)


def _fixed_rubric() -> dict[str, Any]:
    """One fixed rubric: max_score 10, exactly 3 criteria, points sum 10."""
    return {
        "max_score": 10,
        "criteria": [
            {"name": "problem", "points": 3,
             "good": "Mo ta boi canh nghiem trong: he thong, nguoi dung bi anh "
                     "huong va quy mo su co."},
            {"name": "actions", "points": 4,
             "good": "Trinh bay cac buoc giao loi ro rang, cong cu da dung va "
                     "nguyen nhan goc tim thay."},
            {"name": "result", "points": 3,
             "good": "Ket qua do duoc va thay doi cu the sau khi xu ly xong."},
        ],
    }


SAMPLE_QUESTION = (
    "Hay ke ve mot su co production ban da tu debug tu dau den cuoi, "
    "va ban da rut ra bai hoc gi?"
)

SAMPLE_ANSWER = (
    "Nam ngoai toi phu trach dich vu thanh toan cua cong ty, mot buoi toi he "
    "thong bat dau tra ve loi 500 cho khoang 15 phan tram nguoi dung. "
    "Toi nhan canh bao tu Prometheus va kiem tra log cua cac service lien quan. "
    "So sanh ty le loi giua cac endpoint, toi phat hien moi loi deu di qua "
    "cung mot database connection pool bi dat thap hon nhu cau that su. "
    "Toi tang pool size tai cho, theo doi den khi he thong on dinh roi cung "
    "doi dat lai cau hinh dung. "
    "Bai hoc la phai dat gia tri san pool dua tren so lieu that su thay vi "
    "gia tri mac dinh."
)

_DRY_RNG = random.Random(20260514)  # fixed seed: deterministic fake latencies


# ==========================================================================
# Fixture validation - mirrors the module's own _validate_questions()
# ==========================================================================
class FixtureError(Exception):
    """Raised when a probe fixture breaks the module's schema shape."""


def _validate_rubric(rubric: Any, label: str) -> None:
    if not isinstance(rubric, dict):
        raise FixtureError(f"{label}: rubric must be an object, got {type(rubric).__name__}")
    max_score = rubric.get("max_score")
    if isinstance(max_score, bool) or not isinstance(max_score, (int, float)) \
            or float(max_score) != 10.0:
        raise FixtureError(f"{label}: max_score must be the number 10, got {max_score!r}")
    criteria = rubric.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != 3:
        raise FixtureError(f"{label}: expected exactly 3 criteria, got "
                           f"{len(criteria) if isinstance(criteria, list) else 'none'}")
    total = 0.0
    for item in criteria:
        if not isinstance(item, dict):
            raise FixtureError(f"{label}: criterion is not an object")
        points = item.get("points")
        if isinstance(points, bool) or not isinstance(points, (int, float)) \
                or not 0 < float(points) <= 10:
            raise FixtureError(f"{label}: criterion points must be 0-10, got {points!r}")
        total += float(points)
    if abs(total - 10.0) > 1e-6:
        raise FixtureError(f"{label}: points sum to {total}, expected exactly 10")


def validate_fixtures(job: dict, cv: str, rubric: dict, question: str, answer: str) -> None:
    """Check the JD/CV/question/rubric/answer shapes the module demands."""
    if not isinstance(job, dict) or not str(job.get("title", "")).strip():
        raise FixtureError("job profile must be an object with a non-empty 'title'")
    if not isinstance(cv, str) or not cv.strip():
        raise FixtureError("cv must be a non-empty string")
    if not isinstance(question, str) or not question.strip():
        raise FixtureError("question must be a non-empty string")
    words = len(answer.split())
    if not isinstance(answer, str) or not 90 <= words <= 150:
        raise FixtureError(f"answer must be ~120 words (90-150), got {words}")
    _validate_rubric(rubric, "grade rubric")
    print(f"[fixtures] job title, {words}-word Vietnamese answer, rubric (10 / 3 "
          f"criteria / sum 10): OK", flush=True)


# ==========================================================================
# Loading the module (real, not dry-run) - lazily, after offline checks
# ==========================================================================
class ModuleHandle:
    """What the probe needs from aiworker plus the model label (never keys)."""

    def __init__(self) -> None:
        self.generate_questions: Callable[..., dict] | None = None
        self.grade_answer_with_evidence: Callable[..., dict] | None = None
        self.EvidenceRejected: type[BaseException] | None = None
        self.model: str | None = None
        self.import_error: str | None = None

    @property
    def ready(self) -> bool:
        return self.import_error is None


def load_module() -> ModuleHandle:
    """Import assistant.aiworker only when live runs are actually requested."""
    handle = ModuleHandle()
    if str(SRC_DIR) not in sys.path:  # same bootstrap as eval/run.py
        sys.path.insert(0, str(SRC_DIR))
    try:
        from assistant import aiworker  # noqa: PLC0415 - deliberate late import
    except ImportError as exc:
        handle.import_error = f"{type(exc).__name__}: {exc}"
        return handle
    handle.generate_questions = aiworker.generate_questions
    handle.grade_answer_with_evidence = aiworker.grade_answer_with_evidence
    handle.EvidenceRejected = aiworker.EvidenceRejected
    try:
        from assistant.ai import get_config  # noqa: PLC0415 - lazy, reads .env itself
        handle.model = get_config().model  # safe to print: model name, not a key
    except Exception as exc:  # noqa: BLE001 - config optional for the report
        handle.model = "unknown"
        print(f"[warn] config unavailable: {type(exc).__name__}", file=sys.stderr)
    return handle


# ==========================================================================
# Fakes for --dry-run (no network at all)
# ==========================================================================
def _dry_latency(lo: float, hi: float) -> None:
    """Sleep a fake, deterministic latency: mostly fast, a rarely slow outlier
    so dry-run p95 visibly differs from p50 (exercises nearest-rank math)."""
    latency = _DRY_RNG.uniform(lo, hi)
    if _DRY_RNG.random() < 0.12:  # rare slow attempt, like a retry in real life
        latency += _DRY_RNG.uniform(1.0, 2.5)
    time.sleep(latency)


def _dry_generate_questions(job_profile: dict, cv: dict, notes: str, sources: list,
                            **_: Any) -> dict:
    """Fake of aiworker.generate_questions: same result shape, no I/O."""
    _dry_latency(0.05, 1.2)
    return {
        "source": "dry-run",
        "questions": [
            {
                "question": f"[dry-run] Question {i} for {job_profile.get('title', 'the role')}"
                            f" about {job_profile.get('skills', [])[:1]}",
                "category": "technical" if i % 2 else "behavioral",
                "why": "Fake research notes generated offline for smoke-testing.",
                "rubric": _fixed_rubric(),
            }
            for i in range(1, 4)
        ],
        "research_notes": notes,
        "sources": sources,
    }


def _dry_grade_answer_with_evidence(question: str, answer: str, rubric: dict,
                                    **_: Any) -> dict:
    """Fake of grade_answer_with_evidence: same result shape, no I/O."""
    _dry_latency(0.05, 0.8)
    return {
        "score": 7.5,
        "feedback": "Dry-run grade: score and feedback are fake placeholders.",
        "evidence": [answer.strip()[:80]],
        "model": "dry-run",
        "used_fallback": False,
    }


# ==========================================================================
# One measured run of each stage
# ==========================================================================
def run_generate_once(fn: Callable[..., dict], job: dict, cv_text: str,
                      timeout_s: float | None) -> dict[str, Any]:
    """Time one generate call. ``fn`` is either the real module function or a
    dry-run fake; the caller decides. Notes="" and sources=[] so the researcher
    path stays the module's own business and the probe sees the full call."""
    kwargs: dict[str, Any] = {} if timeout_s is None else {"timeout_s": timeout_s}
    start = time.perf_counter()
    try:
        result = fn(job, {"raw": cv_text}, "", [], **kwargs)
    except Exception as exc:  # noqa: BLE001 - record every failure mode
        return {
            "elapsed_s": round(time.perf_counter() - start, 4),
            "status": "fail",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "elapsed_s": round(time.perf_counter() - start, 4),
        "status": "ok",
        "questions": len(result.get("questions") or []),
        "source": result.get("source"),
    }


def run_grade_once(fn: Callable[..., dict], rejected: type[BaseException] | None,
                   question: str, answer: str, rubric: dict,
                   timeout_s: float | None) -> dict[str, Any]:
    """Time one grading call; EvidenceRejected is its own outcome ('refused')."""
    kwargs: dict[str, Any] = {} if timeout_s is None else {"timeout_s": timeout_s}
    start = time.perf_counter()
    try:
        result = fn(question, answer, rubric, **kwargs)
    except Exception as exc:  # noqa: BLE001 - includes EvidenceRejected
        if rejected is not None and isinstance(exc, rejected):
            return {
                "elapsed_s": round(time.perf_counter() - start, 4),
                "status": "refused",
                "refused_code": getattr(exc, "code", "unknown"),
            }
        return {
            "elapsed_s": round(time.perf_counter() - start, 4),
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "elapsed_s": round(time.perf_counter() - start, 4),
        "status": "ok",
        "score": result.get("score"),
        "used_fallback": result.get("used_fallback"),
    }


# ==========================================================================
# Aggregation
# ==========================================================================
class Stats:
    """n, ok, fail, refused + latency breakdown over a stage's runs."""

    def __init__(self) -> None:
        self.latencies: list[float] = []

    @property
    def n(self) -> int:
        return len(self.latencies)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.latencies)

    @property
    def p50(self) -> float:
        return _percentile(self.latencies, 0.50)

    @property
    def p95(self) -> float:
        return _percentile(self.latencies, 0.95)

    @property
    def min(self) -> float:
        return min(self.latencies)

    @property
    def max(self) -> float:
        return max(self.latencies)


def _percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile: smallest value >= q of the sorted data."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def aggregate(runs: list[dict]) -> dict[str, Any]:
    ok = [r for r in runs if r["status"] == "ok"]
    if not ok:
        return {"n": len(runs), "ok": 0,
                "fail": sum(1 for r in runs if r["status"] in ("fail", "error")),
                "refused": sum(1 for r in runs if r["status"] == "refused"),
                "mean": 0.0, "p50": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    stats = Stats()
    for r in ok:
        stats.latencies.append(r["elapsed_s"])
    return {
        "n": len(runs),
        "ok": len(ok),
        "fail": sum(1 for r in runs if r["status"] in ("fail", "error")),
        "refused": sum(1 for r in runs if r["status"] == "refused"),
        "mean": round(stats.mean, 4),
        "p50": round(stats.p50, 4),
        "p95": round(stats.p95, 4),
        "min": round(stats.min, 4),
        "max": round(stats.max, 4),
    }


# ==========================================================================
# Output
# ==========================================================================
TABLE_HEADER = f"{'stage':<22}{'n':>4}{'ok':>4}{'miss':>6}{'mean':>9}{'p50':>9}{'p95':>9}{'min':>9}{'max':>9}"


def print_table(generate_agg: dict, grade_agg: dict) -> None:
    print()
    print(TABLE_HEADER)
    print("-" * len(TABLE_HEADER))
    for stage, agg in (("generate_questions", generate_agg), ("grade_answer", grade_agg)):
        miss = agg["fail"] + agg["refused"]
        print(f"{stage:<22}{agg['n']:>4}{agg['ok']:>4}{miss:>6}"
              f"{agg['mean']:>8.2f}s{agg['p50']:>8.2f}s{agg['p95']:>8.2f}s"
              f"{agg['min']:>8.2f}s{agg['max']:>8.2f}s")
    print()


def print_verdict(generate_agg: dict, grade_agg: dict, budget: float,
                  dry_run: bool) -> tuple[bool, bool]:
    """Vietnamese verdict lines; returns (generate_ok, grade_ok)."""
    g = generate_agg["p95"]
    s = grade_agg["p95"]
    g_ok, s_ok = g <= budget, s <= budget
    worst = max(g, s)
    floor_s = min(TIMEOUT_MAX_S, max(1.0, math.ceil(worst)))
    suggestion = min(TIMEOUT_MAX_S, max(20.0, floor_s + 5))

    if dry_run:
        print("KET QUA DRY-RUN (do tre gia lap, khong co loi goi API that):")
    print(f"- p95 generate_questions: {g:.2f}s {('OK' if g_ok else 'VUOT NGAN SACH')}"
          f" | p95 grade_answer: {s:.2f}s {('OK' if s_ok else 'VUOT NGAN SACH')}"
          f" | ngan sach: {budget:.1f}s.")
    if g_ok and s_ok:
        print(f"-> Ca hai giai doan deu duoi ngan sach: INTERVIEW_AI_TIMEOUT_S nen tu "
              f"{floor_s:.1f}s tro len (trong khoang [1, 60]), vi du {suggestion:.0f}s.")
    else:
        print(f"-> Co giai doan vuot ngan sach: khong nen giu mac dinh 20s. Hay tang "
              f"INTERVIEW_AI_TIMEOUT_S len gan {floor_s:.1f}s (tran seam la 60s) hoac "
              f"toi uu module (rut bo tai/rate limiting/caching) de giam thoi gian.")
    print("Luu y quan trong: assistant.ai retry toi da 3 lan moi yeu cau, 5s giua cac "
          "lan, nen truong hop xau nhat gan 3x thoi gian do - ngan sach phai de du "
          "bu do. Seam gioi han INTERVIEW_AI_TIMEOUT_S trong [1, 60] va hien mac dinh 20.")
    return g_ok, s_ok


def write_report(out_path: Path, payload: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


# ==========================================================================
# CLI
# ==========================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="timing_probe",
        description="Measure latency of interview question generation and answer "
                    "grading through assistant.aiworker (no live calls with --dry-run).",
    )
    parser.add_argument("--generate", type=int, default=3, metavar="N",
                        help="number of generate runs (default 3)")
    parser.add_argument("--grade", type=int, default=5, metavar="N",
                        help="number of grading runs (default 5)")
    parser.add_argument("--job", metavar="PATH",
                        help="optional path to a JSON file with a job profile dict "
                             "(default: built-in fake JD)")
    parser.add_argument("--cv", metavar="TEXT",
                        help="optional CV text (default: built-in fake Vietnamese CV)")
    parser.add_argument("--budget", type=float, default=45.0, metavar="FLOAT",
                        help="latency budget in seconds p95 is compared against "
                             "(default 45.0)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), metavar="PATH",
                        help=f"JSON report path (default {DEFAULT_OUT.relative_to(REPO_ROOT)})")
    parser.add_argument("--dry-run", action="store_true",
                        help="exercise everything except the actual API calls: fake "
                             "results and latencies, same output shape, JSON gets "
                             "'dry_run': true")
    parser.add_argument("--timeout-s", type=float, default=None, metavar="FLOAT",
                        help="optional timeout_s passed to the module calls "
                             "(default: let the module choose)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        job = dict(FAKE_JD)
        if args.job:
            job_path = Path(args.job)
            if not job_path.is_absolute():
                job_path = Path.cwd() / job_path
            with open(job_path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if not isinstance(loaded, dict):
                print(f"Setup error: job profile must be a JSON object, got "
                      f"{type(loaded).__name__}", file=sys.stderr)
                return 2
            job = loaded

        cv_text = args.cv if args.cv else FAKE_CV
        rubric = _fixed_rubric()
        validate_fixtures(job, cv_text, rubric, SAMPLE_QUESTION, SAMPLE_ANSWER)

        handle = load_module()
        dry = args.dry_run or not handle.ready
        if handle.import_error is not None:
            print(f"[warn] module import failed, running all stages as dry-run: "
                  f"{handle.import_error}", file=sys.stderr)
        if handle.ready:
            gen_fn = handle.generate_questions
            grade_fn = handle.grade_answer_with_evidence
            rejected = handle.EvidenceRejected
        else:
            gen_fn = _dry_generate_questions
            grade_fn = _dry_grade_answer_with_evidence
            rejected = None

        generate_runs: list[dict] = []
        for index in range(max(1, args.generate)):
            run = run_generate_once(_dry_generate_questions if dry else gen_fn,
                                    job, cv_text, args.timeout_s)
            run["run"] = index + 1
            generate_runs.append(run)
            _progress("generate", run)

        grade_runs: list[dict] = []
        for index in range(max(1, args.grade)):
            run = run_grade_once(_dry_grade_answer_with_evidence if dry else grade_fn,
                                 rejected, SAMPLE_QUESTION, SAMPLE_ANSWER,
                                 rubric, args.timeout_s)
            run["run"] = index + 1
            grade_runs.append(run)
            _progress("grade", run)

        generate_agg = aggregate(generate_runs)
        grade_agg = aggregate(grade_runs)

        print_table(generate_agg, grade_agg)
        generate_ok, grade_ok = print_verdict(generate_agg, grade_agg, args.budget,
                                              dry)

        payload = {
            "tool": "eval/timing_probe.py",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget_s": args.budget,
            "timeout_s": args.timeout_s,
            "dry_run": bool(args.dry_run),
            "model": "dry-run" if args.dry_run else (handle.model or "unknown"),
            "counts": {"generate": len(generate_runs), "grade": len(grade_runs)},
            "aggregates": {"generate_questions": generate_agg,
                           "grade_answer": grade_agg},
            "runs": {"generate": generate_runs, "grade": grade_runs},
        }
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        write_report(out_path, payload)
        print(f"[saved] {out_path}")

        if generate_agg["ok"] == 0 or grade_agg["ok"] == 0:
            print("Setup error: no run produced a usable result - check the module "
                  "import, keys/config and network.", file=sys.stderr)
            return 2
        if args.dry_run or (generate_ok and grade_ok):
            return 0
        return 3
    except FixtureError as exc:
        print(f"Setup error: fixture invalid - {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"Setup error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def _progress(stage: str, run: dict) -> None:
    """One compact live line per run; no config, no keys."""
    status = run["status"]
    elapsed = run["elapsed_s"]
    if status == "ok":
        detail = (f"questions={run.get('questions')} source={run.get('source')}"
                  if stage == "generate" else
                  f"score={run.get('score')} used_fallback={run.get('used_fallback')}")
        print(f"[{stage} {run['run']}] ok {elapsed:.2f}s {detail}", flush=True)
    elif status == "refused":
        print(f"[{stage} {run['run']}] refused({run.get('refused_code')}) "
              f"{elapsed:.2f}s", flush=True)
    else:
        print(f"[{stage} {run['run']}] {status} {elapsed:.2f}s {run.get('error')}",
              flush=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[abort] interrupted by user", file=sys.stderr)
        raise SystemExit(2) from None