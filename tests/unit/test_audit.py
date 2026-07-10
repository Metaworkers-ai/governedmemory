"""
Unit tests for E6: provenance graph, cascade purge planning, and the
formal audit hash-chain verifier.

No Docker/DB needed — everything in core/audit/ is pure Python. Coverage
of the DB-integrated entry points (MemoryStore.get_provenance(),
.purge_cascade(), .verify_audit_chain()) lives in
tests/integration/test_memory_store.py, since those need a real audit
table and real memory rows.
"""

import copy

from core.audit import (
    build_provenance_graph,
    compute_event_hash,
    plan_cascade_purge,
    verify_chain,
)

# ---------------------------------------------------------------------------
# provenance_graph.py
# ---------------------------------------------------------------------------


class TestProvenanceGraph:
    def _diamond(self):
        # A has no parents. B and C are both derived from A. D is derived
        # from both B and C — a diamond-shaped lineage, the simplest case
        # that isn't just a straight chain.
        return build_provenance_graph(
            [
                ("A", []),
                ("B", ["A"]),
                ("C", ["A"]),
                ("D", ["B", "C"]),
            ]
        )

    def test_ancestors_of_root_is_empty(self):
        graph = self._diamond()
        assert graph.ancestors("A") == []

    def test_ancestors_transitive_through_diamond(self):
        graph = self._diamond()
        assert set(graph.ancestors("D")) == {"A", "B", "C"}

    def test_descendants_of_leaf_is_empty(self):
        graph = self._diamond()
        assert graph.descendants("D") == []

    def test_descendants_transitive_through_diamond(self):
        graph = self._diamond()
        assert set(graph.descendants("A")) == {"B", "C", "D"}

    def test_immediate_parents_and_children_are_exact(self):
        graph = self._diamond()
        assert graph.parents["D"] == ["B", "C"]
        assert set(graph.children["A"]) == {"B", "C"}

    def test_unknown_id_has_no_ancestors_or_descendants(self):
        graph = self._diamond()
        assert graph.ancestors("does-not-exist") == []
        assert graph.descendants("does-not-exist") == []

    def test_dangling_parent_id_is_tolerated_as_a_leaf(self):
        """A parent_id pointing at a record that was never fetched (already
        deleted, wrong tenant, etc.) must not raise — it's just a leaf."""
        graph = build_provenance_graph([("child", ["ghost-parent"])])
        assert graph.ancestors("child") == ["ghost-parent"]
        assert graph.ancestors("ghost-parent") == []

    def test_cycle_does_not_hang_or_duplicate(self):
        """Nothing at the DB layer prevents a parent_ids loop (it's JSONB,
        not a foreign key) — traversal must still terminate and must not
        double-count a node."""
        graph = build_provenance_graph([("X", ["Y"]), ("Y", ["X"])])
        assert graph.ancestors("X") == ["Y"]
        assert graph.descendants("X") == ["Y"]

    def test_empty_graph(self):
        graph = build_provenance_graph([])
        assert graph.ancestors("anything") == []
        assert graph.descendants("anything") == []


# ---------------------------------------------------------------------------
# cascade_purge.py
# ---------------------------------------------------------------------------


class TestCascadePurge:
    def _chain(self):
        # A -> B -> C (a straight three-hop chain)
        return build_provenance_graph([("A", []), ("B", ["A"]), ("C", ["B"])])

    def test_purging_root_takes_every_descendant(self):
        graph = self._chain()
        plan = plan_cascade_purge(graph, "A")
        assert set(plan.all_ids) == {"A", "B", "C"}
        assert plan.descendant_count == 2

    def test_purging_a_leaf_takes_only_itself(self):
        graph = self._chain()
        plan = plan_cascade_purge(graph, "C")
        assert plan.all_ids == ["C"]
        assert plan.descendant_count == 0

    def test_purging_a_middle_node_takes_only_its_own_descendants(self):
        graph = self._chain()
        plan = plan_cascade_purge(graph, "B")
        assert set(plan.all_ids) == {"B", "C"}
        assert "A" not in plan.all_ids  # ancestors are never swept up, only descendants

    def test_root_id_always_included_even_with_no_descendants(self):
        graph = build_provenance_graph([])
        plan = plan_cascade_purge(graph, "lonely")
        assert plan.all_ids == ["lonely"]


# ---------------------------------------------------------------------------
# verifier.py
# ---------------------------------------------------------------------------


def _chain_of_events(n: int) -> list[dict]:
    """Build `n` events whose hash/prev_hash are correctly chained, exactly
    the way MemoryStore._audit() computes them."""
    events = []
    prev_hash = ""
    for i in range(n):
        event_id = f"event-{i}"
        ts = f"2026-01-01T00:00:{i:02d}"
        op = "write"
        memory_ids = [f"m{i}"]
        outcome = "allow"
        h = compute_event_hash(prev_hash, event_id, "tenant-1", ts, op, memory_ids, outcome)
        events.append(
            {
                "id": event_id,
                "tenant_id": "tenant-1",
                "ts": ts,
                "op": op,
                "memory_ids": memory_ids,
                "outcome": outcome,
                "hash": h,
                "prev_hash": prev_hash,
            }
        )
        prev_hash = h
    return events


class TestVerifier:
    def test_empty_chain_is_valid(self):
        result = verify_chain([])
        assert result.valid is True
        assert result.total_events == 0

    def test_intact_chain_of_one_is_valid(self):
        result = verify_chain(_chain_of_events(1))
        assert result.valid is True
        assert result.events_checked == 1

    def test_intact_chain_of_several_is_valid(self):
        result = verify_chain(_chain_of_events(5))
        assert result.valid is True
        assert result.events_checked == 5
        assert result.total_events == 5

    def test_in_place_tamper_is_detected(self):
        """Modifying a stored field (outcome) without recomputing hash — a
        same-row UPDATE, which the DB has no trigger to prevent — must be
        caught even though prev_hash linkage is completely untouched."""
        events = _chain_of_events(4)
        tampered = copy.deepcopy(events)
        tampered[2]["outcome"] = "deny"

        result = verify_chain(tampered)
        assert result.valid is False
        assert result.broken_index == 2
        assert result.broken_event_id == "event-2"
        assert "modified in place" in result.reason

        # everything strictly before the tampered event still checks out
        assert result.events_checked == 2

    def test_memory_ids_tamper_is_detected(self):
        events = _chain_of_events(3)
        tampered = copy.deepcopy(events)
        tampered[1]["memory_ids"] = ["some-other-memory-id"]

        result = verify_chain(tampered)
        assert result.valid is False
        assert result.broken_index == 1

    def test_deleted_event_breaks_linkage(self):
        """Removing an event entirely (not just editing it) must also be
        caught, via the prev_hash linkage check rather than a hash mismatch."""
        events = _chain_of_events(4)
        with_gap = [events[0], events[2], events[3]]  # events[1] silently removed

        result = verify_chain(with_gap)
        assert result.valid is False
        assert result.broken_index == 1
        assert "prev_hash mismatch" in result.reason

    def test_reordered_events_break_linkage(self):
        events = _chain_of_events(3)
        reordered = [events[0], events[2], events[1]]

        result = verify_chain(reordered)
        assert result.valid is False
        assert result.broken_index == 1

    def test_first_event_must_have_empty_prev_hash(self):
        events = _chain_of_events(1)
        events[0]["prev_hash"] = "not-empty"

        result = verify_chain(events)
        assert result.valid is False
        assert result.broken_index == 0

    def test_memory_ids_as_json_string_is_accepted(self):
        """list_audit() rows may come back with memory_ids already parsed
        as a list, or (depending on psycopg2/driver behavior) as a raw
        JSON string — verify_chain() must handle either, same as
        store.py's own _jsonb_list() helper does."""
        events = _chain_of_events(2)
        as_json_string = copy.deepcopy(events)
        for e in as_json_string:
            e["memory_ids"] = f'["{e["memory_ids"][0]}"]'

        result = verify_chain(as_json_string)
        assert result.valid is True
