"""
Precision/recall tracking for the E5 classifier (README.md: "a real classifier
that tracks precision/recall").

E2's heuristic scanner had no notion of measured accuracy — patterns were
either added or they weren't, with no held-out set to check them against.
This module is what actually computes precision/recall/F1 for any scorer
(the classifier, the heuristic, or the combined E5 scorer) against a set of
`LabeledExample`s, so a change to the model or the dataset has a number
attached to it instead of just a vibe.

`scripts/eval_detection.py` is the CLI entry point that prints this as a
report; this module is the reusable computation underneath it.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from core.detection.dataset import LabeledExample

# A scorer takes raw text and returns a score in [0, 1]. Both
# `InjectionClassifier.predict_proba` and `core.write_governor.scan_for_injection`
# (once you drop its label list) satisfy a compatible shape — see
# `core/detection/scanner.py` for the adapters used at evaluation time.
Scorer = Callable[[str], float]


class DetectionMetrics(BaseModel):
    """Confusion-matrix counts plus derived precision/recall/F1 at one threshold."""

    threshold: float
    n_examples: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1: float

    @property
    def accuracy(self) -> float:
        total = (
            self.true_positives
            + self.false_positives
            + self.false_negatives
            + (self.true_negatives)
        )
        correct = self.true_positives + self.true_negatives
        return correct / total if total else 0.0


def evaluate(
    scorer: Scorer,
    examples: list[LabeledExample],
    threshold: float = 0.7,
) -> DetectionMetrics:
    """
    Score every example with `scorer`, flag it as positive when the score
    is >= `threshold`, and compute precision/recall/F1 against the true
    labels. Precision/recall are 0.0 (not NaN) when their denominator is 0,
    so a degenerate eval set never raises.
    """
    tp = fp = fn = tn = 0
    for ex in examples:
        score = scorer(ex.text)
        predicted_positive = score >= threshold
        actual_positive = ex.label == 1

        if predicted_positive and actual_positive:
            tp += 1
        elif predicted_positive and not actual_positive:
            fp += 1
        elif not predicted_positive and actual_positive:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return DetectionMetrics(
        threshold=threshold,
        n_examples=len(examples),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )


def evaluate_at_thresholds(
    scorer: Scorer,
    examples: list[LabeledExample],
    thresholds: list[float] | None = None,
) -> list[DetectionMetrics]:
    """Sweep `evaluate()` across several thresholds — useful for picking one."""
    thresholds = thresholds if thresholds is not None else [0.3, 0.5, 0.7, 0.9]
    return [evaluate(scorer, examples, threshold=t) for t in thresholds]
