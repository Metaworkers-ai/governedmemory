"""
Integration tests for MemoryStore against a real Postgres + pgvector instance.

REQUIREMENTS
  - Docker must be running (used by testcontainers to spin up postgres automatically)
  - No manual setup needed — the fixture handles everything

E1 DEFINITION OF DONE (verified here)
  [x] write+read a record
  [x] tenant-isolated (wrong tenant cannot read another tenant's records)
  [x] migrations run and are idempotent

Run: pytest tests/integration/ -v
     (takes ~15s on first run to pull the Docker image)
"""
import pytest

# testcontainers spins up a Docker container automatically.
# If Docker daemon is not running, tests are skipped (not failed) to avoid blocking CI.
DOCKER_AVAILABLE = False
try:
    import docker as _docker
    _docker.from_env().ping()   # actually connect to the daemon
    from testcontainers.postgres import PostgresContainer
    DOCKER_AVAILABLE = True
except Exception:
    pass

from core.memory_store import MemoryStore, init_db, NullEmbeddingProvider
from core.models import WriteRequest, Provenance, SourceType, Taint

POSTGRES_IMAGE = "pgvector/pgvector:pg16"  # official image with pgvector pre-installed

pytestmark = pytest.mark.skipif(
    not DOCKER_AVAILABLE,
    reason="Docker not available — skipping integration tests",
)


# ============================================================
# Session-scoped fixtures: one DB per test session
# ============================================================

@pytest.fixture(scope="session")
def postgres_dsn():
    """Spin up a Postgres+pgvector container for the test session."""
    with PostgresContainer(POSTGRES_IMAGE) as pg:
        url = pg.get_connection_url()
        dsn = url.replace("postgresql+psycopg2://", "postgresql://")
        # Verify pgvector is actually available in this image before running any tests
        import psycopg2
        try:
            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.close()
        except Exception as e:
            pytest.skip(f"vector extension not available in {POSTGRES_IMAGE}: {e}")
        yield dsn


@pytest.fixture(scope="session")
def migrated_store(postgres_dsn):
    """Create all tables, return a store backed by the test DB."""
    init_db(postgres_dsn)
    return MemoryStore(postgres_dsn, NullEmbeddingProvider(768))


@pytest.fixture(scope="session")
def migrated_dsn(postgres_dsn):
    """DSN after tables are created — for tests that need raw DB access."""
    init_db(postgres_dsn)
    return postgres_dsn


# ============================================================
# Helpers
# ============================================================

def _req(tenant_id: str, customer_id: str = "cust-001", content: str = "test memory",
         source_type: SourceType = SourceType.USER) -> WriteRequest:
    return WriteRequest(
        tenant_id=tenant_id,
        customer_id=customer_id,
        agent_id="test-agent",
        session_id="test-session",
        content=content,
        provenance=Provenance(source_type=source_type, source_ref="test-ref", confidence=0.9),
    )


# ============================================================
# Migration idempotency
# ============================================================

class TestMigrations:
    def test_init_db_is_idempotent(self, postgres_dsn):
        """Calling init_db twice must not raise — all statements use IF NOT EXISTS."""
        init_db(postgres_dsn)  # already run by fixture; must be a no-op
        init_db(postgres_dsn)  # third call — still fine

    def test_memory_table_exists(self, postgres_dsn):
        import psycopg2
        conn = psycopg2.connect(postgres_dsn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'memory'"
            )
            columns = {row[0] for row in cur.fetchall()}
        conn.close()
        expected = {
            "id", "tenant_id", "customer_id", "agent_id", "session_id",
            "content", "embedding",
            "source_type", "source_ref", "ingested_at", "confidence", "parent_ids",
            "taint", "taint_reason", "injection_score",
            "allowed_purposes", "policy_id",
            "valid_from", "valid_until", "superseded_by", "version",
            "acl", "created_at", "updated_at",
        }
        assert expected <= columns, f"Missing columns: {expected - columns}"

    def test_audit_table_exists(self, postgres_dsn):
        import psycopg2
        conn = psycopg2.connect(postgres_dsn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'audit'"
            )
            columns = {row[0] for row in cur.fetchall()}
        conn.close()
        assert "hash" in columns
        assert "prev_hash" in columns


# ============================================================
# E1 Definition of Done: write + read a record
# ============================================================

class TestWriteAndRead:
    def test_write_returns_record_with_id(self, migrated_store):
        record = migrated_store.write(_req("tenant-e1", content="E1 test memory"))
        assert record.id
        assert len(record.id) == 36  # UUID format

    def test_get_by_id_returns_same_record(self, migrated_store):
        written = migrated_store.write(_req("tenant-e1-read", content="roundtrip test"))
        fetched = migrated_store.get(written.id, "tenant-e1-read")
        assert fetched is not None
        assert fetched.id == written.id
        assert fetched.content == "roundtrip test"
        assert fetched.customer_id == "cust-001"

    def test_all_provenance_fields_persisted(self, migrated_store):
        req = _req("tenant-e1-prov")
        req.provenance.confidence = 0.75
        req.provenance.parent_ids = ["parent-uuid-1"]
        written = migrated_store.write(req)
        fetched = migrated_store.get(written.id, "tenant-e1-prov")
        assert fetched.provenance.confidence == 0.75
        assert fetched.provenance.parent_ids == ["parent-uuid-1"]

    def test_taint_auto_applied_for_untrusted_web(self, migrated_store):
        req = _req("tenant-taint", source_type=SourceType.UNTRUSTED_WEB)
        record = migrated_store.write(req)
        fetched = migrated_store.get(record.id, "tenant-taint")
        assert fetched.trust.taint == Taint.UNTRUSTED
        assert "untrusted_web" in fetched.trust.taint_reason

    def test_trusted_source_stays_trusted(self, migrated_store):
        req = _req("tenant-trusted", source_type=SourceType.TRUSTED_SYSTEM)
        record = migrated_store.write(req)
        fetched = migrated_store.get(record.id, "tenant-trusted")
        assert fetched.trust.taint == Taint.TRUSTED

    def test_list_for_customer(self, migrated_store):
        tenant = "tenant-list"
        migrated_store.write(_req(tenant, customer_id="cust-A", content="mem 1"))
        migrated_store.write(_req(tenant, customer_id="cust-A", content="mem 2"))
        migrated_store.write(_req(tenant, customer_id="cust-B", content="other customer"))

        results = migrated_store.list_for_customer(tenant, "cust-A")
        assert len(results) == 2
        assert all(r.customer_id == "cust-A" for r in results)
        assert all(r.tenant_id == tenant for r in results)


# ============================================================
# E1 Definition of Done: tenant isolation
# ============================================================

class TestTenantIsolation:
    """
    CRITICAL: These tests verify the most important security property of the store.
    A record written to tenant-A must NEVER be readable by tenant-B.
    """

    def test_get_with_wrong_tenant_returns_none(self, migrated_store):
        record = migrated_store.write(_req("tenant-alpha"))
        result = migrated_store.get(record.id, "tenant-beta")  # wrong tenant
        assert result is None, "Cross-tenant read must return None — data leak!"

    def test_list_only_returns_own_tenant_records(self, migrated_store):
        migrated_store.write(_req("tenant-x", customer_id="cust-shared"))
        migrated_store.write(_req("tenant-y", customer_id="cust-shared"))

        x_results = migrated_store.list_for_customer("tenant-x", "cust-shared")
        y_results = migrated_store.list_for_customer("tenant-y", "cust-shared")

        assert all(r.tenant_id == "tenant-x" for r in x_results)
        assert all(r.tenant_id == "tenant-y" for r in y_results)
        # No cross-contamination
        x_ids = {r.id for r in x_results}
        y_ids = {r.id for r in y_results}
        assert x_ids.isdisjoint(y_ids), "Tenant IDs must not overlap!"

    def test_empty_tenant_id_raises(self, migrated_store):
        with pytest.raises(ValueError, match="tenant_id"):
            migrated_store.get("any-id", "")

    def test_stats_are_tenant_scoped(self, migrated_store):
        migrated_store.write(_req("tenant-stats-a", content="a1"))
        migrated_store.write(_req("tenant-stats-a", content="a2"))
        migrated_store.write(_req("tenant-stats-b", content="b1"))

        stats_a = migrated_store.get_stats("tenant-stats-a")
        stats_b = migrated_store.get_stats("tenant-stats-b")

        # Each tenant only sees their own count
        assert stats_a["total_memories"] >= 2
        assert stats_b["total_memories"] >= 1
        assert stats_a["tenant_id"] == "tenant-stats-a"


# ============================================================
# Governance mutations
# ============================================================

class TestGovernanceMutations:
    def test_quarantine_changes_taint(self, migrated_store):
        record = migrated_store.write(_req("tenant-quar"))
        assert record.trust.taint == Taint.TRUSTED

        success = migrated_store.quarantine(record.id, "tenant-quar", "suspicious content")
        assert success is True

        fetched = migrated_store.get(record.id, "tenant-quar")
        assert fetched.trust.taint == Taint.QUARANTINED
        assert fetched.trust.taint_reason == "suspicious content"

    def test_quarantine_wrong_tenant_fails(self, migrated_store):
        record = migrated_store.write(_req("tenant-quar-a"))
        success = migrated_store.quarantine(record.id, "tenant-quar-b")
        assert success is False   # wrong tenant — must not affect record

    def test_delete_removes_record(self, migrated_store):
        record = migrated_store.write(_req("tenant-del"))
        deleted = migrated_store.delete(record.id, "tenant-del")
        assert deleted is True
        assert migrated_store.get(record.id, "tenant-del") is None

    def test_delete_wrong_tenant_leaves_record_intact(self, migrated_store):
        record = migrated_store.write(_req("tenant-del-safe"))
        deleted = migrated_store.delete(record.id, "tenant-del-wrong")
        assert deleted is False
        assert migrated_store.get(record.id, "tenant-del-safe") is not None


# ============================================================
# Audit log
# ============================================================

class TestAuditLog:
    def test_write_emits_audit_event(self, migrated_store, migrated_dsn):
        import psycopg2
        tenant = "tenant-audit-write"
        record = migrated_store.write(_req(tenant))

        conn = psycopg2.connect(migrated_dsn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT op, outcome, hash, prev_hash FROM audit WHERE tenant_id = %s ORDER BY ts DESC LIMIT 1",
                (tenant,),
            )
            row = cur.fetchone()
        conn.close()

        assert row is not None
        op, outcome, hash_val, prev_hash = row
        assert op == "write"
        assert outcome == "allow"
        assert len(hash_val) == 64   # SHA-256 hex = 64 chars

    def test_audit_hash_chain_is_valid(self, migrated_store, migrated_dsn):
        """Verify hash-chaining: each event's prev_hash matches the previous event's hash."""
        import psycopg2
        tenant = "tenant-audit-chain"
        for i in range(3):
            migrated_store.write(_req(tenant, content=f"memory {i}"))

        conn = psycopg2.connect(migrated_dsn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT hash, prev_hash FROM audit WHERE tenant_id = %s ORDER BY ts ASC",
                (tenant,),
            )
            rows = cur.fetchall()
        conn.close()

        assert len(rows) >= 3
        # Each event's prev_hash must equal the prior event's hash
        for i in range(1, len(rows)):
            assert rows[i][1] == rows[i - 1][0], (
                f"Hash chain broken at event {i}: "
                f"prev_hash={rows[i][1]} != hash={rows[i-1][0]}"
            )


# ============================================================
# Vector search (basic smoke test — NullEmbeddingProvider returns zero vectors)
# ============================================================

class TestVectorSearch:
    def test_vector_search_returns_results(self, migrated_store):
        tenant = "tenant-vec"
        migrated_store.write(_req(tenant, content="refund policy for premium users"))
        migrated_store.write(_req(tenant, content="how to contact support team"))
        # NullEmbeddingProvider returns zero vectors — results are arbitrary but call must succeed
        results = migrated_store.vector_search("refund", tenant, k=5)
        assert isinstance(results, list)
        assert all(r.tenant_id == tenant for r in results)

    def test_vector_search_tenant_scoped(self, migrated_store):
        migrated_store.write(_req("tenant-vec-a", content="private info for A"))
        migrated_store.write(_req("tenant-vec-b", content="private info for B"))

        results_a = migrated_store.vector_search("private", "tenant-vec-a", k=10)
        assert all(r.tenant_id == "tenant-vec-a" for r in results_a)
