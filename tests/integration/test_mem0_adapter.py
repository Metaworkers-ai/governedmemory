"""Docker-backed integration for the synchronous Mem0 adapter."""

from __future__ import annotations

import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg2
import pytest
import uvicorn
from metaworkers import (
    ExternalBindingConflictError,
    ExternalContractError,
    ExternalOperationFailed,
    GovernanceDenied,
    GovernedMemory,
    IdempotencyConflictError,
    Source,
)
from metaworkers.adapters.mem0 import GovernedMem0

TENANT = "tenant-mem0-adapter"
API_KEY = "mem0-adapter-key"


class DeterministicMem0:
    def __init__(self, prefix="mem0"):
        self.prefix = prefix
        self.records = []
        self.calls = 0

    def add(self, messages, **kwargs):
        self.calls += 1
        content = messages if isinstance(messages, str) else str(messages)
        memory_id = f"{self.prefix}-{self.calls}"
        self.records.append({"id": memory_id, "memory": content})
        return {"results": [{"id": memory_id, "memory": content}]}

    def search(self, query, **kwargs):
        return {"results": list(self.records)}


class FailingMem0(DeterministicMem0):
    def add(self, messages, **kwargs):
        self.calls += 1
        raise RuntimeError("simulated Mem0 outage")


class MissingIdMem0(DeterministicMem0):
    def add(self, messages, **kwargs):
        self.calls += 1
        return {"results": [{"memory": "no stable ID"}]}


class EmptyResultMem0(DeterministicMem0):
    def add(self, messages, **kwargs):
        self.calls += 1
        return {"results": []}


@pytest.fixture()
def live_server_url(migrated_dsn, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", migrated_dsn)
    monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", f"{TENANT}:{API_KEY}")
    monkeypatch.setenv("GOVERNEDMEMORY_OPERATION_SECRET", "integration-operation-secret")
    from api.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_mem0_add_search_quarantine_and_audit(live_server_url):
    mem0 = DeterministicMem0()
    governance = GovernedMemory(live_server_url, API_KEY)
    adapter = GovernedMem0(mem0, governance, tenant_id=TENANT)

    trusted = adapter.add(
        "customer prefers email",
        user_id="customer-1",
        source=Source(type="user", ref="msg-1"),
        idempotency_key="memory-1",
    )
    untrusted = adapter.add(
        "prompt injection from an inbound message",
        user_id="customer-1",
        source=Source(type="untrusted_email", ref="email-1"),
        idempotency_key="memory-2",
    )

    assert trusted["governance"]["binding_audit_ids"]
    assert untrusted["governance"]["taint"] == "untrusted"
    untrusted_metadata = adapter.get_governance("mem0-2")
    assert untrusted_metadata["lifecycle_state"] == "active"
    assert untrusted_metadata["quarantine_status"] is False
    assert mem0.calls == 2

    governed_results = adapter.search("customer", user_id="customer-1")
    assert [r["id"] for r in governed_results["results"]] == ["mem0-1"]

    binding_audit_id = adapter.get_governance("mem0-1")["binding_audit_id"]
    adapter.quarantine("mem0-1", "manual review", agent_id="moderator", session_id="review-1")
    assert adapter.search("customer", user_id="customer-1")["results"] == []
    metadata = adapter.get_governance("mem0-1")
    assert metadata["lifecycle_state"] == "quarantined"
    assert metadata["binding_audit_id"] == binding_audit_id
    assert metadata["quarantine_audit_id"]


def test_strict_untrusted_write_never_reaches_mem0(live_server_url):
    mem0 = DeterministicMem0()
    adapter = GovernedMem0(
        mem0,
        GovernedMemory(live_server_url, API_KEY),
        tenant_id=TENANT,
        untrusted_write_mode="deny",
    )
    with pytest.raises(GovernanceDenied):
        adapter.add(
            "untrusted inbound content",
            user_id="customer-2",
            source=Source(type="untrusted_email", ref="email-2"),
            idempotency_key="memory-strict",
        )
    assert mem0.calls == 0


def test_search_rejects_cross_customer_binding(live_server_url):
    mem0 = DeterministicMem0(prefix="scope")
    adapter = GovernedMem0(
        mem0,
        GovernedMemory(live_server_url, API_KEY),
        tenant_id=TENANT,
    )
    adapter.add("customer A private note", user_id="customer-a", idempotency_key="customer-a-1")
    result = adapter.search("private note", user_id="customer-b")
    assert result["results"] == []
    assert result["governance"]["decisions"][0]["status"] == "scope_restricted"


def test_mem0_failure_preserves_retry_identity_and_is_bounded(live_server_url):
    mem0 = FailingMem0(prefix="failure")
    governance = GovernedMemory(live_server_url, API_KEY)
    adapter = GovernedMem0(mem0, governance, tenant_id=TENANT)
    errors = []
    for _ in range(3):
        with pytest.raises(ExternalOperationFailed) as exc_info:
            adapter.add("will fail", user_id="customer-f", idempotency_key="failure-key")
        errors.append(exc_info.value)
    assert errors[0].correlation_id
    assert errors[0].idempotency_key == "failure-key"
    with pytest.raises(ExternalOperationFailed):
        adapter.add("will fail", user_id="customer-f", idempotency_key="failure-key")
    assert mem0.calls == 3


def test_missing_mem0_id_is_typed_and_retryable(live_server_url):
    missing = MissingIdMem0(prefix="missing")
    governance = GovernedMemory(live_server_url, API_KEY)
    adapter = GovernedMem0(missing, governance, tenant_id=TENANT)
    with pytest.raises(ExternalContractError) as exc_info:
        adapter.add("missing id", user_id="customer-m", idempotency_key="missing-key")
    assert exc_info.value.correlation_id
    assert exc_info.value.idempotency_key == "missing-key"


def test_empty_mem0_result_completes_without_binding(live_server_url, migrated_dsn):
    mem0 = EmptyResultMem0(prefix="empty")
    governance = GovernedMemory(live_server_url, API_KEY)
    adapter = GovernedMem0(mem0, governance, tenant_id=TENANT)

    result = adapter.add(
        "duplicate or no extracted fact",
        user_id="customer-empty",
        idempotency_key="empty-operation",
    )

    assert result["results"] == []
    assert result["governance"]["status"] == "completed"
    assert result["governance"]["external_memory_ids"] == []
    assert result["governance"]["binding_audit_ids"]
    assert mem0.calls == 1

    replay = adapter.add(
        "duplicate or no extracted fact",
        user_id="customer-empty",
        idempotency_key="empty-operation",
    )
    assert replay["results"] == []
    assert replay["governance"]["idempotent_replay"] is True
    assert replay["governance"]["original_mem0_result_available"] is False
    assert mem0.calls == 1

    with psycopg2.connect(migrated_dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT status, external_memory_ids, decision
               FROM external_governance_operations
               WHERE tenant_id = %s AND idempotency_key = %s""",
            (TENANT, "empty-operation"),
        )
        status, external_ids, decision = cur.fetchone()
        cur.execute(
            """SELECT COUNT(*) FROM external_memory_bindings
               WHERE tenant_id = %s AND operation_id = %s::uuid""",
            (TENANT, decision["operation_id"]),
        )
        binding_count = cur.fetchone()[0]
    assert status == "completed"
    assert external_ids == []
    assert decision["binding_audit_ids"]
    assert binding_count == 0


def test_concurrent_same_key_evaluation_is_idempotent(live_server_url):
    governance = GovernedMemory(live_server_url, API_KEY)

    def evaluate():
        return governance.evaluate_external_write(
            customer_id="customer-concurrent",
            agent_id="agent-concurrent",
            session_id="session-concurrent",
            content="same payload",
            source=Source(type="user", ref="concurrent"),
            idempotency_key="concurrent-key",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: evaluate(), range(8)))
    assert {result["operation_id"] for result in results}.__len__() == 1
    assert {result["correlation_id"] for result in results}.__len__() == 1


def test_changed_payload_with_same_key_is_a_typed_conflict(live_server_url):
    governance = GovernedMemory(live_server_url, API_KEY)
    kwargs = {
        "customer_id": "customer-conflict",
        "agent_id": "agent-conflict",
        "session_id": "session-conflict",
        "source": Source(type="user", ref="conflict"),
        "idempotency_key": "conflict-key",
    }
    governance.evaluate_external_write(content="first", **kwargs)
    with pytest.raises(IdempotencyConflictError):
        governance.evaluate_external_write(content="changed", **kwargs)


def test_changed_write_policy_with_same_key_is_a_typed_conflict(
    live_server_url,
    migrated_dsn,
):
    governance = GovernedMemory(live_server_url, API_KEY)
    kwargs = {
        "customer_id": "customer-policy-conflict",
        "agent_id": "agent-policy-conflict",
        "session_id": "session-policy-conflict",
        "content": "same content",
        "source": Source(type="user", ref="policy-conflict"),
        "idempotency_key": "policy-conflict-key",
    }
    governance.evaluate_external_write(strict_untrusted_write=False, **kwargs)
    with pytest.raises(IdempotencyConflictError):
        governance.evaluate_external_write(strict_untrusted_write=True, **kwargs)
    with psycopg2.connect(migrated_dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT context FROM external_governance_operations
               WHERE tenant_id = %s AND idempotency_key = %s""",
            (TENANT, "policy-conflict-key"),
        )
        context = cur.fetchone()[0]
    assert "content_digest" not in context
    assert context["content_signature"] != hashlib.sha256(b"same content").hexdigest()
    assert context["strict_untrusted_write"] is False


def test_binding_pending_recovery_rejects_altered_ids(live_server_url, migrated_dsn):
    governance = GovernedMemory(live_server_url, API_KEY)
    owner = governance.evaluate_external_write(
        customer_id="customer-owner",
        agent_id="agent-owner",
        session_id="session-owner",
        content="owner",
        source=Source(type="user", ref="owner"),
        idempotency_key="owner-operation",
    )
    governance.bind_external_memories(
        correlation_id=owner["correlation_id"], external_memory_ids=["occupied-id"]
    )
    pending = governance.evaluate_external_write(
        customer_id="customer-pending",
        agent_id="agent-pending",
        session_id="session-pending",
        content="pending",
        source=Source(type="user", ref="pending"),
        idempotency_key="pending-operation",
    )
    with pytest.raises(ExternalBindingConflictError):
        governance.bind_external_memories(
            correlation_id=pending["correlation_id"], external_memory_ids=["occupied-id"]
        )
    with pytest.raises(ExternalBindingConflictError):
        governance.retry_binding(
            correlation_id=pending["correlation_id"], external_memory_ids=["different-id"]
        )
    with psycopg2.connect(migrated_dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT external_memory_ids, decision
               FROM external_governance_operations
               WHERE tenant_id = %s AND correlation_id = %s""",
            (TENANT, pending["correlation_id"]),
        )
        stored_ids, decision = cur.fetchone()
    assert stored_ids == ["occupied-id"]
    assert decision["external_memory_ids"] == ["occupied-id"]


def test_binding_conflict_and_retry_are_serialized(
    live_server_url,
    migrated_dsn,
    monkeypatch,
):
    governance = GovernedMemory(live_server_url, API_KEY)
    owner = governance.evaluate_external_write(
        customer_id="customer-race-owner",
        agent_id="agent-race-owner",
        session_id="session-race-owner",
        content="race owner",
        source=Source(type="user", ref="race-owner"),
        idempotency_key="race-owner-operation",
    )
    governance.bind_external_memories(
        correlation_id=owner["correlation_id"],
        external_memory_ids=["race-occupied-id"],
    )
    pending = governance.evaluate_external_write(
        customer_id="customer-race-pending",
        agent_id="agent-race-pending",
        session_id="session-race-pending",
        content="race pending",
        source=Source(type="user", ref="race-pending"),
        idempotency_key="race-pending-operation",
    )

    from api.main import app

    store = app.state.store
    original_mark_pending = store._set_binding_pending_in_tx
    pending_written = threading.Event()
    allow_commit = threading.Event()

    def pause_after_pending_write(cur, operation, reason, external_memory_ids):
        original_mark_pending(cur, operation, reason, external_memory_ids)
        pending_written.set()
        assert allow_commit.wait(timeout=5)

    monkeypatch.setattr(store, "_set_binding_pending_in_tx", pause_after_pending_write)

    def first_attempt():
        with pytest.raises(ExternalBindingConflictError):
            governance.bind_external_memories(
                correlation_id=pending["correlation_id"],
                external_memory_ids=["race-occupied-id"],
            )

    def competing_retry():
        with pytest.raises(ExternalBindingConflictError):
            governance.retry_binding(
                correlation_id=pending["correlation_id"],
                external_memory_ids=["race-different-id"],
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_attempt)
        assert pending_written.wait(timeout=5)
        second = pool.submit(competing_retry)
        time.sleep(0.1)
        assert not second.done()
        allow_commit.set()
        first.result(timeout=5)
        second.result(timeout=5)

    with psycopg2.connect(migrated_dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT status, external_memory_ids, decision
               FROM external_governance_operations
               WHERE tenant_id = %s AND correlation_id = %s""",
            (TENANT, pending["correlation_id"]),
        )
        status, stored_ids, decision = cur.fetchone()
    assert status == "binding_pending"
    assert stored_ids == ["race-occupied-id"]
    assert decision["external_memory_ids"] == ["race-occupied-id"]


def test_concurrent_same_id_binding_completes_once(live_server_url, migrated_dsn):
    governance = GovernedMemory(live_server_url, API_KEY)
    evaluation = governance.evaluate_external_write(
        customer_id="customer-bind-once",
        agent_id="agent-bind-once",
        session_id="session-bind-once",
        content="bind exactly once",
        source=Source(type="user", ref="bind-once"),
        idempotency_key="bind-once-operation",
    )

    def bind(index):
        method = governance.bind_external_memories if index % 2 == 0 else governance.retry_binding
        return method(
            correlation_id=evaluation["correlation_id"],
            external_memory_ids=["bind-once-id"],
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(bind, range(8)))

    assert {result["status"] for result in results} == {"completed"}
    assert len({tuple(result["binding_audit_ids"]) for result in results}) == 1
    with psycopg2.connect(migrated_dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT COUNT(*), MIN(binding_audit_id::text), MAX(binding_audit_id::text)
               FROM external_memory_bindings
               WHERE tenant_id = %s AND external_memory_id = %s""",
            (TENANT, "bind-once-id"),
        )
        binding_count, first_audit_id, last_audit_id = cur.fetchone()
        cur.execute(
            """SELECT COUNT(*) FROM audit
               WHERE tenant_id = %s AND op = 'external_binding'
                 AND memory_ids @> %s::jsonb""",
            (TENANT, '["bind-once-id"]'),
        )
        audit_count = cur.fetchone()[0]
    assert binding_count == 1
    assert first_audit_id == last_audit_id
    assert audit_count == 1


def test_competing_multi_id_bindings_do_not_deadlock(live_server_url, migrated_dsn):
    governance = GovernedMemory(live_server_url, API_KEY)

    def evaluate(suffix):
        return governance.evaluate_external_write(
            customer_id=f"customer-multi-{suffix}",
            agent_id=f"agent-multi-{suffix}",
            session_id=f"session-multi-{suffix}",
            content=f"multi binding {suffix}",
            source=Source(type="user", ref=f"multi-{suffix}"),
            idempotency_key=f"multi-binding-{suffix}",
        )

    first = evaluate("first")
    second = evaluate("second")

    def attempt(correlation_id, external_ids):
        try:
            result = governance.bind_external_memories(
                correlation_id=correlation_id,
                external_memory_ids=external_ids,
            )
            return ("completed", result["operation_id"])
        except ExternalBindingConflictError:
            return ("binding_pending", None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                attempt,
                first["correlation_id"],
                ["multi-shared-a", "multi-shared-b"],
            ),
            pool.submit(
                attempt,
                second["correlation_id"],
                ["multi-shared-b", "multi-shared-a"],
            ),
        ]
        outcomes = [future.result(timeout=5) for future in futures]

    assert sorted(status for status, _ in outcomes) == ["binding_pending", "completed"]
    winning_operation_id = next(operation_id for status, operation_id in outcomes if operation_id)
    with psycopg2.connect(migrated_dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT external_memory_id, operation_id::text
               FROM external_memory_bindings
               WHERE tenant_id = %s
                 AND external_memory_id IN ('multi-shared-a', 'multi-shared-b')
               ORDER BY external_memory_id""",
            (TENANT,),
        )
        bindings = cur.fetchall()
    assert bindings == [
        ("multi-shared-a", winning_operation_id),
        ("multi-shared-b", winning_operation_id),
    ]


def test_terminal_external_operation_states_are_immutable(live_server_url, migrated_dsn):
    governance = GovernedMemory(live_server_url, API_KEY)

    def snapshot(correlation_id):
        with psycopg2.connect(migrated_dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT status, external_memory_ids, decision, failure_reason,
                          retry_count, updated_at
                   FROM external_governance_operations
                   WHERE tenant_id = %s AND correlation_id = %s""",
                (TENANT, correlation_id),
            )
            return cur.fetchone()

    noop = governance.evaluate_external_write(
        customer_id="customer-terminal-noop",
        agent_id="agent-terminal-noop",
        session_id="session-terminal-noop",
        content="terminal noop",
        source=Source(type="user", ref="terminal-noop"),
        idempotency_key="terminal-noop-operation",
    )
    governance.complete_external_noop(correlation_id=noop["correlation_id"])
    completed_snapshot = snapshot(noop["correlation_id"])
    with pytest.raises(ExternalBindingConflictError):
        governance.bind_external_memories(
            correlation_id=noop["correlation_id"],
            external_memory_ids=["late-id"],
        )
    governance.mark_external_failure(
        correlation_id=noop["correlation_id"],
        reason="late failure must not mutate completion",
    )
    governance.complete_external_noop(correlation_id=noop["correlation_id"])
    assert snapshot(noop["correlation_id"]) == completed_snapshot

    failed = governance.evaluate_external_write(
        customer_id="customer-terminal-failed",
        agent_id="agent-terminal-failed",
        session_id="session-terminal-failed",
        content="terminal failed",
        source=Source(type="user", ref="terminal-failed"),
        idempotency_key="terminal-failed-operation",
    )
    for attempt in range(3):
        governance.mark_external_failure(
            correlation_id=failed["correlation_id"],
            reason=f"failure {attempt}",
        )
    failed_snapshot = snapshot(failed["correlation_id"])
    assert failed_snapshot[0] == "failed"
    governance.mark_external_failure(
        correlation_id=failed["correlation_id"],
        reason="fourth failure must not mutate terminal state",
    )
    replay = governance.evaluate_external_write(
        customer_id="customer-terminal-failed",
        agent_id="agent-terminal-failed",
        session_id="session-terminal-failed",
        content="terminal failed",
        source=Source(type="user", ref="terminal-failed"),
        idempotency_key="terminal-failed-operation",
    )
    assert replay["status"] == "failed"
    with pytest.raises(ExternalOperationFailed):
        governance.bind_external_memories(
            correlation_id=failed["correlation_id"],
            external_memory_ids=["failed-late-id"],
        )
    assert snapshot(failed["correlation_id"]) == failed_snapshot

    denied = governance.evaluate_external_write(
        customer_id="customer-terminal-denied",
        agent_id="agent-terminal-denied",
        session_id="session-terminal-denied",
        content="terminal denied",
        source=Source(type="untrusted_email", ref="terminal-denied"),
        idempotency_key="terminal-denied-operation",
        strict_untrusted_write=True,
    )
    assert denied["status"] == "denied"
    denied_snapshot = snapshot(denied["correlation_id"])
    governance.mark_external_failure(
        correlation_id=denied["correlation_id"],
        reason="late failure must not mutate denial",
    )
    with pytest.raises(ExternalOperationFailed):
        governance.complete_external_noop(correlation_id=denied["correlation_id"])
    with pytest.raises(ExternalOperationFailed):
        governance.bind_external_memories(
            correlation_id=denied["correlation_id"],
            external_memory_ids=["denied-late-id"],
        )
    assert snapshot(denied["correlation_id"]) == denied_snapshot


def test_concurrent_quarantine_is_idempotent(live_server_url):
    governance = GovernedMemory(live_server_url, API_KEY)
    evaluation = governance.evaluate_external_write(
        customer_id="customer-quarantine",
        agent_id="agent-quarantine",
        session_id="session-quarantine",
        content="quarantine me",
        source=Source(type="user", ref="quarantine"),
        idempotency_key="quarantine-operation",
    )
    governance.bind_external_memories(
        correlation_id=evaluation["correlation_id"], external_memory_ids=["quarantine-id"]
    )

    def quarantine(index):
        return governance.quarantine_external_memory(
            "quarantine-id",
            f"review-{index}",
            agent_id=f"moderator-{index}",
            session_id=f"s-{index}",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(quarantine, range(4)))
    assert len({result["quarantine_audit_id"] for result in results}) == 1
    assert len({result["binding_audit_id"] for result in results}) == 1


def test_compatibility_modes_against_real_store(live_server_url):
    mem0 = DeterministicMem0(prefix="modes")
    mem0.records.append({"id": "legacy-mode-id", "memory": "legacy"})
    governance = GovernedMemory(live_server_url, API_KEY)

    compatible = GovernedMem0(mem0, governance, tenant_id=TENANT, compatibility_mode="compatible")
    assert [
        item["id"] for item in compatible.search("legacy", user_id="customer-modes")["results"]
    ] == ["legacy-mode-id"]

    with pytest.warns(RuntimeWarning):
        observed = GovernedMem0(
            mem0, governance, tenant_id=TENANT, compatibility_mode="observe"
        ).search("legacy", user_id="customer-modes")
    assert [item["id"] for item in observed["results"]] == ["legacy-mode-id"]

    strict = GovernedMem0(mem0, governance, tenant_id=TENANT, compatibility_mode="strict")
    assert strict.search("legacy", user_id="customer-modes")["results"] == []
