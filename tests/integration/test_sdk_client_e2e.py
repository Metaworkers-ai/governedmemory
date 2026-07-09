"""
End-to-end test for the thin SDK client (sdk/python/metaworkers) against a
REAL running server -- a live uvicorn instance bound to an actual TCP
socket, not the in-process ASGI transport tests/integration/test_api.py
uses. This is the one thing nothing else in the suite proves: that
metaworkers.GovernedMemory (built on urllib.request) can actually talk
over a real socket to api.main:app and back.

Every route/behavior is already covered by test_api.py (server side) and
tests/unit/test_sdk_client.py (client request/response logic, mocked) --
this file stays deliberately small.
"""

from __future__ import annotations

import threading
import time
import uuid

import pytest
import uvicorn
from metaworkers import GovernedMemory, GovernedMemoryError, Source

TENANT = "tenant-sdk-e2e"
API_KEY = "sdk-e2e-test-key"


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
    assert server.started, "uvicorn server did not start within 10s"

    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


def test_write_then_retrieve_over_a_real_socket(live_server_url):
    mem = GovernedMemory(base_url=live_server_url, api_key=API_KEY)
    marker = str(uuid.uuid4())

    record = mem.write(
        customer_id="cust-1",
        agent_id="cx-1",
        session_id="s-1",
        content=f"customer prefers email contact {marker}",
        source=Source(type="user", ref="msg-1", confidence=0.9),
    )
    assert record["tenant_id"] == TENANT
    assert marker in record["content"]

    results = mem.retrieve(query=marker, agent_id="cx-1", session_id="s-1", k=5)
    assert any(marker in r["content"] for r in results)


def test_wrong_api_key_raises_governedmemoryerror(live_server_url):
    mem = GovernedMemory(base_url=live_server_url, api_key="not-the-real-key")
    with pytest.raises(GovernedMemoryError) as exc_info:
        mem.audit()
    assert exc_info.value.status_code == 401
