"""Compare complete runs on identical corpora, preserving original result files."""
import argparse
import json
from pathlib import Path


def summarize(rows, overrides):
    totals = {"cases": len(rows), "correct": 0, "unnecessary": 0,
              "missed": 0, "wrong_target": 0, "errors": 0}
    failures = []
    for row in rows:
        expected = overrides.get(row["id"], {}).get("expected_ask", row["expected"])
        if "error" in row or row["asked"] is None:
            kind = "errors"
        elif row["asked"] and not expected:
            kind = "unnecessary"
        elif not row["asked"] and expected:
            kind = "missed"
        elif expected and (not row["gap_matches"] or not row.get("criterion_matches", True)):
            kind = "wrong_target"
        else:
            kind = "correct"
        totals[kind] += 1
        if kind != "correct":
            failures.append({"id": row["id"], "kind": kind})
    totals["mean_seconds"] = round(sum(row["seconds"] for row in rows) / len(rows), 2)
    return {"summary": totals, "failures": failures}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", nargs="+", type=Path, required=True)
    parser.add_argument("--after", nargs="+", type=Path, required=True)
    parser.add_argument("--label-review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.before) != len(args.after):
        parser.error("Provide one after file for each before file")
    overrides = {}
    if args.label_review:
        review = json.loads(args.label_review.read_text(encoding="utf-8"))
        overrides = {row["id"]: row for row in review["overrides"]}
    before, after, groups = [], [], []
    for left_path, right_path in zip(args.before, args.after):
        left, right = [json.loads(path.read_text(encoding="utf-8")) for path in (left_path, right_path)]
        if left["corpus_sha256"] != right["corpus_sha256"]:
            parser.error("Input hashes differ")
        for report in (left, right):
            if report["completed"] != report["total"] or len(report["results"]) != report["total"]:
                parser.error("Incomplete run cannot be compared")
        left_ids = [row["id"] for row in left["results"]]
        right_ids = [row["id"] for row in right["results"]]
        if left_ids != right_ids or len(set(left_ids)) != len(left_ids):
            parser.error("Case IDs differ or contain repeats")
        before.extend(left["results"])
        after.extend(right["results"])
        groups.append({"before_file": str(left_path), "after_file": str(right_path),
                       "corpus_sha256": left["corpus_sha256"],
                       "before": summarize(left["results"], overrides),
                       "after": summarize(right["results"], overrides)})
    if len({row["id"] for row in before}) != len(before):
        parser.error("Cases overlap across groups")
    report = {"label_review": str(args.label_review) if args.label_review else None,
              "before": summarize(before, overrides), "after": summarize(after, overrides),
              "groups": groups}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"before": report["before"]["summary"], "after": report["after"]["summary"]}))


if __name__ == "__main__":
    main()
