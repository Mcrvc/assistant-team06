"""Evaluate follow-up selection on fictional, labelled interview answers."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from assistant.interview_follow_up import generate


def main() -> None:
    cases = json.loads(Path(__file__).with_name("follow_up_cases.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        start = time.monotonic()
        try:
            proposal = generate(case["question"], case["answer"], [])
            result = {"id": case["id"], "expected": case["expected_ask"],
                      "asked": proposal is not None,
                      "gap_matches": proposal is None or proposal["gap"] == case["expected_gap"]}
        except Exception as exc:
            result = {"id": case["id"], "expected": case["expected_ask"],
                      "asked": False, "error": type(exc).__name__}
        result["seconds"] = round(time.monotonic() - start, 2)
        results.append(result)
        print(json.dumps(result), flush=True)
    errors = sum("error" in result for result in results)
    unnecessary = sum(result["asked"] and not result["expected"] for result in results)
    missed = sum(not result["asked"] and result["expected"] for result in results)
    wrong_gap = sum(result["asked"] and result["expected"] and not result.get("gap_matches") for result in results)
    print(json.dumps({"cases": len(results), "provider_errors": errors,
                      "unnecessary_questions": unnecessary, "missed_questions": missed,
                      "wrong_gap": wrong_gap,
                      "mean_seconds": round(sum(r["seconds"] for r in results) / len(results), 2)}))


if __name__ == "__main__":
    main()
