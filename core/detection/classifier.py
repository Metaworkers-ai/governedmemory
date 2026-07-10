"""
InjectionClassifier — a trained classifier for the E5 detection pipeline.

E2's scanner is a fixed set of regexes: fast and explainable, but its recall
is bounded by whatever patterns someone thought to write, and there was never
a principled way to measure precision/recall against it (`README.md` calls
this out explicitly: "E5 replaces it with a real classifier that tracks
precision/recall"). This module is that classifier.

Implementation choice: multinomial Naive Bayes over a bag-of-words, trained
with Laplace smoothing, implemented in pure Python (stdlib only — `math` +
`collections.Counter`). No numpy/scikit-learn/torch dependency. This is a
deliberate trade-off, consistent with `EmbeddingProvider`'s
`NullEmbeddingProvider` and the project's general OSS-accessibility stance
(CONTRIBUTING.md's "Why sync psycopg2" section): a classifier that trains in
milliseconds on stdlib alone, with zero install friction, beats a more
powerful model that requires a heavy dependency just to try out E5. Anyone
who wants a stronger model can swap in their own — see `train()` below, which
accepts any list of `LabeledExample`s, not just the bundled dataset.

The model is a plain dict of floats, so it round-trips through JSON exactly
(`to_dict()` / `from_dict()`) — same "human-diffable, no opaque binary blob"
philosophy CONTRIBUTING.md applies to the schema (`_SCHEMA_SQL`, no ORM).
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from core.detection.dataset import LabeledExample, load_examples

_TOKEN_RE = re.compile(r"[a-z0-9']+")
_LAPLACE_ALPHA = 1.0

DEFAULT_ARTIFACT_PATH = Path(__file__).parent / "artifacts" / "injection_classifier.json"


def tokenize(text: str) -> list[str]:
    """Lowercase, alphanumeric-token split. Same tokenization at train and score time."""
    return _TOKEN_RE.findall(text.lower())


class InjectionClassifier:
    """
    Multinomial Naive Bayes over a bag-of-words.

    Not fit until `train()` (or `from_dict()`/`load()`) is called —
    `predict_proba()` raises before that, so a caller can't silently get
    meaningless scores from an empty model.
    """

    def __init__(self) -> None:
        self._fitted = False
        self._class_log_prior: dict[int, float] = {}
        self._token_log_likelihood: dict[int, dict[str, float]] = {}
        self._vocab: set[str] = set()
        self._n_train_examples = 0

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def train(self, examples: list[LabeledExample]) -> None:
        """
        Fit on `examples`. Any prior fit is discarded — this is not
        incremental/online training.
        """
        if not examples:
            raise ValueError("cannot train InjectionClassifier on an empty example list")

        class_counts: dict[int, int] = Counter(ex.label for ex in examples)
        token_counts: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
        vocab: set[str] = set()

        for ex in examples:
            tokens = tokenize(ex.text)
            token_counts[ex.label].update(tokens)
            vocab.update(tokens)

        n_total = len(examples)
        vocab_size = len(vocab)

        self._class_log_prior = {
            label: math.log(count / n_total) for label, count in class_counts.items()
        }

        self._token_log_likelihood = {}
        for label in (0, 1):
            total_tokens_in_class = sum(token_counts[label].values())
            denom = total_tokens_in_class + _LAPLACE_ALPHA * vocab_size
            self._token_log_likelihood[label] = {
                token: math.log((token_counts[label][token] + _LAPLACE_ALPHA) / denom)
                for token in vocab
            }
            # Smoothed log-likelihood for any token unseen at train time.
            self._token_log_likelihood[label]["__unseen__"] = math.log(_LAPLACE_ALPHA / denom)

        self._vocab = vocab
        self._n_train_examples = n_total
        self._fitted = True

    def predict_proba(self, text: str) -> float:
        """
        P(label=1 | text) — i.e. how likely `text` is an injection attempt,
        in [0, 1]. Raises RuntimeError if the model hasn't been trained.
        """
        if not self._fitted:
            raise RuntimeError("InjectionClassifier.predict_proba() called before train()/load()")

        tokens = tokenize(text)
        log_scores: dict[int, float] = {}
        for label in (0, 1):
            score = self._class_log_prior[label]
            likelihoods = self._token_log_likelihood[label]
            for token in tokens:
                score += likelihoods.get(token, likelihoods["__unseen__"])
            log_scores[label] = score

        # log-sum-exp for a numerically stable softmax over the two classes.
        max_score = max(log_scores.values())
        exp_scores = {label: math.exp(score - max_score) for label, score in log_scores.items()}
        total = sum(exp_scores.values())
        return exp_scores[1] / total if total else 0.0

    def to_dict(self) -> dict:
        return {
            "class_log_prior": self._class_log_prior,
            "token_log_likelihood": self._token_log_likelihood,
            "vocab_size": len(self._vocab),
            "n_train_examples": self._n_train_examples,
        }

    @classmethod
    def from_dict(cls, data: dict) -> InjectionClassifier:
        clf = cls()
        clf._class_log_prior = {int(k): v for k, v in data["class_log_prior"].items()}
        clf._token_log_likelihood = {
            int(label): dict(likelihoods)
            for label, likelihoods in data["token_log_likelihood"].items()
        }
        clf._vocab = {tok for tok in clf._token_log_likelihood.get(1, {}) if tok != "__unseen__"}
        clf._n_train_examples = data.get("n_train_examples", 0)
        clf._fitted = True
        return clf

    def save(self, path: str | Path = DEFAULT_ARTIFACT_PATH) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: str | Path = DEFAULT_ARTIFACT_PATH) -> InjectionClassifier:
        return cls.from_dict(json.loads(Path(path).read_text()))


@lru_cache(maxsize=1)
def get_default_classifier() -> InjectionClassifier:
    """
    Zero-config classifier: trained in-process, once per process, from the
    bundled dataset (`core/detection/dataset.py`). Mirrors E4's "zero
    configuration still gets you something" default-policy pattern — no
    artifact file, no training step required to use E5's classifier backend.

    If `DETECTION_MODEL_PATH` (see `core/detection/scanner.py`) points at a
    saved artifact instead, that path is loaded rather than this default
    being trained — this function is only the fallback.
    """
    clf = InjectionClassifier()
    clf.train(load_examples())
    return clf
