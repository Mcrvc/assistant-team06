import csv
import sys
from pathlib import Path


def run_assistant(query: str) -> str:
 
    return query


def evaluate(cases_path: Path) -> float:
    if not cases_path.exists():
        print(f"Error: {cases_path} does not exist.")
        sys.exit(1)

    total = 0
    correct = 0

    with open(cases_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            query = row["query"].strip()
            expected = row["expected"].strip()

            actual = str(run_assistant(query)).strip()

            if actual.lower() == expected.lower():
                correct += 1

    if total == 0:
        print("Accuracy: 0.00%")
        return 0.0

    accuracy = (correct / total) * 100
    print(f"Accuracy: {accuracy:.2f}%")
    return accuracy


if __name__ == "__main__":
    cases_file = Path(__file__).resolve().parent / "cases.csv"
    evaluate(cases_file)