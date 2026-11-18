"""Print generation + questions for the newest interview (finalized or not)."""
import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
conn = sqlite3.connect("data/private/interviews.sqlite")
rows = list(conn.execute("select payload from local_interviews order by rowid desc"))
conn.close()
(payload,) = rows[0]
record = json.loads(payload)
print("id:", record["id"][:8], "| name:", record.get("name"), "| status:", record.get("status"))
print("question_generation:", record.get("question_generation"))
print("questions:", len(record.get("questions", [])))
for i, q in enumerate(record.get("questions", [])):
    print(f"\nQ{i}: {q.get('text')}")
    print(f"    has_rubric: {bool(q.get('rubric'))}")
print("\nanswers:", [(a.get("grading_status"), a.get("error_code")) for a in record.get("answers", [])])