"""
Precision/recall report for E5's detection backends (README.md: "E5 |
Detection — injection classifier (precision/recall tracked)").

Unlike the other scripts in this directory, this one needs no DATABASE_URL
and no Docker — detection is pure Python, evaluated against the bundled
labeled dataset in core/detection/dataset.py.

Usage:
    python scripts/eval_detection.py
    python scripts/eval_detection.py --thresholds 0.3 0.5 0.7 0.9
    python scripts/eval_detection.py --seed 7 --test-ratio 0.4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.detection import InjectionClassifier, evaluate_at_thresholds, split_examples
from core.detection.scanner import combine_detection_scores
from core.write_governor import scan_for_injection


def _print_table(name: str, rows) -> None:
    print(f"\n=== {name} ===")
    header = f"{'threshold':>9}  {'precision':>9}  {'recall':>7}  {'f1':>6}  {'tp':>3} {'fp':>3} {'fn':>3} {'tn':>3}"
    print(header)
    print("-" * len(header))
    for m in rows:
        print(
            f"{m.threshold:>9.2f}  {m.precision:>9.3f}  {m.recall:>7.3f}  {m.f1:>6.3f}  "
            f"{m.true_positives:>3} {m.false_positives:>3} {m.false_negatives:>3} {m.true_negatives:>3}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thresholds", type=float, nargs="+", default=[0.3, 0.5, 0.7, 0.9])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-ratio", type=float, default=0.3)
    args = parser.parse_args()

    train, test = split_examples(test_ratio=args.test_ratio, seed=args.seed)
    print(f"Train: {len(train)} examples, Test (held-out): {len(test)} examples")

    clf = InjectionClassifier()
    clf.train(train)

    heuristic_scorer = lambda text: scan_for_injection(text)[0]  # noqa: E731
    classifier_scorer = clf.predict_proba
    ensemble_scorer = lambda text: combine_detection_scores(  # noqa: E731
        scan_for_injection(text),
        (clf.predict_proba(text), []),
    )[0]

    _print_table(
        "E2 heuristic scanner", evaluate_at_thresholds(heuristic_scorer, test, args.thresholds)
    )
    _print_table(
        "E5 trained classifier", evaluate_at_thresholds(classifier_scorer, test, args.thresholds)
    )
    _print_table(
        "E5 ensemble (heuristic + classifier)",
        evaluate_at_thresholds(ensemble_scorer, test, args.thresholds),
    )

    print(
        "\nNote: this is a small, illustrative held-out set (the bundled "
        "dataset in core/detection/dataset.py), not a production benchmark. "
        "Train/evaluate on your own labeled traffic before relying on these "
        "numbers for a real deployment."
    )


if __name__ == "__main__":
    main()
