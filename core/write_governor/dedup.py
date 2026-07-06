"""
Exact-duplicate detection for the Write Governor (E2).

Runs before embedding is computed — a whitespace/case-normalized resubmission
of the same fact for the same customer doesn't need a fresh embedding, it
needs to supersede the old record instead. This is intentionally simple:
normalized-text equality, not semantic similarity. A near-duplicate with
different wording is treated as a new, independent memory — semantic dedup
would need an embedding-similarity pass, a reasonable later enhancement once
retrieval quality work (E3) is underway.

The DB fetch (scoping to one tenant+customer, non-superseded rows) stays in
MemoryStore, matching the existing separation where this package only
contains pure logic and store.py owns all SQL.
"""

from __future__ import annotations

import re
from typing import Any


def normalize(content: str) -> str:
    """Case/whitespace-insensitive normalization for exact-duplicate comparison."""
    return re.sub(r"\s+", " ", content.strip().lower())


def find_duplicate(existing: list[dict[str, Any]], content: str) -> dict[str, Any] | None:
    """
    The most recent non-superseded record among `existing` whose content
    matches `content` after normalization, or None.

    `existing` should already be scoped to one tenant+customer and ordered
    newest-first; each row needs at least "content" and "superseded_by".
    """
    target = normalize(content)
    for row in existing:
        if row.get("superseded_by") is None and normalize(row["content"]) == target:
            return row
    return None
