"""
Heuristic prompt-injection scanner (E2).

This is a fast, explainable, rule-based scorer — not a trained classifier.
It exists so obviously-malicious content (fake system directives, instruction
overrides, credential exfiltration attempts) gets flagged even when it arrives
through a nominally trusted channel, not just when the source_type itself is
untrusted. E5 (core/detection/) adds a trained classifier that tracks
precision/recall and can augment or replace this scanner via the
DETECTION_BACKEND env var — this module remains the default and is unchanged
by E5, so these patterns keep catching the common cases on their own.

Each pattern contributes a weight in [0, 1]. Multiple independent matches are
combined via a noisy-OR (`1 - product(1 - weight_i)`) rather than a simple
max, so content matching several attack patterns at once scores higher than
content matching just one — reflecting that co-occurring signals raise
confidence rather than just repeating it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _Pattern:
    regex: re.Pattern[str]
    weight: float
    label: str


_PATTERNS: list[_Pattern] = [
    _Pattern(
        re.compile(r"\bignore\b.{0,40}\b(previous|prior|above)\b.{0,20}\binstructions?\b", re.I),
        0.9,
        "instruction_override",
    ),
    _Pattern(
        re.compile(
            r"\bdisregard\b.{0,40}\b(previous|prior|above|verification|identity|approval|instructions?)\b",
            re.I,
        ),
        0.85,
        "instruction_override",
    ),
    _Pattern(re.compile(r"\bsystem\s*(override|prompt)\b", re.I), 0.8, "fake_system_directive"),
    _Pattern(
        re.compile(r"\bAI\s+(ASSISTANT|AGENT)\b\s*[:\-—]", re.I), 0.75, "fake_agent_directive"
    ),
    _Pattern(re.compile(r"\byou are now\b|\bnew instructions?\s*:", re.I), 0.7, "role_override"),
    _Pattern(
        re.compile(
            r"\b(reveal|provide|send|reply with)\b.{0,40}\b(system prompt|api key|credentials|password|account)\b",
            re.I,
        ),
        0.85,
        "credential_exfiltration",
    ),
    _Pattern(
        re.compile(r"\bgrant\b.{0,40}\b(access|admin|refund|upgrade|approval)\b", re.I),
        0.6,
        "privilege_escalation",
    ),
    _Pattern(
        re.compile(r"\bwithout\b.{0,20}\b(approval|verification)\b", re.I),
        0.5,
        "verification_bypass",
    ),
]


def scan_for_injection(content: str) -> tuple[float, list[str]]:
    """
    Score `content` for likely prompt-injection / social-engineering patterns.

    Returns (score in [0, 1], sorted list of matched pattern labels).
    Empty or falsy content always scores 0.0 with no labels.
    """
    if not content:
        return 0.0, []

    matches = [(p.weight, p.label) for p in _PATTERNS if p.regex.search(content)]
    if not matches:
        return 0.0, []

    combined_miss_probability = 1.0
    for weight, _ in matches:
        combined_miss_probability *= 1.0 - weight
    score = round(min(1.0 - combined_miss_probability, 1.0), 3)

    labels = sorted({label for _, label in matches})
    return score, labels
