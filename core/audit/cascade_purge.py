"""
Cascade purge (E6).

MemoryStore.delete() (E1) hard-deletes exactly one record. That's correct
for "this one memory is wrong, remove it" but incomplete for two governance
scenarios this project exists for:

  - GDPR right-to-erasure: if memory X was later distilled into an
    agent-derived summary Y (Y.provenance.parent_ids contains X), deleting
    X alone leaves Y behind — the customer's data survives via its own
    derivative even after the "original" was erased.
  - Poisoning cleanup: if X is discovered to be a prompt-injection payload
    after the fact, anything derived from X (summaries, follow-up agent
    actions logged as memories, etc.) is downstream of a poisoned source
    and arguably shouldn't survive X's removal either.

plan_cascade_purge() computes what a cascade purge of `root_id` would
delete: the root plus every transitive descendant in the provenance graph.
It's a pure function over a ProvenanceGraph — MemoryStore.purge_cascade()
(core/memory_store/store.py) is the DB-aware caller that builds the graph,
calls this, and actually deletes + audits in one transaction.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.audit.provenance_graph import ProvenanceGraph


@dataclass(frozen=True)
class CascadePurgePlan:
    """What a cascade purge of `root_id` would delete."""

    root_id: str
    descendant_ids: list[str]

    @property
    def all_ids(self) -> list[str]:
        """root_id followed by every descendant — the full delete set."""
        return [self.root_id, *self.descendant_ids]

    @property
    def descendant_count(self) -> int:
        return len(self.descendant_ids)


def plan_cascade_purge(graph: ProvenanceGraph, root_id: str) -> CascadePurgePlan:
    """
    Compute the full delete set for purging `root_id` and everything
    (transitively) derived from it. Does not touch the database — see
    MemoryStore.purge_cascade() for the write path that applies this plan.
    """
    return CascadePurgePlan(root_id=root_id, descendant_ids=graph.descendants(root_id))
