#!/usr/bin/env python3
"""Đánh giá grader chấm điểm phỏng vấn của nhóm (``assistant.aiworker``).

Harness ngoại tuyến: không tự gọi API ở chế độ ``--offline`` (chỉ kiểm tra
hình dạng bộ ca hỏi), và chỉ gọi grader khi chạy thật ở bước sau. Mỗi ca được
đo thời gian, và mọi lỗi của một ca riêng lẻ đều được thu lại thành một dòng
kết quả - không bao giờ làm sập cả lần chạy.

Báo cáo ghi ra ``data/private/eval/`` (đã gitignore). Báo cáo chỉ chứa mốc
thời gian, tên model và số liệu: không bao giờ chứa khoá API.

Cách chạy (từ gốc repo):
    python eval/interview_eval.py --offline
    python eval/interview_eval.py --limit 4 --fail-under 0.8
"""
from __future__ import annotations

import argparse
import inspect
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DEFAULT_CASES = REPO_ROOT / "eval" / "interview_cases.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "data" / "private" / "eval"
DEFAULT_TIMEOUT_S = 20.0
DEFAULT_FAIL_UNDER = 0.8

POSITIVE_LABEL = "Good"
NEGATIVE_LABEL = "Needs Improvement"

# Quy ước của bộ ca mẫu: 8 strong / 8 medium / 6 weak / 2 short.
BAND_EXPECTED = {"strong": 8, "medium": 8, "weak": 6, "short": 2}
BAND_SCORE_RANGE = {
    "strong": (7.5, 9.0),
    "medium": (5.5, 6.5),
    "weak": (2.5, 4.5),
    "short": (2.0, 3.5),
}
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d .\-]{7,}\d)(?!\d)")


# ==========================================================================
# Ngưỡng Good - lấy từ module đang được sửa, hoặc mặc định 6.0/10
# ==========================================================================
def load_threshold() -> tuple[float, str]:
    """Trả về ``(ngưỡng, nguồn)``. Nếu aiworker chưa có ``GOOD_THRESHOLD``
    thì dùng quy tắc tạm đã có của backend: 6.0 trên thang 10."""
    try:
        from assistant.aiworker import GOOD_THRESHOLD
    except ImportError:
        return 6.0, "mac dinh 6.0 (aiworker chua co GOOD_THRESHOLD)"
    return float(GOOD_THRESHOLD), "assistant.aiworker.GOOD_THRESHOLD"


def label_for(score: float, threshold: float) -> str:
    """Nhãn của backend: score >= ngưỡng thì Good, ngược lại Needs Improvement."""
    return POSITIVE_LABEL if score >= threshold else NEGATIVE_LABEL


# ==========================================================================
# Metrics - hàm thuần, không I/O, không import module repo
# ==========================================================================
def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _percentile_nearest_rank(values: list[float], pct: float) -> float:
    """Phân vị kiểu nearest-rank: rank = ceil(pct/100 * n), lấy giá trị thứ rank."""
    n = len(values)
    if n == 0:
        return 0.0
    rank = math.ceil((pct / 100.0) * n)
    rank = max(1, min(rank, n))
    return float(sorted(values)[rank - 1])


def compute_metrics(rows: list[dict[str, Any]],
                    threshold: float = 6.0) -> dict[str, Any]:
    """Tổng hợp kết quả chấm thử thành một dict số liệu thuần túy.

    Mỗi ``row`` là một dòng kết quả cho một ca:
        - chấm được: ``{"score", "ref_score", "pred_label", "ref_label",
          "used_fallback", "latency_s", ...}``
        - bị từ chối: ``{"refused": True, "code": "...", "latency_s", ...}``
        - lỗi:       ``{"error": "<TênLỗi>", "latency_s", ...}``

    Ca bị lỗi (``error``) bị loại khỏi mẫu số của điểm và nhãn. Tỉ lệ trả về
    dạng phân số 0-1. Với danh sách rỗng, mọi giá trị về 0.0/0.
    """
    rows = list(rows or [])
    scored: list[tuple[float, float, str | None, str | None]] = []
    latencies: list[float] = []
    refusals_total = 0
    refusals_by_code: dict[str, int] = {}
    errors = 0
    fallbacks = 0

    for row in rows:
        latency = row.get("latency_s")
        if _is_number(latency):
            latencies.append(float(latency))

        if row.get("refused"):
            refusals_total += 1
            code = row.get("code") or "unknown"
            refusals_by_code[code] = refusals_by_code.get(code, 0) + 1
            continue
        if row.get("error"):
            errors += 1
            continue

        if row.get("used_fallback"):
            fallbacks += 1

        score = row.get("score")
        ref = row.get("ref_score", row.get("ref"))
        if not _is_number(score) or not _is_number(ref):
            continue
        score = float(score)
        pred_label = row.get("pred_label")
        if pred_label is None:
            # Không có nhãn dự đoán sẵn thì suy ra từ điểm và ngưỡng Good.
            pred_label = label_for(score, threshold)
        scored.append((score, float(ref), pred_label, row.get("ref_label")))

    n = len(scored)
    mae = bias = 0.0
    within_1 = within_2 = 0.0
    if n:
        diffs = [score - ref for score, ref, _, _ in scored]
        mae = sum(abs(d) for d in diffs) / n
        bias = sum(diffs) / n
        within_1 = sum(1 for d in diffs if abs(d) <= 1.0) / n
        within_2 = sum(1 for d in diffs if abs(d) <= 2.0) / n

    labelled = [(pred, ref) for _, _, pred, ref in scored
                if isinstance(pred, str) and isinstance(ref, str)]
    total_labelled = len(labelled)
    correct = sum(1 for pred, ref in labelled if pred == ref)
    label_accuracy = (correct / total_labelled) if total_labelled else 0.0

    tp = fp = fn = tn = 0
    for pred, ref in labelled:
        if ref == POSITIVE_LABEL and pred == POSITIVE_LABEL:
            tp += 1
        elif ref != POSITIVE_LABEL and pred == POSITIVE_LABEL:
            fp += 1
        elif ref == POSITIVE_LABEL and pred != POSITIVE_LABEL:
            fn += 1
        else:
            tn += 1

    return {
        "n": n,
        "mae": mae,
        "bias": bias,
        "within_1_pct": within_1,
        "within_2_pct": within_2,
        "label_accuracy": label_accuracy,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "refusals_total": refusals_total,
        "refusals_by_code": refusals_by_code,
        "errors": errors,
        "fallbacks": fallbacks,
        "latency": {
            "mean": (sum(latencies) / len(latencies)) if latencies else 0.0,
            "p50": _percentile_nearest_rank(latencies, 50),
            "p95": _percentile_nearest_rank(latencies, 95),
        },
    }


# ==========================================================================
# Kiểm tra hình dạng bộ ca mẫu (dùng cho --offline)
# ==========================================================================
def validate_cases(cases: Any, threshold: float = 6.0) -> list[str]:
    """Trả về danh sách vấn đề; rỗng nghĩa là bộ ca hợp lệ."""
    problems: list[str] = []
    if not isinstance(cases, list):
        return [f"tap cases phai la mot JSON array, nhan {type(cases).__name__}"]

    if len(cases) != 24:
        problems.append(f"can dung 24 cases, nhan {len(cases)}")

    bands: dict[str, int] = {}
    seen_ids: set[str] = set()
    for index, case in enumerate(cases, 1):
        tag = f"case[{index}]"
        if not isinstance(case, dict):
            problems.append(f"{tag} khong phai object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            problems.append(f"{tag} thieu id")
        elif case_id in seen_ids:
            problems.append(f"{tag} id trung lap: {case_id}")
        else:
            seen_ids.add(case_id)

        band = case.get("band")
        if band not in BAND_EXPECTED:
            problems.append(f"{tag} band khong hop le: {band!r}")
        else:
            bands[band] = bands.get(band, 0) + 1

        for field in ("question", "answer"):
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{tag} thieu {field}")

        if isinstance(case.get("answer"), str):
            if EMAIL_RE.search(case["answer"]):
                problems.append(f"{tag} answer chua email")
            if PHONE_RE.search(case["answer"]):
                problems.append(f"{tag} answer chua so dien thoai")

        rubric = case.get("rubric")
        if not isinstance(rubric, dict):
            problems.append(f"{tag} thieu rubric")
        else:
            max_score = rubric.get("max_score")
            if isinstance(max_score, bool) or not isinstance(max_score, int):
                problems.append(f"{tag} max_score phai la so nguyen 10, nhan {max_score!r}")
            elif max_score != 10:
                problems.append(f"{tag} max_score phai bang 10, nhan {max_score!r}")
            criteria = rubric.get("criteria")
            if not isinstance(criteria, list) or len(criteria) != 3:
                problems.append(f"{tag} can dung 3 criteria, nhan "
                                f"{len(criteria) if isinstance(criteria, list) else criteria!r}")
            else:
                total = 0.0
                for c_index, criterion in enumerate(criteria, 1):
                    if not isinstance(criterion, dict):
                        problems.append(f"{tag} criterion[{c_index}] khong phai object")
                        continue
                    name = criterion.get("name")
                    if not isinstance(name, str) or not name.strip():
                        problems.append(f"{tag} criterion[{c_index}] thieu name")
                    points = criterion.get("points")
                    if not _is_number(points) or float(points) <= 0:
                        problems.append(f"{tag} criterion[{c_index}] points phai la so duong, "
                                        f"nhan {points!r}")
                    else:
                        total += float(points)
                    good = criterion.get("good")
                    if not isinstance(good, str) or not good.strip():
                        problems.append(f"{tag} criterion[{c_index}] thieu good")
                if abs(total - 10.0) > 1e-9:
                    problems.append(f"{tag} tong diem phai bang 10, nhan {total:g}")

        reference = case.get("reference")
        if not isinstance(reference, dict):
            problems.append(f"{tag} thieu reference")
        else:
            ref_score = reference.get("score")
            label = reference.get("label")
            if not _is_number(ref_score):
                problems.append(f"{tag} reference.score phai la so, nhan {ref_score!r}")
            else:
                score = float(ref_score)
                if label not in (POSITIVE_LABEL, NEGATIVE_LABEL):
                    problems.append(f"{tag} reference.label khong hop le: {label!r}")
                elif label != label_for(score, threshold):
                    problems.append(f"{tag} reference.label {label!r} khong khop quy tac "
                                    f"score {score:g} voi nguong {threshold:g}")
                if band in BAND_SCORE_RANGE:
                    low, high = BAND_SCORE_RANGE[band]
                    if not low <= score <= high:
                        problems.append(f"{tag} reference.score {score:g} ngoai khoang "
                                        f"{low:g}-{high:g} cua band {band}")
            if not isinstance(reference.get("note"), str) or not reference["note"].strip():
                problems.append(f"{tag} reference thieu note")

    for band, expected in BAND_EXPECTED.items():
        got = bands.get(band, 0)
        if got != expected:
            problems.append(f"band {band}: can {expected} cases, nhan {got}")
    for band in bands:
        if band not in BAND_EXPECTED:
            problems.append(f"band khong biet: {band!r}")
    return problems


# ==========================================================================
# Chạy chấm thử (chỉ khi không --offline)
# ==========================================================================
def _grader_module():
    """Import trễ: chế độ offline và unit test không bao giờ đụng tới module này."""
    from assistant import aiworker
    return aiworker


def grade_case(case: dict[str, Any], threshold: float,
               timeout_s: float = DEFAULT_TIMEOUT_S) -> dict[str, Any]:
    """Chấm một ca, đo thời gian, và không bao giờ ném lỗi ra ngoài."""
    reference = case.get("reference") if isinstance(case.get("reference"), dict) else {}
    row: dict[str, Any] = {
        "id": case.get("id"),
        "band": case.get("band"),
        "ref_score": reference.get("score"),
        "ref_label": reference.get("label"),
    }

    aiworker = _grader_module()
    grade_fn = getattr(aiworker, "grade_answer_with_evidence")
    EvidenceRejected = getattr(aiworker, "EvidenceRejected", ())

    kwargs: dict[str, Any] = {}
    try:
        params = inspect.signature(grade_fn).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtin/callable lạ
        params = {}
    if "timeout_s" in params:
        kwargs["timeout_s"] = timeout_s

    started = time.perf_counter()
    try:
        result = grade_fn(case["question"], case["answer"], case["rubric"], **kwargs)
    except EvidenceRejected as exc:
        row["latency_s"] = time.perf_counter() - started
        row["refused"] = True
        row["code"] = getattr(exc, "code", None) or "unknown"
        return row
    except Exception as exc:  # một ca hỏng không được kéo sập cả lần chạy
        row["latency_s"] = time.perf_counter() - started
        row["error"] = type(exc).__name__
        return row

    row["latency_s"] = time.perf_counter() - started
    score = result.get("score") if isinstance(result, dict) else None
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = None
    row["model"] = result.get("model") if isinstance(result, dict) else None
    row["used_fallback"] = bool(result.get("used_fallback")) if isinstance(result, dict) else False
    if score is None:
        row["error"] = "NoScore"
        return row
    row["score"] = score
    row["pred_label"] = label_for(score, threshold)
    return row


def run_eval(cases: list[dict[str, Any]], threshold: float,
             timeout_s: float = DEFAULT_TIMEOUT_S) -> list[dict[str, Any]]:
    return [grade_case(case, threshold, timeout_s) for case in cases]


# ==========================================================================
# In bảng và tổng hợp (tiếng Việt, gọn)
# ==========================================================================
def print_case_table(rows: list[dict[str, Any]]) -> None:
    print(f"{'id':<8} {'band':<7} {'ref':>5} {'pred':>5}  {'nhan ref->pred':<34} {'ms':>7}  trang thai")
    print("-" * 88)
    for row in rows:
        ref = row.get("ref_score")
        score = row.get("score")
        ref_text = f"{ref:g}" if _is_number(ref) else "-"
        score_text = f"{score:g}" if _is_number(score) else "-"
        labels = f"{row.get('ref_label') or '-'}->{row.get('pred_label') or '-'}"
        ms = row.get("latency_s")
        ms_text = f"{ms * 1000:7.0f}" if _is_number(ms) else "      -"
        if row.get("refused"):
            status = f"tu choi ({row.get('code')})"
        elif row.get("error"):
            status = f"loi ({row.get('error')})"
        else:
            status = "ok"
        print(f"{str(row.get('id')):<8} {str(row.get('band')):<7} {ref_text:>5} {score_text:>5}  "
              f"{labels:<34} {ms_text}  {status}")


def print_aggregate(metrics: dict[str, Any], threshold: float,
                    threshold_source: str, fail_under: float,
                    n_run: int, n_total: int) -> None:
    refusal = metrics["refusals_total"]
    errors = metrics["errors"]
    latency = metrics["latency"]
    print("")
    print("=== TONG HOP ===")
    print(f"Da cham {metrics['n']}/{n_run} ca (gom {n_total} ca trong file) | "
          f"tu choi: {refusal} | loi: {errors} | fallback: {metrics['fallbacks']}")
    print(f"Nguong Good: >= {threshold:.1f} ({threshold_source})")
    print(f"MAE: {metrics['mae']:.3f} | Bias: {metrics['bias']:+.3f}")
    print(f"Trong ±1 diem: {metrics['within_1_pct'] * 100:.1f}% | "
          f"trong ±2 diem: {metrics['within_2_pct'] * 100:.1f}%")
    confusion = metrics["confusion"]
    print(f"Nhan dung (label accuracy): {metrics['label_accuracy'] * 100:.1f}% "
          f"(nguong dat: {fail_under * 100:.1f}%)")
    print(f"Confusion: TP={confusion['tp']} FP={confusion['fp']} "
          f"FN={confusion['fn']} TN={confusion['tn']}")
    if metrics["refusals_by_code"]:
        codes = ", ".join(f"{code}={count}"
                          for code, count in sorted(metrics["refusals_by_code"].items()))
        print(f"Tu choi theo ma: {codes}")
    print(f"Do tre moi ca: mean {latency['mean'] * 1000:.0f}ms | "
          f"p50 {latency['p50'] * 1000:.0f}ms | p95 {latency['p95'] * 1000:.0f}ms")


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def default_report_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return DEFAULT_REPORT_DIR / f"interview_eval-{stamp}.json"


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _force_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def load_cases(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ==========================================================================
# CLI
# ==========================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="interview_eval",
        description="Đánh giá grader chấm điểm phỏng vấn trên bộ ca mẫu "
                    "(so với điểm tham chiếu do người cho).",
    )
    parser.add_argument("--cases", default=str(DEFAULT_CASES),
                        help="đường dẫn file cases (mặc định: eval/interview_cases.json)")
    parser.add_argument("--limit", type=int, default=None,
                        help="chỉ chấm N ca đầu tiên")
    parser.add_argument("--out", default=None,
                        help="đường dẫn báo cáo JSON "
                             "(mặc định: data/private/eval/interview_eval-<UTC>.json)")
    parser.add_argument("--fail-under", type=float, default=DEFAULT_FAIL_UNDER,
                        help="ngưỡng đạt của label accuracy (mặc định: 0.8)")
    parser.add_argument("--offline", action="store_true",
                        help="không gọi API; chỉ kiểm tra hình dạng file cases")
    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    args = build_parser().parse_args(argv)
    try:
        cases_path = _resolve(args.cases)
        cases = load_cases(cases_path)

        if args.offline:
            problems = validate_cases(cases)
            print(f"[offline] Kiem tra hinh dang {cases_path}")
            if problems:
                print(f"Shape validation: FAIL ({len(problems)} van de)")
                for problem in problems:
                    print(f"  - {problem}")
                return 2
            if not isinstance(cases, list):
                cases = []
            bands: dict[str, int] = {}
            for case in cases:
                bands[case.get("band")] = bands.get(case.get("band"), 0) + 1
            print("Shape validation: OK")
            print(f"- {len(cases)} cases; band: " + ", ".join(
                f"{band}={count}" for band, count in sorted(bands.items())))
            print("- Moi rubric: max_score la so nguyen 10, dung 3 criteria, tong diem = 10")
            print("- Moi case co question/answer/reference (score, label, note)")
            return 0

        if not isinstance(cases, list) or not cases:
            print("[setup] file cases khong co ca nao", file=sys.stderr)
            return 2
        if args.limit is not None and args.limit > 0:
            cases = cases[: args.limit]

        threshold, threshold_source = load_threshold()
        rows = run_eval(cases, threshold)
        metrics = compute_metrics(rows, threshold)

        print_case_table(rows)
        print_aggregate(metrics, threshold, threshold_source,
                        args.fail_under, len(rows), len(cases))

        models = sorted({row["model"] for row in rows if row.get("model")})
        report = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "cases_file": str(cases_path),
            "n_cases_in_file": len(cases),
            "n_cases_run": len(rows),
            "limit": args.limit,
            "threshold": {"value": threshold, "source": threshold_source},
            "fail_under": args.fail_under,
            "models": models,
            "metrics": metrics,
            "rows": rows,
            "secret_policy": "Bao cao nay khong chua khoa API hay gia tri cau hinh.",
        }
        report_path = _resolve(args.out) if args.out else default_report_path()
        write_report(report_path, report)
        print(f"\n[da ghi bao cao] {report_path}")

        return 0 if metrics["label_accuracy"] >= args.fail_under else 1
    except Exception as exc:  # crash khi dựng môi trường -> exit 2
        print(f"[setup] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())