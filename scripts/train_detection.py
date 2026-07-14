"""
Train an E5 InjectionClassifier and save it to disk as a JSON artifact.

Not required for normal use — `get_default_classifier()` trains in-process
from the bundled dataset automatically, with zero setup. This script exists
for two cases: (1) you've extended core/detection/dataset.py (or built your
own labeled dataset) and want a reproducible saved artifact instead of
retraining on every process start, or (2) you want to point
DETECTION_MODEL_PATH at a specific trained model rather than always using
the bundled default.

Usage:
    python scripts/train_detection.py
    python scripts/train_detection.py --out core/detection/artifacts/injection_classifier.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.detection import InjectionClassifier, evaluate, load_examples
from core.detection.classifier import DEFAULT_ARTIFACT_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_ARTIFACT_PATH)
    args = parser.parse_args()

    examples = load_examples()
    print(f"Training on {len(examples)} bundled examples...")

    clf = InjectionClassifier()
    clf.train(examples)

    # Report in-sample metrics as a sanity check — this is NOT a held-out
    # eval; use scripts/eval_detection.py for a proper train/test split.
    metrics = evaluate(clf.predict_proba, examples, threshold=0.7)
    print(
        f"In-sample @ threshold=0.7 — precision={metrics.precision:.3f} "
        f"recall={metrics.recall:.3f} f1={metrics.f1:.3f}"
    )

    clf.save(args.out)
    print(f"Saved to {args.out}")
    print(f"\nTo use it: export DETECTION_MODEL_PATH={args.out}")
    print("           export DETECTION_BACKEND=classifier   # or: ensemble")


if __name__ == "__main__":
    main()
