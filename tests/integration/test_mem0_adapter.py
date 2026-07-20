"""Docker-backed integration for the synchronous Mem0 adapter."""

from __future__ import annotations

import threading
import time

import pytest
import uvicorn
from metaworkers import GovernanceDenied, GovernedMemory, Source
from metaworkers.adapters.mem0 import GovernedMem0

TENANT = "tenant-mem0-adapter"
API_KEY = "mem0-adapter-key"


class DeterministicMem0:
    def __init__(self):
        self.records = []
        self.calls = 0

    def add(self, messages, **kwargs):
        self.calls += 1
        content = messages if isinstance(messages, str) else str(messages)
        memory_id = f"mem0-{self.calls}"
        self.records.append({"id": memory_id, "memory": content})
        return {"results": [{"id": memory_id, "memory": content}]}

    def search(self, query, **kwargs):
        return {"results": list(self.records)}


@pytest.fixture()
def live_server_url(migrated_dsn, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", migrated_dsn)
    monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", f"{TENANT}:{API_KEY}")
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
    assert mem0.calls == 2

    governed_results = adapter.search("customer", user_id="customer-1")
    assert [r["id"] for r in governed_results["results"]] == ["mem0-1"]

    adapter.quarantine("mem0-1", "manual review")
    assert adapter.search("customer", user_id="customer-1")["results"] == []
    metadata = adapter.get_governance("mem0-1")
    assert metadata["lifecycle_state"] == "quarantined"


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
