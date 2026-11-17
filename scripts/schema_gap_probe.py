"""Which REAL-shaped writer payloads does the team schema refuse?

Feeds realistic model output (the shapes aiworker accepts) into the
``Generation`` contract ``SafeInterviewAI`` validates with, and reports the
exact refusal for each. Run: python scripts/schema_gap_probe.py
"""
from __future__ import annotations

import sys

from assistant.interview_schemas import Generation


def rubric(criteria):
    return {"max_score": 10.0, "criteria": criteria}


def criterion(name="depth", points=5.0, good="Walks through the design with detail.",
              **extra):
    item = {"name": name, "points": points, "good": good}
    item.update(extra)
    return item


def question(text="Tell me about your payment service.", **overrides):
    item = {
        "text": text,
        "source_type": "open",
        "reference": None,
        "criteria": ["Explains the design clearly with a concrete example."],
        "rubric": rubric([criterion(), criterion(name="clarity")]),
    }
    item.update(overrides)
    return item


def payload(**overrides):
    base = {"questions": [question()], "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
            "used_fallback": False}
    base.update(overrides)
    return base


CASES = [
    ("clean baseline", payload()),
    ("criterion name longer than 200 chars", payload(questions=[question(
        rubric=rubric([criterion(name="D" * 201), criterion(name="clarity")]))])),
    ("criterion name blank", payload(questions=[question(
        rubric=rubric([criterion(name="   "), criterion(name="clarity")]))])),
    ("extra key inside a criterion", payload(questions=[question(
        rubric=rubric([criterion(why="because"), criterion(name="clarity")]))])),
    ("extra key inside the rubric", payload(questions=[question(
        rubric={**rubric([criterion(points=10.0)]), "note": "keep it fair"})])),
    ("points given as int", payload(questions=[question(
        rubric=rubric([criterion(points=5), criterion(name="clarity", points=5)]))])),
    ("max_score given as int 10", payload(questions=[question(
        rubric={**rubric([criterion(), criterion(name="clarity")]),
                "max_score": 10})])),
    ("7 criteria", payload(questions=[question(
        rubric=rubric([criterion(name=f"c{index}", points=10 / 7)
                       for index in range(7)]))])),
    ("criteria list of 7 strings", payload(questions=[question(
        criteria=[f"criterion {index}" for index in range(7)])])),
    ("one long criterion text (1001 chars)", payload(questions=[question(
        criteria=["x" * 1001])])),
    ("question text of 4001 chars", payload(questions=[question(text="q" * 4001)])),
    ("five good questions, one refused", payload(questions=[
        question(f"Question {index} about your payment work.") for index in range(4)
    ] + [question(rubric=rubric([criterion(name="N" * 300, points=10.0)]))])),
]


def main() -> int:
    for label, body in CASES:
        try:
            Generation.model_validate(body)
            print(f"  accepted : {label}")
        except Exception as exc:  # noqa: BLE001
            head = str(exc).splitlines()[1] if len(str(exc).splitlines()) > 1 else str(exc)
            print(f"  REFUSED  : {label}\n             {head.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())