"""Unit tests ngoại tuyến cho ``compute_metrics`` trong ``eval/interview_eval.py``.

Chỉ dùng dòng dữ liệu tổng hợp (synthetic rows): không gọi API, không cần khoa.
``conftest.py`` của tests/ đã chặn mạng và xoá khoa trong env nên các test này
chạy được ở mọi máy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _extra in (REPO_ROOT / "src", REPO_ROOT / "eval"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from interview_eval import (  # noqa: E402
    compute_metrics,
    label_for,
    main,
    validate_cases,
)

CASES_FILE = REPO_ROOT / "eval" / "interview_cases.json"


# --------------------------------------------------------------------------
# Helper dựng dòng dữ liệu tổng hợp
# --------------------------------------------------------------------------
def row(*, score=None, ref_score=None, pred_label=None, ref_label=None,
        refused=False, code=None, error=None, used_fallback=False,
        latency_s=1.0, **extra) -> dict:
    """Một dòng kết quả cho một ca, mặc định là ca chấm được bình thường."""
    data: dict = {
        "id": "case-xx",
        "band": "medium",
        "latency_s": latency_s,
        "ref_score": ref_score,
        "ref_label": ref_label,
        "pred_label": pred_label,
        "used_fallback": used_fallback,
    }
    if score is not None:
        data["score"] = score
    if refused:
        data["refused"] = True
        data["code"] = code or "unknown"
    if error:
        data["error"] = error
    data.update(extra)
    return data


# --------------------------------------------------------------------------
# 1. Thống nhất tuyệt đối
# --------------------------------------------------------------------------
def test_perfect_agreement_scores_and_labels():
    rows = [
        row(score=7.5, ref_score=7.5, ref_label="Good"),
        row(score=6.0, ref_score=6.0, ref_label="Good"),
        row(score=3.0, ref_score=3.0, ref_label="Needs Improvement"),
    ]
    metrics = compute_metrics(rows)

    assert metrics["n"] == 3
    assert metrics["mae"] == pytest.approx(0.0)
    assert metrics["bias"] == pytest.approx(0.0)
    assert metrics["within_1_pct"] == 1.0
    assert metrics["within_2_pct"] == 1.0
    assert metrics["label_accuracy"] == 1.0
    assert metrics["confusion"] == {"tp": 2, "fp": 0, "fn": 0, "tn": 1}


# --------------------------------------------------------------------------
# 2. Lệch +1 điểm có hệ thống
# --------------------------------------------------------------------------
def test_one_point_positive_bias():
    rows = [
        row(score=8.5, ref_score=7.5, ref_label="Good"),
        row(score=6.0, ref_score=5.0, ref_label="Needs Improvement"),
    ]
    metrics = compute_metrics(rows)

    assert metrics["n"] == 2
    assert metrics["mae"] == pytest.approx(1.0)
    assert metrics["bias"] == pytest.approx(1.0)
    assert metrics["within_1_pct"] == 1.0
    assert metrics["within_2_pct"] == 1.0
    # điểm sát 6.0 bị đẩy sang Good nên nhãn lệch ở ca thứ hai.
    assert metrics["confusion"] == {"tp": 1, "fp": 1, "fn": 0, "tn": 0}
    assert metrics["label_accuracy"] == pytest.approx(0.5)


def test_negative_bias_and_point_windows():
    rows = [
        row(score=5.0, ref_score=6.5, ref_label="Good"),    # lệch -1.5
        row(score=4.5, ref_score=6.5, ref_label="Good"),    # lệch -2.0
    ]
    metrics = compute_metrics(rows)

    assert metrics["mae"] == pytest.approx(1.75)
    assert metrics["bias"] == pytest.approx(-1.75)
    assert metrics["within_1_pct"] == pytest.approx(0.0)
    assert metrics["within_2_pct"] == 1.0


# --------------------------------------------------------------------------
# 3. Nhãn và ma trận nhầm lẫn
# --------------------------------------------------------------------------
def test_label_accuracy_and_confusion_matrix():
    rows = [
        row(score=7.0, ref_score=8.0, ref_label="Good"),
        row(score=5.0, ref_score=7.0, ref_label="Good"),
        row(score=7.0, ref_score=5.0, ref_label="Needs Improvement"),
        row(score=5.0, ref_score=5.0, ref_label="Needs Improvement"),
    ]
    metrics = compute_metrics(rows)

    assert metrics["label_accuracy"] == pytest.approx(0.5)  # tp + tn = 2/4
    assert metrics["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert metrics["n"] == 4


def test_pred_label_is_derived_from_threshold_when_missing():
    rows = [row(score=6.5, ref_score=6.5, ref_label="Good")]

    lenient = compute_metrics(rows, threshold=6.0)
    strict = compute_metrics(rows, threshold=7.0)

    assert lenient["label_accuracy"] == 1.0
    assert lenient["confusion"]["tp"] == 1
    # cùng một dòng dữ liệu, đổi ngưỡng thì nhãn dự đoán đổi theo.
    assert strict["label_accuracy"] == 0.0
    assert strict["confusion"] == {"tp": 0, "fp": 0, "fn": 1, "tn": 0}


def test_explicit_pred_label_wins_over_threshold():
    rows = [row(score=8.0, ref_score=8.0, ref_label="Good", pred_label="Needs Improvement")]
    metrics = compute_metrics(rows, threshold=6.0)
    assert metrics["confusion"] == {"tp": 0, "fp": 0, "fn": 1, "tn": 0}


def test_label_for_rule():
    assert label_for(6.0, 6.0) == "Good"
    assert label_for(9.9, 6.0) == "Good"
    assert label_for(5.9, 6.0) == "Needs Improvement"
    assert label_for(6.9, 7.0) == "Needs Improvement"


# --------------------------------------------------------------------------
# 4. Từ chối và lỗi
# --------------------------------------------------------------------------
def test_refusals_are_counted_by_code_and_leave_the_score_denominator():
    rows = [
        row(score=8.0, ref_score=8.0, ref_label="Good"),
        row(refused=True, code="evidence_not_found", latency_s=0.5),
        row(refused=True, code="feedback_ungrounded", latency_s=0.7),
        row(refused=True, code="evidence_not_found", latency_s=0.6),
    ]
    metrics = compute_metrics(rows)

    assert metrics["n"] == 1
    assert metrics["mae"] == pytest.approx(0.0)
    assert metrics["refusals_total"] == 3
    assert metrics["refusals_by_code"] == {
        "evidence_not_found": 2, "feedback_ungrounded": 1,
    }
    assert metrics["errors"] == 0
    assert metrics["label_accuracy"] == 1.0


def test_errors_are_counted_and_excluded_from_scores_and_labels():
    rows = [
        row(score=8.0, ref_score=8.0, ref_label="Good", latency_s=0.2),
        row(error="ValueError", latency_s=1.0),
        row(error="TimeoutError", latency_s=1.0),
    ]
    metrics = compute_metrics(rows)

    assert metrics["n"] == 1
    assert metrics["errors"] == 2
    assert metrics["label_accuracy"] == 1.0
    assert metrics["latency"]["mean"] == pytest.approx((0.2 + 1.0 + 1.0) / 3)


def test_missing_score_counts_as_absent_without_crashing():
    rows = [row(score=None, ref_score=8.0, ref_label="Good")]
    metrics = compute_metrics(rows)
    assert metrics["n"] == 0
    assert metrics["mae"] == pytest.approx(0.0)
    assert metrics["label_accuracy"] == 0.0


def test_fallbacks_are_counted():
    rows = [
        row(score=6.0, ref_score=6.0, ref_label="Good", used_fallback=True),
        row(score=5.0, ref_score=5.0, ref_label="Needs Improvement"),
    ]
    metrics = compute_metrics(rows)
    assert metrics["fallbacks"] == 1
    assert metrics["n"] == 2


# --------------------------------------------------------------------------
# 5. Danh sách rỗng
# --------------------------------------------------------------------------
def test_empty_rows_returns_zeroed_metrics():
    metrics = compute_metrics([])
    assert metrics["n"] == 0
    assert metrics["mae"] == pytest.approx(0.0)
    assert metrics["bias"] == pytest.approx(0.0)
    assert metrics["within_1_pct"] == pytest.approx(0.0)
    assert metrics["within_2_pct"] == pytest.approx(0.0)
    assert metrics["label_accuracy"] == pytest.approx(0.0)
    assert metrics["confusion"] == {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    assert metrics["refusals_total"] == 0
    assert metrics["refusals_by_code"] == {}
    assert metrics["errors"] == 0
    assert metrics["fallbacks"] == 0
    assert metrics["latency"] == {"mean": 0.0, "p50": 0.0, "p95": 0.0}


def test_empty_metrics_use_the_documented_key_set():
    expected = {"n", "mae", "bias", "within_1_pct", "within_2_pct", "label_accuracy",
                "confusion", "refusals_total", "refusals_by_code", "errors",
                "fallbacks", "latency"}
    assert set(compute_metrics([])) == expected
    assert set(compute_metrics([])["latency"]) == {"mean", "p50", "p95"}


# --------------------------------------------------------------------------
# 6. Thống kê độ trễ (phân vị nearest-rank)
# --------------------------------------------------------------------------
def test_latency_mean_and_nearest_rank_percentiles():
    rows = [row(latency_s=value) for value in (1.0, 2.0, 3.0, 4.0)]
    metrics = compute_metrics(rows)

    assert metrics["latency"]["mean"] == pytest.approx(2.5)
    assert metrics["latency"]["p50"] == pytest.approx(2.0)   # ceil(0.50*4) = 2
    assert metrics["latency"]["p95"] == pytest.approx(4.0)   # ceil(0.95*4) = 4


def test_latency_percentiles_of_a_single_sample():
    metrics = compute_metrics([row(latency_s=7.0)])
    assert metrics["latency"] == {"mean": 7.0, "p50": 7.0, "p95": 7.0}


def test_latency_percentiles_of_two_samples():
    metrics = compute_metrics([row(latency_s=1.0), row(latency_s=5.0)])
    assert metrics["latency"]["p50"] == pytest.approx(1.0)   # ceil(1.0) = 1
    assert metrics["latency"]["p95"] == pytest.approx(5.0)   # ceil(1.9) = 2


def test_latency_ignores_rows_without_a_latency():
    rows = [row(latency_s=None), row(latency_s=2.0)]
    metrics = compute_metrics(rows)
    assert metrics["latency"] == {"mean": 2.0, "p50": 2.0, "p95": 2.0}


# --------------------------------------------------------------------------
# 7. Bộ ca mẫu thật và CLI offline
# --------------------------------------------------------------------------
def test_shipped_fixture_passes_shape_validation():
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    assert len(cases) == 24
    assert validate_cases(cases) == []


def test_validate_cases_rejects_a_rubric_whose_points_do_not_sum_to_ten():
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    cases[0]["rubric"]["criteria"][0]["points"] = 2  # 2 + 4 + 3 = 9

    problems = validate_cases(cases)
    assert any("tong diem" in problem for problem in problems)


def test_validate_cases_rejects_a_label_that_breaks_the_six_rule():
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    strong = next(case for case in cases if case["band"] == "strong")
    strong["reference"]["label"] = "Needs Improvement"

    problems = validate_cases(cases)
    assert any("khong khop quy tac" in problem for problem in problems)


def test_offline_cli_returns_zero(capsys):
    assert main(["--offline"]) == 0
    out = capsys.readouterr().out
    assert "Shape validation: OK" in out


def test_offline_cli_is_explicit_about_the_cases_file(capsys):
    assert main(["--offline", "--cases", str(CASES_FILE)]) == 0
    out = capsys.readouterr().out
    assert "interview_cases.json" in out
    assert "strong=8" in out and "medium=8" in out and "weak=6" in out and "short=2" in out