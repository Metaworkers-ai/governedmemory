"""
E5 detection entry point — `score_injection()` is the drop-in replacement
for `core.write_governor.scan_for_injection` that `MemoryStore.write()`
calls.

Three backends, selected by the `DETECTION_BACKEND` env var (read at call
time, not import time, so it can be changed per-call/per-test without a
module reload):

  heuristic   (default) — pure passthrough to E2's regex scanner. Byte-
              identical behavior to before E5 existed. This is the default
              specifically so installing E5 doesn't change anything for
              existing deployments until they opt in — the same "no-op
              until configured" pattern E4 used for purpose bindings.
  classifier  — score comes only from the trained InjectionClassifier
              (core/detection/classifier.py). Labels are ["ml_classifier"]
              when flagged, [] otherwise — the classifier doesn't have
              per-pattern explainability the way the regex scanner does.
  ensemble    — combines both via the same noisy-OR the heuristic scanner
              uses internally to combine its own patterns, so a text that
              either scanner would catch alone gets caught, and a text
              both agree on scores higher than either alone. Labels are the
              union of both backends' labels. This is the recommended
              setting for production use: heuristic patterns stay
              explainable, the classifier adds recall the patterns
              didn't anticipate.

`INJECTION_THRESHOLD` (already used by `MemoryStore.write()` to decide
whether a score taints a record) applies uniformly regardless of backend —
E5 changes how the score is computed, not how it's consumed.
"""

from __future__ import annotations

import os
from pathlib import Path

from core.detection.classifier import InjectionClassifier, get_default_classifier
from core.write_governor.injection_scanner import scan_for_injection as _heuristic_scan

_VALID_BACKENDS = {"heuristic", "classifier", "ensemble"}
_ML_LABEL = "ml_classifier"


def _get_classifier() -> InjectionClassifier:
    model_path = os.getenv("DETECTION_MODEL_PATH")
    if model_path and Path(model_path).exists():
        return InjectionClassifier.load(model_path)
    return get_default_classifier()


def _classifier_score(content: str) -> tuple[float, list[str]]:
    if not content:
        return 0.0, []
    score = round(_get_classifier().predict_proba(content), 3)
    threshold = float(os.getenv("INJECTION_THRESHOLD", "0.7"))
    labels = [_ML_LABEL] if score >= threshold else []
    return score, labels


def _ensemble_score(content: str) -> tuple[float, list[str]]:
    heuristic_score, heuristic_labels = _heuristic_scan(content)
    ml_score, ml_labels = _classifier_score(content)

    combined = round(1.0 - (1.0 - heuristic_score) * (1.0 - ml_score), 3)
    labels = sorted(set(heuristic_labels) | set(ml_labels))
    return combined, labels


def score_injection(content: str, backend: str | None = None) -> tuple[float, list[str]]:
    """
    Score `content` for likely prompt-injection / social-engineering intent.

    Returns (score in [0, 1], sorted list of matched labels) — same shape as
    `core.write_governor.scan_for_injection`, so this is a drop-in
    replacement wherever that was called.

    `backend` overrides `DETECTION_BACKEND` for this call only; when None
    (the normal case), the env var is read fresh on every call, defaulting
    to "heuristic".
    """
    backend = backend if backend is not None else os.getenv("DETECTION_BACKEND", "heuristic")
    if backend not in _VALID_BACKENDS:
        raise ValueError(
            f"unknown DETECTION_BACKEND={backend!r}, expected one of {sorted(_VALID_BACKENDS)}"
        )

    if backend == "heuristic":
        return _heuristic_scan(content)
    if backend == "classifier":
        return _classifier_score(content)
    return _ensemble_score(content)
