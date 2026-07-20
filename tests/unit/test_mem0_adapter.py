from __future__ import annotations

import pytest
from metaworkers import ExternalContractError, GovernanceDenied, Source
from metaworkers.adapters.mem0 import GovernedMem0


class FakeMem0:
    def __init__(self):
        self.add_calls = []
        self.search_calls = []

    def add(self, messages, **kwargs):
        self.add_calls.append((messages, kwargs))
        return {"results": [{"id": "m-1", "memory": "safe"}]}

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return {
            "results": [
                {"id": "m-1", "memory": "safe"},
                {"id": "m-2", "memory": "quarantined"},
                {"memory": "legacy"},
            ]
        }


class FakeGovernance:
    def __init__(self, storage="allow"):
        self.storage = storage
        self.evaluated = []
        self.bound = []

    def evaluate_external_write(self, **kwargs):
        self.evaluated.append(kwargs)
        return {
            "operation_id": "op-1",
            "correlation_id": "corr-1",
            "storage": self.storage,
            "retrieval": "allow",
            "taint": "trusted",
            "status": "evaluated",
        }

    def bind_external_memories(self, **kwargs):
        self.bound.append(kwargs)
        return {
            "operation_id": "op-1",
            "correlation_id": "corr-1",
            "storage": "allow",
            "retrieval": "allow",
            "taint": "trusted",
            "status": "completed",
            "external_memory_ids": kwargs["external_memory_ids"],
            "binding_audit_ids": ["audit-bind"],
        }

    def evaluate_external_candidates(self, **kwargs):
        decisions = []
        for candidate in kwargs["candidates"]:
            memory_id = candidate["external_memory_id"]
            decisions.append(
                {
                    "external_memory_id": memory_id,
                    "status": "quarantined"
                    if memory_id == "m-2"
                    else "untracked"
                    if not memory_id
                    else "governed",
                    "decision": "exclude" if memory_id == "m-2" else "allow",
                    "reason": "test",
                }
            )
        return {
            "operation_id": "op-search",
            "correlation_id": "corr-search",
            "audit_id": "audit-search",
            "decisions": decisions,
        }

    def quarantine_external_memory(
        self, external_memory_id, reason, *, agent_id="system", session_id="external-quarantine"
    ):
        return {
            "external_memory_id": external_memory_id,
            "reason": reason,
            "agent_id": agent_id,
            "session_id": session_id,
        }

    def get_external_governance(self, external_memory_id):
        return {"external_memory_id": external_memory_id}

    def retry_binding(self, **kwargs):
        return kwargs


def test_add_governs_then_delegates_and_binds_ids():
    mem0 = FakeMem0()
    governance = FakeGovernance()
    adapter = GovernedMem0(mem0, governance, tenant_id="tenant-a", agent_id="agent-a")

    result = adapter.add(
        "customer prefers email",
        user_id="user-a",
        run_id="run-a",
        source=Source(type="user", ref="msg-a"),
        idempotency_key="key-a",
    )

    assert len(mem0.add_calls) == 1
    assert governance.bound[0]["external_memory_ids"] == ["m-1"]
    assert result["results"][0]["id"] == "m-1"
    assert result["governance"]["status"] == "completed"
    assert mem0.add_calls[0][1]["metadata"]["governedmemory_correlation_id"] == "corr-1"


def test_add_preserves_multiple_mem0_results_and_ids():
    class MultiMem0(FakeMem0):
        def add(self, messages, **kwargs):
            self.add_calls.append((messages, kwargs))
            return {"results": [{"id": "m-1"}, {"metadata": {"id": "m-2"}}]}

    mem0 = MultiMem0()
    governance = FakeGovernance()
    result = GovernedMem0(mem0, governance, tenant_id="tenant-a").add(
        "multiple", user_id="user-a", idempotency_key="multi-key"
    )
    assert GovernedMem0._external_id(result["results"][0]) == "m-1"
    assert GovernedMem0._external_id(result["results"][1]) == "m-2"
    assert governance.bound[0]["external_memory_ids"] == ["m-1", "m-2"]


def test_denied_write_never_calls_mem0():
    mem0 = FakeMem0()
    adapter = GovernedMem0(mem0, FakeGovernance(storage="deny"), tenant_id="tenant-a")
    with pytest.raises(GovernanceDenied):
        adapter.add("blocked", user_id="user-a")
    assert mem0.add_calls == []


def test_search_preserves_order_and_excludes_quarantined():
    mem0 = FakeMem0()
    adapter = GovernedMem0(mem0, FakeGovernance(), tenant_id="tenant-a")
    result = adapter.search("safe", user_id="user-a")
    assert [item["id"] for item in result["results"] if "id" in item] == ["m-1"]
    assert result["governance"]["decisions"][1]["status"] == "quarantined"


def test_quarantine_and_retry_delegate_to_governance():
    governance = FakeGovernance()
    adapter = GovernedMem0(FakeMem0(), governance, tenant_id="tenant-a")
    assert adapter.quarantine("m-1", "investigate") == {
        "external_memory_id": "m-1",
        "reason": "investigate",
        "agent_id": "system",
        "session_id": "external-quarantine",
    }
    assert adapter.retry_binding(correlation_id="corr", external_memory_ids=["m-1"]) == {
        "correlation_id": "corr",
        "external_memory_ids": ["m-1"],
    }


@pytest.mark.parametrize("mode", ["count", "id"])
def test_search_rejects_mismatched_governance_decisions(mode):
    class BrokenGovernance(FakeGovernance):
        def evaluate_external_candidates(self, **kwargs):
            response = super().evaluate_external_candidates(**kwargs)
            if mode == "count":
                response["decisions"] = response["decisions"][:1]
            else:
                response["decisions"][0]["external_memory_id"] = "wrong-id"
            return response

    with pytest.raises(ExternalContractError):
        GovernedMem0(FakeMem0(), BrokenGovernance(), tenant_id="tenant-a").search(
            "safe", user_id="user-a"
        )
