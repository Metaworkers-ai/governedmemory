"""
Provenance graph (E6).

Every MemoryRecord.provenance.parent_ids has existed since E1 as "provenance
graph edges (E6)" — the memory IDs a record was derived from (an agent-derived
summary might list the three support tickets it was distilled from). Until
now nothing ever built a graph out of that field or walked it. This module
does both: build_provenance_graph() turns a flat set of (id, parent_ids)
pairs into a queryable graph, and ProvenanceGraph.ancestors()/descendants()
answer "what did this come from" and "what came from this" across
arbitrarily deep chains.

Pure Python, no DB access — mirrors the style of core/retrieval_engine/fusion.py
(operates on plain ids, not full records). MemoryStore.get_provenance()
(core/memory_store/store.py) is the DB-aware caller: it fetches every
(id, parent_ids) pair for a tenant, builds the graph here, and returns one
node's lineage. core/audit/cascade_purge.py builds on top of descendants()
to compute a cascade-purge delete set.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProvenanceGraph:
    """
    A directed graph over memory IDs. An edge child -> parent means
    "child was derived from parent" (child's parent_ids contains parent's id).

    parents[id]  -> that record's own immediate parent_ids ("what this came from, directly")
    children[id] -> ids of records whose parent_ids directly name this one
                    ("what was directly derived from this")

    An id referenced only as someone's parent_id but not itself present in
    the input (already deleted, out of tenant, or simply not fetched) is
    tolerated: it has no entry in `parents`, so ancestors() treats it as a
    leaf rather than raising.
    """

    parents: dict[str, list[str]] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)

    def ancestors(self, memory_id: str) -> list[str]:
        """All ancestors, transitively, in breadth-first order. Cycle-safe."""
        return _walk(memory_id, self.parents)

    def descendants(self, memory_id: str) -> list[str]:
        """All descendants, transitively, in breadth-first order. Cycle-safe."""
        return _walk(memory_id, self.children)


def _walk(start: str, edges: dict[str, list[str]]) -> list[str]:
    """
    Breadth-first traversal collecting every node reachable from `start`
    (exclusive of `start` itself). Guards against cycles — a malformed
    parent_ids loop (which nothing upstream prevents, since parent_ids is
    free-form JSONB, not a foreign key) can't hang traversal or double-count
    a node.
    """
    visited: set[str] = {start}
    order: list[str] = []
    queue: list[str] = list(edges.get(start, []))
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        queue.extend(edges.get(node, []))
    return order


def build_provenance_graph(records: list[tuple[str, list[str]]]) -> ProvenanceGraph:
    """
    Build a ProvenanceGraph from (memory_id, parent_ids) pairs, e.g.:

        edges = [(r.id, r.provenance.parent_ids) for r in records]
        graph = build_provenance_graph(edges)
        graph.ancestors("some-id")
        graph.descendants("some-id")

    A parent_id that never appears as a memory_id in `records` becomes a
    leaf in `parents`/`children` rather than raising — the same
    already-deleted-or-out-of-tenant tolerance described on ProvenanceGraph.
    """
    parents: dict[str, list[str]] = {}
    children: dict[str, list[str]] = {}

    for memory_id, parent_ids in records:
        parents[memory_id] = list(parent_ids)
        children.setdefault(memory_id, [])
        for pid in parent_ids:
            children.setdefault(pid, [])
            children[pid].append(memory_id)

    return ProvenanceGraph(parents=parents, children=children)
