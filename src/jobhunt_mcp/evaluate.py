"""Evaluate the reply classifier against a labelled set of recruiter emails.

    jobhunt-eval                       # uses evals/classify_cases.jsonl
    jobhunt-eval --cases my_cases.jsonl --min-accuracy 0.9

Each case is one JSON line: {"id", "subject", "body", "expected"} where expected is
offer, rejected, interview, assessment or other. The report shows overall accuracy,
precision and recall per label, and every miss, so a rule change can be checked
before and after.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .classify import classify

LABELS = ("offer", "rejected", "interview", "assessment", "other")
DEFAULT_CASES = Path(__file__).resolve().parents[2] / "evals" / "classify_cases.jsonl"


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for c in cases:
        got = classify(c["subject"], c["body"])
        results.append({**c, "got": got, "ok": got == c["expected"]})
    per_label = {}
    for label in LABELS:
        tp = sum(1 for r in results if r["got"] == label and r["expected"] == label)
        predicted = sum(1 for r in results if r["got"] == label)
        actual = sum(1 for r in results if r["expected"] == label)
        per_label[label] = {
            "precision": tp / predicted if predicted else None,
            "recall": tp / actual if actual else None,
            "n": actual,
        }
    correct = sum(r["ok"] for r in results)
    return {"total": len(results), "correct": correct,
            "accuracy": correct / len(results) if results else 0.0,
            "per_label": per_label, "misses": [r for r in results if not r["ok"]]}


def _fmt(x: float | None) -> str:
    return "  -  " if x is None else f"{x:5.0%}"


def report(res: dict[str, Any]) -> str:
    lines = [f"Accuracy: {res['correct']}/{res['total']} = {res['accuracy']:.0%}", "",
             f"{'label':<12}{'cases':>6}{'precision':>11}{'recall':>8}"]
    for label, m in res["per_label"].items():
        lines.append(f"{label:<12}{m['n']:>6}{_fmt(m['precision']):>11}{_fmt(m['recall']):>8}")
    if res["misses"]:
        lines += ["", "Misses:"]
        for r in res["misses"]:
            lines.append(f"  {r['id']:<28} expected {r['expected']:<11} got {r['got']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the recruiter-email classifier")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--min-accuracy", type=float, default=None,
                        help="exit with code 1 if accuracy is below this (e.g. 0.9), for CI")
    args = parser.parse_args()
    res = run(load_cases(args.cases))
    print(report(res))
    if args.min_accuracy is not None and res["accuracy"] < args.min_accuracy:
        sys.exit(1)


if __name__ == "__main__":
    main()
