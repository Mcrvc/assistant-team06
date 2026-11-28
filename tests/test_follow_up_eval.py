"""The evaluation must distinguish provider failures from selection mistakes."""
import importlib.util
import json
from pathlib import Path
import sys


def test_eval_keeps_provider_errors_separate_from_missed_questions(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "eval" / "follow_up_eval.py"
    spec = importlib.util.spec_from_file_location("follow_up_eval", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = [
        {"id": "unnecessary", "expected_ask": False, "expected_gap": None},
        {"id": "missed", "expected_ask": True, "expected_gap": "personal_action_missing"},
        {"id": "provider-error", "expected_ask": True, "expected_gap": "personal_action_missing"},
    ]
    for case in cases:
        case.update(question={"text": "Question", "criteria": ["Actions"]}, answer=case["id"])
    cases_path, output = tmp_path / "cases.json", tmp_path / "result.json"
    cases_path.write_text(json.dumps(cases), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["follow_up_eval.py", "--cases", str(cases_path), "--output", str(output)])

    def generate(question, answer, previous):
        if answer == "provider-error":
            raise TimeoutError()
        return {"gap": "personal_action_missing"} if answer == "unnecessary" else None

    monkeypatch.setattr(module, "generate", generate)
    module.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["completed"] == 3
    assert report["summary"]["provider_errors"] == 1
    assert report["summary"]["unnecessary_questions"] == 1
    assert report["summary"]["missed_questions"] == 1
    assert report["results"][2]["asked"] is None
    assert len(report["corpus_sha256"]) == 64


def test_label_review_is_applied_equally_without_changing_raw_rows():
    path = Path(__file__).resolve().parents[1] / "eval" / "compare_follow_up_eval.py"
    spec = importlib.util.spec_from_file_location("compare_follow_up_eval", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [{"id": "reviewed", "expected": True, "asked": False,
             "gap_matches": True, "seconds": 1}]
    report = module.summarize(rows, {"reviewed": {"expected_ask": False}})
    assert report["summary"]["correct"] == 1
    assert report["summary"]["missed"] == 0
    assert rows[0]["expected"] is True
