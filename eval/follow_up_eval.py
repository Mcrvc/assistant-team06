"""Evaluate follow-up selection on fictional, labelled interview answers."""
from __future__ import annotations

import json
import argparse
import hashlib
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from assistant.interview_follow_up import generate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("follow_up_cases.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    raw = args.cases.read_bytes()
    cases = json.loads(raw.decode("utf-8"))
    if args.ids:
        known = {case["id"] for case in cases}
        if set(args.ids) - known:
            parser.error("Unknown case id")
        cases = [case for case in cases if case["id"] in args.ids]
    if not cases or args.repeat < 1:
        parser.error("Select at least one case and a positive repeat count")
    cases = [{**case, "repetition": repetition + 1}
             for repetition in range(args.repeat) for case in cases]
    results = []
    from assistant.ai import get_config
    from assistant import interview_follow_up
    model = get_config().model
    original_reply = interview_follow_up._json_reply
    checks = []

    def traced_reply(messages):
        result = original_reply(messages)
        checks.append(result)
        return result

    if args.trace:
        interview_follow_up._json_reply = traced_reply
    for case in cases:
        checks.clear()
        start = time.monotonic()
        try:
            proposal = generate(case["question"], case["answer"], case.get("previous", []))
            result = {"id": case["id"], "expected": case["expected_ask"],
                      "asked": proposal is not None,
                      "gap_matches": proposal is None or proposal["gap"] == case["expected_gap"],
                      "criterion_matches": proposal is None or "expected_criterion_index" not in case
                      or proposal["criterion_index"] == case["expected_criterion_index"],
                      "proposal": proposal}
        except Exception as exc:
            result = {"id": case["id"], "expected": case["expected_ask"],
                      "asked": None, "error": type(exc).__name__}
        result["category"] = case.get("category", "baseline")
        result["language"] = case.get("language", "en")
        result["repetition"] = case["repetition"]
        if args.trace:
            result["checks"] = list(checks)
        result["seconds"] = round(time.monotonic() - start, 2)
        results.append(result)
        print(json.dumps(result), flush=True)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps({
                "model": model, "corpus_sha256": hashlib.sha256(raw).hexdigest(),
                "completed": len(results), "total": len(cases), "results": results,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = sum("error" in result for result in results)
    unnecessary = sum(result["asked"] is True and not result["expected"] for result in results)
    missed = sum(result["asked"] is False and result["expected"] for result in results)
    wrong_gap = sum(result["asked"] is True and result["expected"] and not result.get("gap_matches")
                    for result in results)
    wrong_criterion = sum(result["asked"] is True and result["expected"]
                          and not result.get("criterion_matches") for result in results)
    summary = {"cases": len(results), "provider_errors": errors,
               "unnecessary_questions": unnecessary, "missed_questions": missed,
               "wrong_gap": wrong_gap,
               "wrong_criterion": wrong_criterion,
               "mean_seconds": round(statistics.mean(r["seconds"] for r in results), 2),
               "median_seconds": round(statistics.median(r["seconds"] for r in results), 2),
               "max_seconds": max(r["seconds"] for r in results)}
    print(json.dumps(summary))
    if args.output:
        report = json.loads(args.output.read_text(encoding="utf-8"))
        report["summary"] = summary
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    interview_follow_up._json_reply = original_reply


if __name__ == "__main__":
    main()
