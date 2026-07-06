"""
Reciprocal Rank Fusion for the Retrieval Engine (E3).

Combines multiple independently-ranked result lists (vector similarity,
lexical relevance) into a single ranking, without needing to normalize or
compare their raw scores directly — cosine distance and ts_rank aren't on
the same scale, so averaging them would be meaningless. RRF sidesteps that
by scoring purely on rank position: an item ranked highly in *either* list
contributes strongly, and an item ranked highly in *both* lists (a genuine
hybrid match) naturally rises to the top.

score(item) = sum over each list containing item of 1 / (k + rank)

`k` (default 60) is the standard RRF damping constant from the original
paper (Cormack et al., 2009) — it de-emphasizes the exact rank position at
the top of each list so one list's #1 result doesn't dominate the fused
ranking just for being #1 rather than #2.
"""

from __future__ import annotations

_DEFAULT_K = 60


def reciprocal_rank_fusion(
    ranked_id_lists: list[list[str]], k: int = _DEFAULT_K
) -> dict[str, float]:
    """
    ranked_id_lists: each a list of IDs in rank order (best first).
    Returns: {id: fused_score}, for every ID appearing in any list.
    Higher score = better. Caller sorts by score descending.
    """
    scores: dict[str, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, item_id in enumerate(ranked_ids, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores
