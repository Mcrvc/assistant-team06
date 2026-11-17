"""Live probe: one real NVIDIA grading call against a Vietnamese answer.

Verifies the English-prose rule: feedback prose in English, evidence/quote
spans verbatim (Vietnamese stays Vietnamese).
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from assistant import aiworker

RUBRIC = {"max_score": 10, "criteria": [
    {"name": "incident diagnosis", "points": 4,
     "good": "Concrete steps: reproduce, read logs, find root cause"},
    {"name": "fix and verification", "points": 3,
     "good": "Names the change and how it was verified"},
    {"name": "prevention", "points": 3,
     "good": "What stops the incident from happening again"},
]}
QUESTION = "You debugged a duplicate-charge incident. Walk me through it."
ANSWER = ("Trong dự án API thanh toán bằng FastAPI, tôi gặp sự cố trừ tiền hai lần "
          "cho một giao dịch khi client retry sau timeout. Tôi đã tái hiện lỗi bằng "
          "test pytest với TestClient, đọc log Supabase để tìm nguyên nhân, và phát "
          "hiện endpoint không kiểm tra idempotency key. Tôi đã thêm bảng lưu key "
          "trong PostgreSQL với ràng buộc unique, sau đó viết test hồi quy.")

grade = aiworker.grade_answer_with_evidence(QUESTION, ANSWER, RUBRIC, timeout_s=60)
print("score:", grade["score"], "| model:", grade["model"], "| used_fallback:", grade["used_fallback"])
print("\nfeedback:\n", grade["feedback"])
print("\nevidence:")
for quote in grade["evidence"]:
    print(f"  verbatim={quote in ANSWER!s:5} | {quote}")
prose = grade["feedback"]
print("\nchecks:")
print("  feedback ascii (English prose):", prose.isascii())
print("  all evidence verbatim:", all(q in ANSWER for q in grade["evidence"]))