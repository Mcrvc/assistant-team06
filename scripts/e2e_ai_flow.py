"""End-to-end probe of the interview flow against a running local server.

Exercises the real AI provider (INTERVIEW_AI_PROVIDER=nvidia): question
generation, answer submission with background grading, progress polling and
finalize/report. Prints a JSON transcript of every step.

Usage: python scripts/e2e_ai_flow.py <base_url> <access_token>
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

JOB = {
    "title": "Backend Engineering Intern",
    "company": "Yourin",
    "domain": "Fintech",
    "level": "Intern",
    "description": (
        "We are hiring a backend engineering intern to work on our payment "
        "services. You will build REST APIs with Python and FastAPI, work with "
        "PostgreSQL through Supabase, write tests with pytest, and help debug "
        "production incidents. You will learn about idempotency keys, rate "
        "limiting and reliable background jobs. Mentor support is provided."
    ),
}
CV = (
    "Intern profile: 2 years of Python, built a FastAPI service with PostgreSQL, "
    "wrote pytest suites, debugged a duplicate-charge incident found by a "
    "reconciliation job, added idempotency keys and cut double charges to zero."
)

ANSWERS = [
    (
        "Trong dự án API thanh toán bằng FastAPI, tôi gặp sự cố trừ tiền hai "
        "lần cho một giao dịch khi client retry sau timeout. Tôi đã tái hiện "
        "lỗi bằng test pytest với TestClient, đọc log Supabase để tìm nguyên "
        "nhân, và phát hiện endpoint không kiểm tra idempotency key. Tôi đã "
        "thêm bảng lưu key kèm phản hồi trong PostgreSQL với ràng buộc unique, "
        "sau đó viết test hồi quy. Sau hai tuần, số giao dịch bị trừ hai lần "
        "giảm về 0."
    ),
    (
        "Tôi sẽ thiết kế endpoint nhận idempotency key từ client, kiểm tra key "
        "trong bảng PostgreSQL riêng trước khi xử lý. Nếu key đã tồn tại, tôi "
        "trả về phản hồi đã lưu thay vì trừ tiền lần nữa. Tôi dùng ràng buộc "
        "unique trên cột key để hai request đồng thời không cùng tạo bản ghi. "
        "Về test, tôi viết pytest với TestClient: gửi cùng một key hai lần và "
        "khẳng định lần thứ hai trả về kết quả cache mà số dư chỉ bị trừ một lần."
    ),
    (
        "Trong dự án đồng bộ dữ liệu, tôi xây dựng worker chạy nền gửi biến "
        "động số dư cho ngân hàng đối tác. Khi gọi API đối tác thất bại, tôi "
        "dùng cơ chế retry với exponential backoff: lần đầu chờ 1 giây, sau đó "
        "2 giây, 4 giây và tối đa 5 lần. Tôi lưu trạng thái job trong "
        "PostgreSQL để sau khi process chết có thể tiếp tục từ job chưa hoàn "
        "thành. Nhờ vậy tỷ lệ đồng bộ thành công tăng từ 90 phần trăm lên 99.5 "
        "phần trăm."
    ),
    (
        "Tôi quan tâm đến vị trí này vì tôi đã xây dựng API thanh toán bằng "
        "FastAPI và PostgreSQL trong dự án cá nhân, và muốn học thêm về hệ "
        "thống fintech an toàn. Tôi từng phát hiện và sửa lỗi trừ tiền hai lần "
        "khi client retry sau timeout, sau đó thêm idempotency key để ngăn "
        "lặp lại. Tôi muốn đóng góp cho đội ngũ của các bạn."
    ),
    (
        "Khi gặp nhiệm vụ chưa quen, tôi đọc tài liệu trước, làm bản nhỏ nhất "
        "chạy được, rồi kiểm tra kết quả bằng test. Ví dụ lần đầu làm rate "
        "limiter, tôi không rõ token bucket nên đã đọc tài liệu và viết bản "
        "thử với dictionary trong bộ nhớ. Tôi kiểm tra bằng pytest với 1000 "
        "request đồng thời để chắc chắn không chặn nhầm người dùng thật."
    ),
    (
        "Tôi làm việc nhóm bằng cách chia nhỏ công việc và cập nhật tiến độ "
        "hàng ngày trên nhóm chat của dự án. Khi đồng nghiệp gặp lỗi ở module "
        "thanh toán, tôi đã ngồi cùng debug và viết test tái hiện lỗi trước "
        "khi sửa. Chúng tôi đã giảm thời gian xử lý sự cố từ một ngày xuống "
        "hai giờ nhờ quy trình này."
    ),
]


def answer_for(index: int) -> str:
    """Reuse the strongest answers round-robin; every interview gets one."""
    return ANSWERS[index % len(ANSWERS)]


def call(method: str, url: str, token: str, body: dict | None = None, timeout: float = 300.0):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode())


def main() -> int:
    # Windows consoles default to cp1252; feedback is Vietnamese.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    base, token = sys.argv[1].rstrip("/"), sys.argv[2]
    transcript: list[dict] = []
    name = f"AI wire e2e {int(time.time()) % 100000}"

    print("== 1. create interview (AI generates questions) ==")
    started = time.monotonic()
    status, created = call("POST", f"{base}/api/interviews", token,
                           {"job_profile": JOB, "cv": CV, "name": name})
    elapsed = time.monotonic() - started
    print(f"HTTP {status} in {elapsed:.1f}s")
    print("question_generation:", created.get("question_generation"))
    print("first question:", json.dumps(created.get("question"), ensure_ascii=False)[:400])
    transcript.append({"step": "create", "status": status, "seconds": round(elapsed, 1),
                       "body": created})
    interview_id, revision = created["id"], created["revision"]

    print("\n== 2. resume interview (full question list) ==")
    status, view = call("GET", f"{base}/api/interviews/{interview_id}", token)
    print(f"HTTP {status}")
    for index, question in enumerate(view.get("questions", [])):
        print(f"  Q{index}: {question.get('text')}")
        print(f"        criteria: {question.get('criteria')}")
    revision = view.get("revision", revision)
    transcript.append({"step": "get", "status": status, "questions": view.get("questions")})

    print("\n== 3. submit answers (background grading) ==")
    total = len(view.get("questions", []))
    print(f"interview has {total} questions")
    for index in range(total):
        status, submitted = call("POST",
                                 f"{base}/api/interviews/{interview_id}/answers/{index}",
                                 token, {"revision": revision, "text": answer_for(index)})
        print(f"answer {index}: HTTP {status} grading_status={submitted['answers'][index]['grading_status']}")
        revision = submitted["revision"]
        transcript.append({"step": f"submit-{index}", "status": status,
                           "grading_status": submitted["answers"][index]["grading_status"]})

    print("\n== 4. poll progress until grading finishes ==")
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        status, progress = call("GET", f"{base}/api/interviews/{interview_id}/progress", token,
                                timeout=30)
        print("progress:", progress)
        if progress["pending"] == 0 and progress["answered"] == progress["total"]:
            break
        time.sleep(4)
    else:
        print("TIMEOUT waiting for grading")
    transcript.append({"step": "progress", "status": status, "progress": progress})

    print("\n== 5. finalize ==")
    status, finalized = call("POST", f"{base}/api/interviews/{interview_id}/finalize", token,
                             {"revision": revision, "name": name})
    print(f"HTTP {status}")
    report = finalized.get("report") or {}
    print("overall_score:", report.get("overall_score"), "label:", report.get("label"),
          "used_fallback:", report.get("used_fallback"))
    for item in report.get("items", []):
        print(f"  Q{item['question_index']}: score={item.get('score')} label={item.get('label')} "
              f"model={item.get('model')}")
        print(f"     feedback: {item.get('feedback')}")
        print(f"     evidence: {item.get('evidence')}")
    print("notice:", report.get("notice"))
    transcript.append({"step": "finalize", "status": status, "report": report})

    with open("data/private/e2e_ai_flow.json", "w", encoding="utf-8") as handle:
        json.dump(transcript, handle, ensure_ascii=False, indent=2)
    print("\ntranscript -> data/private/e2e_ai_flow.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())