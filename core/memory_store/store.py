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
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from core.audit import (
    AuditVerificationResult,
    CascadePurgePlan,
    ProvenanceGraph,
    build_provenance_graph,
    plan_cascade_purge,
    verify_chain,
)
from core.detection import score_injection
from core.memory_store.embeddings import EmbeddingProvider
from core.models.audit_event import AuditDecision, AuditOp, AuditOutcome
from core.models.memory_record import (
    Access,
    MemoryRecord,
    Provenance,
    Purpose,
    SourceType,
    Taint,
    Temporal,
    Trust,
    WriteRequest,
)
from core.models.policy import Policy, PrivilegeRules, PurposeBinding
from core.policy_engine import evaluate_privileged_action, filter_by_purpose_binding
from core.retrieval_engine import apply_privilege_gate, reciprocal_rank_fusion
from core.write_governor import find_duplicate

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

DROP TRIGGER IF EXISTS policy_updated_at ON policy;
CREATE TRIGGER policy_updated_at
    BEFORE UPDATE ON policy FOR EACH ROW EXECUTE FUNCTION _set_updated_at();
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


def _jsonb_list(v) -> list:
    return v if isinstance(v, list) else json.loads(v)


def _jsonb_dict(v) -> dict:
    return v if isinstance(v, dict) else json.loads(v)


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

        The injection scan itself is E5-pluggable: `score_injection()`
        defaults to E2's heuristic regex scanner but can be switched to a
        trained classifier (or an ensemble of both) via the
        DETECTION_BACKEND env var — see core/detection/scanner.py.
        """
        _require_tenant(req.tenant_id)

        injection_score, injection_labels = score_injection(req.content)
        source_untrusted = req.provenance.source_type in _UNTRUSTED_SOURCE_TYPES
        injection_flagged = injection_score >= _INJECTION_THRESHOLD

        if source_untrusted or injection_flagged:
            reasons = []
            if source_untrusted:
                reasons.append(f"source_type={req.provenance.source_type.value}")
            if injection_flagged:
                reasons.append(
                    f"injection_score={injection_score:.2f} ({'/'.join(injection_labels)})"
                )
            trust = Trust(
                taint=Taint.UNTRUSTED,
                taint_reason="; ".join(reasons),
                injection_score=injection_score,
            )
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
                        record.id,
                        record.tenant_id,
                        record.customer_id,
                        record.agent_id,
                        record.session_id,
                        record.content,
                        embedding,
                        record.provenance.source_type.value,
                        record.provenance.source_ref,
                        record.provenance.ingested_at,
                        record.provenance.confidence,
                        json.dumps(record.provenance.parent_ids),
                        record.trust.taint.value,
                        record.trust.taint_reason,
                        record.trust.injection_score,
                        json.dumps(record.purpose.allowed_purposes),
                        record.purpose.policy_id,
                        record.temporal.valid_from,
                        record.temporal.valid_until,
                        record.temporal.superseded_by,
                        record.temporal.version,
                        json.dumps(record.access.acl),
                        record.created_at,
                        record.updated_at,
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
        self._audit(
            record.tenant_id,
            record.agent_id,
            record.session_id,
            AuditOp.WRITE,
            [record.id],
            AuditDecision(
                outcome=AuditOutcome.ALLOW, reason=reason, policy_id=record.purpose.policy_id
            ),
        )
        return record

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, memory_id: str, tenant_id: str) -> MemoryRecord | None:
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

    def list_for_customer(self, tenant_id: str, customer_id: str) -> list[MemoryRecord]:
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

    def list_customers(self, tenant_id: str) -> list[dict]:
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

    def vector_search(self, query: str, tenant_id: str, k: int = 10) -> list[MemoryRecord]:
        """
        Semantic similarity search — cosine distance via pgvector.

        Raw primitive: does NOT apply the privilege gate (taint/purpose
        filtering) or emit an audit event. Use retrieve() for governed,
        audited retrieval — this exists for direct inspection/debugging
        and as a building block retrieve() calls internally.
        """
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

    def lexical_search(self, query: str, tenant_id: str, k: int = 10) -> list[MemoryRecord]:
        """
        Full-text search via Postgres tsvector.

        Raw primitive: does NOT apply the privilege gate (taint/purpose
        filtering) or emit an audit event — same caveat as vector_search().
        """
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

    def retrieve(
        self,
        query: str,
        tenant_id: str,
        agent_id: str,
        session_id: str,
        purpose: str | None = None,
        k: int = 10,
        include_untrusted: bool = False,
    ) -> list[MemoryRecord]:
        """
        Governed hybrid retrieval — the Retrieval Engine (E3).

        This is the entry point agents should use, not vector_search()/
        lexical_search() directly. Combines both via reciprocal rank fusion,
        applies the privilege gate (taint + purpose-binding filtering), and
        emits an audit event either way — so "who read what, for what
        purpose, and was anything filtered out" is always answerable.
        """
        _require_tenant(tenant_id)

        # Over-fetch before gating so filtering doesn't starve the final k.
        fetch_k = max(k * 3, 20)
        vector_results = self.vector_search(query, tenant_id, k=fetch_k)
        lexical_results = self.lexical_search(query, tenant_id, k=fetch_k)

        fused_scores = reciprocal_rank_fusion(
            [
                [r.id for r in vector_results],
                [r.id for r in lexical_results],
            ]
        )
        by_id = {r.id: r for r in vector_results + lexical_results}
        ranked = [by_id[i] for i in sorted(fused_scores, key=fused_scores.get, reverse=True)]

        gated = apply_privilege_gate(ranked, purpose=purpose, include_untrusted=include_untrusted)
        gated = filter_by_purpose_binding(
            gated, purpose, lambda pid: self.get_policy(tenant_id, pid)
        )
        results = gated[:k]

        filtered_count = len(ranked) - len(gated)
        reason = f"retrieved {len(results)} of {len(ranked)} fused candidates"
        if filtered_count:
            reason += f"; {filtered_count} filtered by privilege gate"
        outcome = AuditOutcome.GATED if filtered_count else AuditOutcome.ALLOW

        self._audit(
            tenant_id,
            agent_id,
            session_id,
            AuditOp.RETRIEVE,
            [r.id for r in results],
            AuditDecision(outcome=outcome, reason=reason),
        )
        return results

    # ------------------------------------------------------------------
    # Policy Engine (E4)
    # ------------------------------------------------------------------

    def get_policy(self, tenant_id: str, policy_id: str = "default") -> Policy:
        """
        Fetch a policy, or a permissive default if none has been configured.

        The default (empty purpose_bindings, default PrivilegeRules) is not
        persisted — it's synthesized on read. This means an unconfigured
        tenant behaves exactly as it did before E4 (purpose bindings are a
        no-op) while still getting PrivilegeRules' defaults, which already
        require trust for send_email/refund/escalate with zero setup.
        """
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM policy WHERE id = %s AND tenant_id = %s",
                    (policy_id, tenant_id),
                )
                row = cur.fetchone()
        if row is None:
            return Policy(id=policy_id, tenant_id=tenant_id)
        return _row_to_policy(row)

    def upsert_policy(self, policy: Policy) -> Policy:
        """Create or update a policy. (id, tenant_id) together are the primary key."""
        _require_tenant(policy.tenant_id)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO policy (id, tenant_id, purpose_bindings, privilege_rules, rbac)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (id, tenant_id) DO UPDATE SET
                           purpose_bindings = EXCLUDED.purpose_bindings,
                           privilege_rules = EXCLUDED.privilege_rules,
                           rbac = EXCLUDED.rbac""",
                    (
                        policy.id,
                        policy.tenant_id,
                        json.dumps([b.model_dump() for b in policy.purpose_bindings]),
                        json.dumps(policy.privilege_rules.model_dump()),
                        json.dumps(policy.rbac),
                    ),
                )
        return policy

    def check_privilege(
        self, memory_id: str, tenant_id: str, action: str, agent_id: str, session_id: str
    ) -> bool:
        """
        May `action` be performed using this memory? Evaluates the memory's
        own policy's privilege_rules (PrivilegeRules.privileged_actions +
        require_trust) and emits an AuditOp.POLICY_DECISION event either
        way — this is what that audit op existed for since E1 and never had
        a caller until now.
        """
        _require_tenant(tenant_id)
        record = self.get(memory_id, tenant_id)
        if record is None:
            allowed, reason, policy_id = False, "memory not found", "default"
        else:
            policy = self.get_policy(tenant_id, record.purpose.policy_id)
            allowed, reason = evaluate_privileged_action(policy, action, record.trust.taint)
            policy_id = policy.id

        outcome = AuditOutcome.ALLOW if allowed else AuditOutcome.DENY
        self._audit(
            tenant_id,
            agent_id,
            session_id,
            AuditOp.POLICY_DECISION,
            [memory_id],
            AuditDecision(outcome=outcome, reason=reason, policy_id=policy_id),
        )
        return allowed

    # ------------------------------------------------------------------
    # Governance mutations
    # ------------------------------------------------------------------

    def quarantine(self, memory_id: str, tenant_id: str, reason: str = "manual quarantine") -> bool:
        """Mark a memory as quarantined — excluded by retrieve()'s privilege gate (E3)."""
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
            self._audit(
                tenant_id,
                "system",
                "system",
                AuditOp.QUARANTINE,
                [memory_id],
                AuditDecision(outcome=AuditOutcome.ALLOW, reason=reason),
            )
        return updated

    def delete(self, memory_id: str, tenant_id: str) -> bool:
        """Hard-delete a single memory (GDPR right-to-erasure). Does not
        touch anything derived from it — use purge_cascade() (E6) when
        derivatives should be removed too."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM memory WHERE id = %s AND tenant_id = %s",
                    (memory_id, tenant_id),
                )
                deleted = cur.rowcount > 0
        if deleted:
            self._audit(
                tenant_id,
                "system",
                "system",
                AuditOp.PURGE,
                [memory_id],
                AuditDecision(outcome=AuditOutcome.ALLOW, reason="hard delete"),
            )
        return deleted

    # ------------------------------------------------------------------
    # Audit Graph: provenance + cascade purge (E6)
    # ------------------------------------------------------------------

    def _fetch_provenance_edges(self, tenant_id: str) -> list[tuple[str, list[str]]]:
        """(id, parent_ids) for every memory in a tenant — the raw material
        for building a ProvenanceGraph. Tenant-scoped, so cross-tenant
        parent_ids (which should never be written, but nothing enforces it
        at write time) simply won't resolve — see ProvenanceGraph's
        leaf-tolerance for out-of-set ids."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, parent_ids FROM memory WHERE tenant_id = %s",
                    (tenant_id,),
                )
                rows = cur.fetchall()
        return [(str(rid), _jsonb_list(parent_ids)) for rid, parent_ids in rows]

    def get_provenance_graph(self, tenant_id: str) -> ProvenanceGraph:
        """
        Build the full provenance graph for a tenant — every memory's
        parent_ids, as ancestor/descendant edges. Useful for a UI that wants
        to render more than one memory's lineage without re-querying per
        node; get_provenance() below is the single-memory convenience
        wrapper most callers want.
        """
        edges = self._fetch_provenance_edges(tenant_id)
        return build_provenance_graph(edges)

    def get_provenance(self, memory_id: str, tenant_id: str) -> dict:
        """
        Lineage for one memory: what it was derived from (ancestors) and
        what has been derived from it (descendants), each transitively.
        Read-only introspection — like vector_search()/lexical_search(),
        this does not emit an audit event (nothing is disclosed or gated
        that retrieve()/get() wouldn't already reveal one hop at a time;
        this just saves the caller from walking parent_ids by hand).
        """
        _require_tenant(tenant_id)
        graph = self.get_provenance_graph(tenant_id)
        return {
            "memory_id": memory_id,
            "ancestors": graph.ancestors(memory_id),
            "descendants": graph.descendants(memory_id),
        }

    def preview_cascade_purge(self, memory_id: str, tenant_id: str) -> CascadePurgePlan:
        """
        Preview what purge_cascade(memory_id) would delete, without
        deleting anything — for a confirmation dialog ("this will also
        remove 4 derived memories") before committing to the irreversible
        version below.
        """
        _require_tenant(tenant_id)
        graph = self.get_provenance_graph(tenant_id)
        return plan_cascade_purge(graph, memory_id)

    def purge_cascade(
        self,
        memory_id: str,
        tenant_id: str,
        reason: str = "cascade purge",
        agent_id: str = "system",
        session_id: str = "system",
    ) -> CascadePurgePlan:
        """
        Hard-delete `memory_id` and everything transitively derived from it
        (its full descendant set in the provenance graph), in one
        transaction, and emit a single AuditOp.PURGE event listing every id
        removed. Use this instead of delete() for GDPR right-to-erasure
        (so a customer's data can't survive via its own derivatives) or
        when cleaning up a memory discovered to be poisoned after the fact
        (so anything built on top of it goes with it).

        Idempotent-ish: purging an id with no descendants behaves exactly
        like delete() (a plan of just [memory_id]). Purging an id that no
        longer exists returns a plan whose all_ids still get attempted
        against DELETE, which simply affects 0 rows for that id — safe to
        retry.
        """
        _require_tenant(tenant_id)
        plan = self.preview_cascade_purge(memory_id, tenant_id)

        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM memory WHERE tenant_id = %s AND id = ANY(%s::uuid[])",
                    (tenant_id, plan.all_ids),
                )
                deleted_count = cur.rowcount

        full_reason = reason
        if plan.descendant_count:
            full_reason += (
                f"; root {memory_id} + {plan.descendant_count} descendant(s) "
                f"cascade-purged ({deleted_count} row(s) actually deleted)"
            )
        else:
            full_reason += f"; no descendants, equivalent to a single delete of {memory_id}"

        self._audit(
            tenant_id,
            agent_id,
            session_id,
            AuditOp.PURGE,
            plan.all_ids,
            AuditDecision(outcome=AuditOutcome.ALLOW, reason=full_reason),
        )
        return plan

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

    def list_audit(self, tenant_id: str, limit: int = 50) -> list[dict]:
        """Recent audit events for a tenant, newest first — for inspection/debugging."""
        _require_tenant(tenant_id)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT id, tenant_id, ts, agent_id, session_id, op, memory_ids,
                              outcome, reason, policy_id, hash, prev_hash
                       FROM audit WHERE tenant_id = %s
                       ORDER BY ts DESC LIMIT %s""",
                    (tenant_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def verify_audit_chain(self, tenant_id: str, limit: int = 10_000) -> AuditVerificationResult:
        """
        Formally verify a tenant's audit chain (E6): recompute every
        event's hash from its own stored fields and confirm both that it
        matches the recorded hash (no in-place tamper) and that prev_hash
        correctly links to the previous event (no deletion/reordering).

        This supersedes the linkage-only check scripts/categorize_demo.py
        used to do by hand — see core/audit/verifier.py for why that
        distinction matters. `limit` bounds how many recent events are
        checked; pass a number >= total event count for a full-history
        verification.
        """
        _require_tenant(tenant_id)
        events = self.list_audit(tenant_id, limit=limit)
        events = list(reversed(events))  # list_audit is newest-first; verify oldest-first
        return verify_chain(events)

    def _audit(
        self,
        tenant_id: str,
        agent_id: str,
        session_id: str,
        op: AuditOp,
        memory_ids: list[str],
        decision: AuditDecision,
    ) -> None:
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
                ts = datetime.now(UTC).isoformat()
                payload = f"{event_id}{tenant_id}{ts}{op.value}{json.dumps(sorted(memory_ids))}{decision.outcome.value}"
                current_hash = hashlib.sha256((prev_hash + payload).encode()).hexdigest()

                # `ts` is stored verbatim (not a separate NOW()) so that E6's
                # verify_chain() can recompute this exact hash later from
                # nothing but the persisted row — see core/audit/verifier.py.
                cur.execute(
                    """INSERT INTO audit (id, tenant_id, ts, agent_id, session_id, op,
                                          memory_ids, outcome, reason, policy_id, hash, prev_hash)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        event_id,
                        tenant_id,
                        ts,
                        agent_id,
                        session_id,
                        op.value,
                        json.dumps(memory_ids),
                        decision.outcome.value,
                        decision.reason,
                        decision.policy_id,
                        current_hash,
                        prev_hash,
                    ),
                )
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Internal: row → model
# ---------------------------------------------------------------------------


def _row_to_record(row: dict) -> MemoryRecord:
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
            parent_ids=_jsonb_list(row["parent_ids"]),
        ),
        trust=Trust(
            taint=Taint(row["taint"]),
            taint_reason=row["taint_reason"],
            injection_score=row["injection_score"],
        ),
        purpose=Purpose(
            allowed_purposes=_jsonb_list(row["allowed_purposes"]),
            policy_id=row["policy_id"],
        ),
        temporal=Temporal(
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
            superseded_by=str(row["superseded_by"]) if row["superseded_by"] else None,
            version=row["version"],
        ),
        access=Access(acl=_jsonb_list(row["acl"])),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_policy(row: dict) -> Policy:
    return Policy(
        id=row["id"],
        tenant_id=row["tenant_id"],
        purpose_bindings=[PurposeBinding(**b) for b in _jsonb_list(row["purpose_bindings"])],
        privilege_rules=PrivilegeRules(**_jsonb_dict(row["privilege_rules"])),
        rbac=_jsonb_list(row["rbac"]),
    )
