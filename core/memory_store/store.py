"""
MemoryStore — Postgres + pgvector backend.

Cloud-agnostic: the only external dependency is a Postgres DSN (DATABASE_URL).
Works on local Docker, AWS RDS, GCP Cloud SQL, Azure Postgres, Supabase, Neon.

GETTING STARTED
    from core.memory_store import MemoryStore, SentenceTransformerProvider, init_db

    dsn = os.environ["DATABASE_URL"]
    init_db(dsn)                              # create tables (safe to call multiple times)
    store = MemoryStore(dsn, SentenceTransformerProvider())
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, List, Optional

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from core.models.memory_record import (
    Access, MemoryRecord, Provenance, Purpose, SourceType,
    Taint, Temporal, Trust, WriteRequest,
)
from core.models.audit_event import AuditActor, AuditDecision, AuditOp, AuditOutcome
from core.memory_store.embeddings import EmbeddingProvider
from core.write_governor import scan_for_injection, find_duplicate

_UNTRUSTED_SOURCE_TYPES = {SourceType.UNTRUSTED_WEB, SourceType.UNTRUSTED_EMAIL}
_INJECTION_THRESHOLD = float(os.getenv("INJECTION_THRESHOLD", "0.7"))


# ---------------------------------------------------------------------------
# Schema — all tables defined here, no separate migration files
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS memory (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       TEXT        NOT NULL,
    customer_id     TEXT        NOT NULL,
    agent_id        TEXT        NOT NULL,
    session_id      TEXT        NOT NULL,
    content         TEXT        NOT NULL,
    embedding       vector(768),

    -- provenance
    source_type     TEXT        NOT NULL,
    source_ref      TEXT        NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confidence      REAL        NOT NULL DEFAULT 1.0
                                CHECK (confidence >= 0.0 AND confidence <= 1.0),
    parent_ids      JSONB       NOT NULL DEFAULT '[]',

    -- trust
    taint           TEXT        NOT NULL DEFAULT 'trusted'
                                CHECK (taint IN ('trusted', 'untrusted', 'quarantined')),
    taint_reason    TEXT,
    injection_score REAL        NOT NULL DEFAULT 0.0
                                CHECK (injection_score >= 0.0 AND injection_score <= 1.0),

    -- purpose
    allowed_purposes JSONB      NOT NULL DEFAULT '[]',
    policy_id       TEXT        NOT NULL DEFAULT 'default',

    -- temporal
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until     TIMESTAMPTZ,
    superseded_by   UUID        REFERENCES memory(id) ON DELETE SET NULL,
    version         INTEGER     NOT NULL DEFAULT 1,

    -- access
    acl             JSONB       NOT NULL DEFAULT '[]',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_tenant_customer ON memory (tenant_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_memory_fts ON memory USING GIN (to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS idx_memory_embedding ON memory
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE IF NOT EXISTS audit (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   TEXT        NOT NULL,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id    TEXT        NOT NULL,
    session_id  TEXT        NOT NULL,
    op          TEXT        NOT NULL
                CHECK (op IN ('write', 'retrieve', 'quarantine', 'purge', 'policy_decision')),
    memory_ids  JSONB       NOT NULL DEFAULT '[]',
    outcome     TEXT        NOT NULL CHECK (outcome IN ('allow', 'deny', 'gated')),
    reason      TEXT        NOT NULL,
    policy_id   TEXT        NOT NULL DEFAULT 'default',
    hash        TEXT        NOT NULL,
    prev_hash   TEXT        NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant_ts ON audit (tenant_id, ts DESC);

CREATE TABLE IF NOT EXISTS policy (
    id               TEXT        NOT NULL,
    tenant_id        TEXT        NOT NULL,
    purpose_bindings JSONB       NOT NULL DEFAULT '[]',
    privilege_rules  JSONB       NOT NULL DEFAULT '{}',
    rbac             JSONB       NOT NULL DEFAULT '[]',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, tenant_id)
);

CREATE OR REPLACE FUNCTION _set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

DROP TRIGGER IF EXISTS memory_updated_at ON memory;
CREATE TRIGGER memory_updated_at
    BEFORE UPDATE ON memory FOR EACH ROW EXECUTE FUNCTION _set_updated_at();
"""


def init_db(dsn: str) -> None:
    """
    Create all tables and indexes. Safe to call multiple times — uses IF NOT EXISTS.
    Call this once at app startup before creating a MemoryStore.

        init_db(os.environ["DATABASE_URL"])
    """
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(_SCHEMA_SQL)
    conn.close()


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def _require_tenant(tenant_id: str) -> None:
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id must not be empty — every operation is tenant-scoped")


class MemoryStore:
    """
    All persistence operations for governed memory.

    Usage:
        init_db(dsn)
        store = MemoryStore(dsn, SentenceTransformerProvider())
        record = store.write(WriteRequest(...))
    """

    def __init__(self, dsn: str, embedding_provider: EmbeddingProvider) -> None:
        self._dsn = dsn
        self._embedder = embedding_provider

    @contextmanager
    def _conn(self) -> Generator[psycopg2.extensions.connection, None, None]:
        conn = psycopg2.connect(self._dsn)
        psycopg2.extras.register_uuid(conn)
        register_vector(conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self, req: WriteRequest) -> MemoryRecord:
        """
        Persist a new memory through the Write Governor pipeline (E2):
        provenance -> taint -> injection scan -> dedup -> embed -> persist.
        """
        _require_tenant(req.tenant_id)

        injection_score, injection_labels = scan_for_injection(req.content)
        source_untrusted = req.provenance.source_type in _UNTRUSTED_SOURCE_TYPES
        injection_flagged = injection_score >= _INJECTION_THRESHOLD

        if source_untrusted or injection_flagged:
            reasons = []
            if source_untrusted:
                reasons.append(f"source_type={req.provenance.source_type.value}")
            if injection_flagged:
                reasons.append(f"injection_score={injection_score:.2f} ({'/'.join(injection_labels)})")
            trust = Trust(taint=Taint.UNTRUSTED, taint_reason="; ".join(reasons),
                          injection_score=injection_score)
        else:
            trust = Trust(taint=Taint.TRUSTED, injection_score=injection_score)

        embedding = self._embedder.embed(req.content)

        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Dedup: does this customer already have this exact (normalized) content?
                cur.execute(
                    """SELECT id, content, version, superseded_by FROM memory
                       WHERE tenant_id = %s AND customer_id = %s AND superseded_by IS NULL
                       ORDER BY created_at DESC""",
                    (req.tenant_id, req.customer_id),
                )
                duplicate = find_duplicate(cur.fetchall(), req.content)

                temporal = req.temporal.model_copy(
                    update={"version": duplicate["version"] + 1} if duplicate else {}
                )
                record = MemoryRecord(
                    tenant_id=req.tenant_id,
                    customer_id=req.customer_id,
                    agent_id=req.agent_id,
                    session_id=req.session_id,
                    content=req.content,
                    provenance=req.provenance,
                    trust=trust,
                    purpose=req.purpose,
                    temporal=temporal,
                    access=req.access,
                )

                cur.execute(
                    """
                    INSERT INTO memory (
                        id, tenant_id, customer_id, agent_id, session_id,
                        content, embedding,
                        source_type, source_ref, ingested_at, confidence, parent_ids,
                        taint, taint_reason, injection_score,
                        allowed_purposes, policy_id,
                        valid_from, valid_until, superseded_by, version,
                        acl, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,  %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,  %s, %s,
                        %s, %s, %s, %s,  %s, %s, %s
                    )
                    """,
                    (
                        record.id, record.tenant_id, record.customer_id,
                        record.agent_id, record.session_id,
                        record.content, embedding,
                        record.provenance.source_type.value, record.provenance.source_ref,
                        record.provenance.ingested_at, record.provenance.confidence,
                        json.dumps(record.provenance.parent_ids),
                        record.trust.taint.value, record.trust.taint_reason,
                        record.trust.injection_score,
                        json.dumps(record.purpose.allowed_purposes), record.purpose.policy_id,
                        record.temporal.valid_from, record.temporal.valid_until,
                        record.temporal.superseded_by, record.temporal.version,
                        json.dumps(record.access.acl),
                        record.created_at, record.updated_at,
                    ),
                )

                if duplicate:
                    cur.execute(
                        "UPDATE memory SET superseded_by = %s WHERE id = %s",
                        (record.id, duplicate["id"]),
                    )

        reason = "write accepted"
        if duplicate:
            reason += f"; supersedes {duplicate['id']}"
        self._audit(record.tenant_id, record.agent_id, record.session_id,
                    AuditOp.WRITE, [record.id],
                    AuditDecision(outcome=AuditOutcome.ALLOW, reason=reason,
                                  policy_id=record.purpose.policy_id))
        return record

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, memory_id: str, tenant_id: str) -> Optional[MemoryRecord]:
        """Fetch one record by ID. Returns None if not found or wrong tenant."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM memory WHERE id = %s AND tenant_id = %s",
                    (memory_id, tenant_id),
                )
                row = cur.fetchone()
        return _row_to_record(row) if row else None

    def list_for_customer(self, tenant_id: str, customer_id: str) -> List[MemoryRecord]:
        """All memories for a customer within a tenant, newest first."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT * FROM memory WHERE tenant_id = %s AND customer_id = %s
                       ORDER BY created_at DESC""",
                    (tenant_id, customer_id),
                )
                rows = cur.fetchall()
        return [_row_to_record(r) for r in rows]

    def list_customers(self, tenant_id: str) -> List[dict]:
        """Distinct customers for a tenant, with memory counts — for navigation UIs."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT customer_id, COUNT(*) AS memory_count, MAX(created_at) AS last_activity
                       FROM memory WHERE tenant_id = %s
                       GROUP BY customer_id ORDER BY last_activity DESC""",
                    (tenant_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def vector_search(self, query: str, tenant_id: str, k: int = 10) -> List[MemoryRecord]:
        """Semantic similarity search — cosine distance via pgvector."""
        _require_tenant(tenant_id)
        embedding = self._embedder.embed(query)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SET ivfflat.probes = 10")
                cur.execute(
                    """SELECT * FROM memory
                       WHERE tenant_id = %s
                         AND (valid_until IS NULL OR valid_until > NOW())
                         AND superseded_by IS NULL
                         AND embedding IS NOT NULL
                       ORDER BY embedding <=> %s::vector
                       LIMIT %s""",
                    (tenant_id, embedding, k),
                )
                rows = cur.fetchall()
        return [_row_to_record(r) for r in rows]

    def lexical_search(self, query: str, tenant_id: str, k: int = 10) -> List[MemoryRecord]:
        """Full-text search via Postgres tsvector (lexical leg of hybrid retrieval)."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT * FROM memory
                       WHERE tenant_id = %s
                         AND (valid_until IS NULL OR valid_until > NOW())
                         AND superseded_by IS NULL
                         AND to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                       ORDER BY ts_rank(to_tsvector('english', content),
                                        plainto_tsquery('english', %s)) DESC
                       LIMIT %s""",
                    (tenant_id, query, query, k),
                )
                rows = cur.fetchall()
        return [_row_to_record(r) for r in rows]

    # ------------------------------------------------------------------
    # Governance mutations
    # ------------------------------------------------------------------

    def quarantine(self, memory_id: str, tenant_id: str,
                   reason: str = "manual quarantine") -> bool:
        """Mark a memory as quarantined — blocked by the privilege gate on retrieval."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE memory SET taint = 'quarantined', taint_reason = %s
                       WHERE id = %s AND tenant_id = %s""",
                    (reason, memory_id, tenant_id),
                )
                updated = cur.rowcount > 0
        if updated:
            self._audit(tenant_id, "system", "system", AuditOp.QUARANTINE, [memory_id],
                        AuditDecision(outcome=AuditOutcome.ALLOW, reason=reason))
        return updated

    def delete(self, memory_id: str, tenant_id: str) -> bool:
        """Hard-delete a memory (GDPR right-to-erasure). Cascade purge added in E6."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM memory WHERE id = %s AND tenant_id = %s",
                    (memory_id, tenant_id),
                )
                deleted = cur.rowcount > 0
        if deleted:
            self._audit(tenant_id, "system", "system", AuditOp.PURGE, [memory_id],
                        AuditDecision(outcome=AuditOutcome.ALLOW, reason="hard delete"))
        return deleted

    def get_stats(self, tenant_id: str) -> dict:
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM memory WHERE tenant_id = %s", (tenant_id,))
                total = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(DISTINCT customer_id) FROM memory WHERE tenant_id = %s",
                    (tenant_id,),
                )
                customers = cur.fetchone()[0]
        return {"tenant_id": tenant_id, "total_memories": total, "total_customers": customers}

    # ------------------------------------------------------------------
    # Audit (hash-chained, append-only)
    # ------------------------------------------------------------------

    def list_audit(self, tenant_id: str, limit: int = 50) -> List[dict]:
        """Recent audit events for a tenant, newest first — for inspection/debugging."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT id, ts, agent_id, session_id, op, memory_ids,
                              outcome, reason, policy_id, hash, prev_hash
                       FROM audit WHERE tenant_id = %s
                       ORDER BY ts DESC LIMIT %s""",
                    (tenant_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def _audit(self, tenant_id: str, agent_id: str, session_id: str,
               op: AuditOp, memory_ids: List[str], decision: AuditDecision) -> None:
        conn = psycopg2.connect(self._dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT hash FROM audit WHERE tenant_id = %s ORDER BY ts DESC LIMIT 1",
                    (tenant_id,),
                )
                row = cur.fetchone()
                prev_hash = row[0] if row else ""

                event_id = str(uuid.uuid4())
                ts = datetime.now(timezone.utc).isoformat()
                payload = f"{event_id}{tenant_id}{ts}{op.value}{json.dumps(sorted(memory_ids))}{decision.outcome.value}"
                current_hash = hashlib.sha256((prev_hash + payload).encode()).hexdigest()

                cur.execute(
                    """INSERT INTO audit (id, tenant_id, ts, agent_id, session_id, op,
                                          memory_ids, outcome, reason, policy_id, hash, prev_hash)
                       VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (event_id, tenant_id, agent_id, session_id, op.value,
                     json.dumps(memory_ids), decision.outcome.value,
                     decision.reason, decision.policy_id, current_hash, prev_hash),
                )
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Internal: row → model
# ---------------------------------------------------------------------------

def _row_to_record(row: dict) -> MemoryRecord:
    def _list(v) -> list:
        return v if isinstance(v, list) else json.loads(v)

    return MemoryRecord(
        id=str(row["id"]),
        tenant_id=row["tenant_id"],
        customer_id=row["customer_id"],
        agent_id=row["agent_id"],
        session_id=row["session_id"],
        content=row["content"],
        provenance=Provenance(
            source_type=SourceType(row["source_type"]),
            source_ref=row["source_ref"],
            ingested_at=row["ingested_at"],
            confidence=row["confidence"],
            parent_ids=_list(row["parent_ids"]),
        ),
        trust=Trust(
            taint=Taint(row["taint"]),
            taint_reason=row["taint_reason"],
            injection_score=row["injection_score"],
        ),
        purpose=Purpose(
            allowed_purposes=_list(row["allowed_purposes"]),
            policy_id=row["policy_id"],
        ),
        temporal=Temporal(
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
            superseded_by=str(row["superseded_by"]) if row["superseded_by"] else None,
            version=row["version"],
        ),
        access=Access(acl=_list(row["acl"])),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
