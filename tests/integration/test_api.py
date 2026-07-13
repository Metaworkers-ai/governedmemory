"""
Integration tests for the E7 REST API (api/main.py) against a real
Postgres+pgvector instance, driven through actual HTTP calls via FastAPI's
TestClient rather than calling MemoryStore directly -- this is what proves
the routes, auth, and tenant isolation work end-to-end, not just that the
underlying store methods do (those are covered by test_memory_store.py).

Requires Docker (see tests/integration/conftest.py) -- skipped automatically
if unavailable.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

TENANT_A = "tenant-api-tests-a"
TENANT_B = "tenant-api-tests-b"
KEY_A = "test-key-a"
KEY_B = "test-key-b"


@pytest.fixture()
def client(migrated_dsn, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", migrated_dsn)
    monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", f"{TENANT_A}:{KEY_A},{TENANT_B}:{KEY_B}")

    from api.main import app

    with TestClient(app) as c:
        yield c


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _write_body(**overrides) -> dict:
    body = {
        "customer_id": "cust-1",
        "agent_id": "cx-1",
        "session_id": "s-1",
        "content": f"customer prefers email contact ({uuid.uuid4()})",
        "provenance": {"source_type": "user", "source_ref": "msg-1", "confidence": 0.9},
    }
    body.update(overrides)
    return body


class TestAuth:
    def test_missing_auth_header_is_401(self, client):
        resp = client.post("/v1/memory", json=_write_body())
        assert resp.status_code == 401

    def test_invalid_key_is_401(self, client):
        resp = client.post("/v1/memory", json=_write_body(), headers=_auth("not-a-real-key"))
        assert resp.status_code == 401

    def test_valid_key_is_accepted(self, client):
        resp = client.post("/v1/memory", json=_write_body(), headers=_auth(KEY_A))
        assert resp.status_code == 201


class TestWriteAndRetrieve:
    def test_write_returns_created_record(self, client):
        resp = client.post("/v1/memory", json=_write_body(), headers=_auth(KEY_A))
        assert resp.status_code == 201
        record = resp.json()
        assert record["tenant_id"] == TENANT_A
        assert record["customer_id"] == "cust-1"

    def test_write_ignores_client_supplied_tenant_id(self, client):
        """WriteBody has no tenant_id field at all, so even if a client tries
        to sneak one into the JSON body, pydantic drops it silently rather
        than it ever reaching the route handler -- this locks that in."""
        resp = client.post("/v1/memory", json=_write_body(tenant_id=TENANT_B), headers=_auth(KEY_A))
        assert resp.status_code == 201
        assert resp.json()["tenant_id"] == TENANT_A

    def test_retrieve_only_sees_own_tenants_memories(self, client):
        marker = str(uuid.uuid4())
        client.post(
            "/v1/memory",
            json=_write_body(content=f"tenant A's memory about a refund {marker}"),
            headers=_auth(KEY_A),
        )
        client.post(
            "/v1/memory",
            json=_write_body(content=f"tenant B's memory about a refund {marker}"),
            headers=_auth(KEY_B),
        )

        resp = client.post(
            "/v1/retrieve",
            json={"query": marker, "agent_id": "cx-1", "session_id": "s-1", "k": 10},
            headers=_auth(KEY_A),
        )
        assert resp.status_code == 200
        contents = [r["content"] for r in resp.json()]
        assert any("tenant A" in c for c in contents)
        assert all("tenant B" not in c for c in contents)


class TestQuarantineAndDelete:
    def test_quarantine_then_delete(self, client):
        write_resp = client.post("/v1/memory", json=_write_body(), headers=_auth(KEY_A))
        memory_id = write_resp.json()["id"]

        q_resp = client.post("/v1/quarantine", json={"memory_id": memory_id}, headers=_auth(KEY_A))
        assert q_resp.status_code == 200
        assert q_resp.json() == {"success": True}

        d_resp = client.delete(f"/v1/memory/{memory_id}", headers=_auth(KEY_A))
        assert d_resp.status_code == 200
        assert d_resp.json() == {"success": True}

    def test_delete_nonexistent_memory_is_404(self, client):
        resp = client.delete(
            "/v1/memory/00000000-0000-0000-0000-000000000000", headers=_auth(KEY_A)
        )
        assert resp.status_code == 404

    def test_cascade_delete_purges_descendants(self, client):
        marker = str(uuid.uuid4())
        customer_id = f"cust-cascade-{marker}"
        root_resp = client.post(
            "/v1/memory",
            json=_write_body(customer_id=customer_id, content=f"root {marker}"),
            headers=_auth(KEY_A),
        )
        root_id = root_resp.json()["id"]

        child_resp = client.post(
            "/v1/memory",
            json=_write_body(
                customer_id=customer_id,
                content=f"derived from root {marker}",
                provenance={
                    "source_type": "agent_derived",
                    "source_ref": "summarizer",
                    "confidence": 0.9,
                    "parent_ids": [root_id],
                },
            ),
            headers=_auth(KEY_A),
        )
        child_id = child_resp.json()["id"]

        preview_resp = client.get(f"/v1/memory/{root_id}/cascade-preview", headers=_auth(KEY_A))
        assert preview_resp.status_code == 200
        assert set(preview_resp.json()["descendant_ids"]) == {child_id}

        resp = client.delete(f"/v1/memory/{root_id}?cascade=true", headers=_auth(KEY_A))
        assert resp.status_code == 200
        assert resp.json() == {"success": True}

        # No GET /v1/memory/{id} route exists in this API -- verify both the
        # root and its descendant are actually gone via the listing endpoint.
        list_resp = client.get(f"/v1/memories?customer_id={customer_id}", headers=_auth(KEY_A))
        remaining_ids = {m["id"] for m in list_resp.json()}
        assert root_id not in remaining_ids
        assert child_id not in remaining_ids

    def test_cascade_delete_nonexistent_memory_is_404(self, client):
        resp = client.delete(
            "/v1/memory/00000000-0000-0000-0000-000000000000?cascade=true", headers=_auth(KEY_A)
        )
        assert resp.status_code == 404

    def test_cannot_quarantine_another_tenants_memory(self, client):
        write_resp = client.post("/v1/memory", json=_write_body(), headers=_auth(KEY_A))
        memory_id = write_resp.json()["id"]

        resp = client.post("/v1/quarantine", json={"memory_id": memory_id}, headers=_auth(KEY_B))
        assert resp.status_code == 404


class TestAudit:
    def test_audit_lists_events_for_the_authenticated_tenant_only(self, client):
        write_resp = client.post("/v1/memory", json=_write_body(), headers=_auth(KEY_A))
        memory_id = write_resp.json()["id"]

        resp = client.get("/v1/audit", headers=_auth(KEY_A))
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        assert any(memory_id in e["memory_ids"] for e in events)

        # list_audit() scopes by tenant_id inside the query itself (there's no
        # tenant_id column in the response -- every row it returns is already
        # guaranteed to belong to the caller's tenant), so isolation is
        # verified here by checking tenant B's audit log never mentions
        # tenant A's memory_id, rather than asserting a key that doesn't exist.
        other_resp = client.get("/v1/audit", headers=_auth(KEY_B))
        assert other_resp.status_code == 200
        assert all(memory_id not in e["memory_ids"] for e in other_resp.json())


class TestCustomersAndMemories:
    def test_list_customers_returns_only_the_authenticated_tenants_customers(self, client):
        marker = str(uuid.uuid4())
        client.post(
            "/v1/memory",
            json=_write_body(customer_id=f"cust-a-{marker}"),
            headers=_auth(KEY_A),
        )
        client.post(
            "/v1/memory",
            json=_write_body(customer_id=f"cust-b-{marker}"),
            headers=_auth(KEY_B),
        )

        resp = client.get("/v1/customers", headers=_auth(KEY_A))
        assert resp.status_code == 200
        customer_ids = [c["customer_id"] for c in resp.json()]
        assert f"cust-a-{marker}" in customer_ids
        assert f"cust-b-{marker}" not in customer_ids

    def test_list_customers_includes_memory_count(self, client):
        marker = str(uuid.uuid4())
        customer_id = f"cust-count-{marker}"
        client.post("/v1/memory", json=_write_body(customer_id=customer_id), headers=_auth(KEY_A))
        client.post("/v1/memory", json=_write_body(customer_id=customer_id), headers=_auth(KEY_A))

        resp = client.get("/v1/customers", headers=_auth(KEY_A))
        row = next(c for c in resp.json() if c["customer_id"] == customer_id)
        assert row["memory_count"] == 2

    def test_list_memories_returns_only_that_customers_memories(self, client):
        marker = str(uuid.uuid4())
        client.post(
            "/v1/memory",
            json=_write_body(customer_id=f"cust-x-{marker}", content=f"about x {marker}"),
            headers=_auth(KEY_A),
        )
        client.post(
            "/v1/memory",
            json=_write_body(customer_id=f"cust-y-{marker}", content=f"about y {marker}"),
            headers=_auth(KEY_A),
        )

        resp = client.get(f"/v1/memories?customer_id=cust-x-{marker}", headers=_auth(KEY_A))
        assert resp.status_code == 200
        contents = [m["content"] for m in resp.json()]
        assert any(f"about x {marker}" in c for c in contents)
        assert all(f"about y {marker}" not in c for c in contents)

    def test_list_memories_is_tenant_scoped(self, client):
        marker = str(uuid.uuid4())
        customer_id = f"cust-shared-{marker}"
        client.post(
            "/v1/memory",
            json=_write_body(customer_id=customer_id, content=f"tenant A only {marker}"),
            headers=_auth(KEY_A),
        )

        resp = client.get(f"/v1/memories?customer_id={customer_id}", headers=_auth(KEY_B))
        assert resp.status_code == 200
        assert resp.json() == []


class TestProvenance:
    def test_provenance_of_a_root_memory_is_empty(self, client):
        write_resp = client.post("/v1/memory", json=_write_body(), headers=_auth(KEY_A))
        memory_id = write_resp.json()["id"]

        resp = client.get(f"/v1/provenance/{memory_id}", headers=_auth(KEY_A))
        assert resp.status_code == 200
        assert resp.json() == {"memory_id": memory_id, "ancestors": [], "descendants": []}

    def test_provenance_reflects_parent_ids(self, client):
        marker = str(uuid.uuid4())
        root_resp = client.post(
            "/v1/memory",
            json=_write_body(content=f"root {marker}"),
            headers=_auth(KEY_A),
        )
        root_id = root_resp.json()["id"]

        child_resp = client.post(
            "/v1/memory",
            json=_write_body(
                content=f"derived from root {marker}",
                provenance={
                    "source_type": "agent_derived",
                    "source_ref": "summarizer",
                    "confidence": 0.9,
                    "parent_ids": [root_id],
                },
            ),
            headers=_auth(KEY_A),
        )
        child_id = child_resp.json()["id"]

        root_provenance = client.get(f"/v1/provenance/{root_id}", headers=_auth(KEY_A)).json()
        assert root_provenance["ancestors"] == []
        assert root_provenance["descendants"] == [child_id]

        child_provenance = client.get(f"/v1/provenance/{child_id}", headers=_auth(KEY_A)).json()
        assert child_provenance["ancestors"] == [root_id]
        assert child_provenance["descendants"] == []


def test_healthz_needs_no_auth(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

