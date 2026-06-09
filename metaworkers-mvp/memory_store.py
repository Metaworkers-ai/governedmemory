"""
SQLite-backed memory store with JSON serialization.
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from pathlib import Path
from models import MemoryRecord, MemoryIngestRequest, SourceType, Sensitivity, AgentRole


DB_PATH = Path("metaworkers.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                content TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                source_type TEXT NOT NULL,
                sensitivity TEXT NOT NULL,
                pii_fields TEXT NOT NULL DEFAULT '[]',
                retention_days INTEGER NOT NULL DEFAULT 365,
                allowed_roles TEXT NOT NULL DEFAULT '["support"]',
                confidence REAL NOT NULL DEFAULT 1.0,
                tags TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_stale INTEGER NOT NULL DEFAULT 0,
                stale_reason TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer ON memories(customer_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON memories(expires_at)")
        conn.commit()


def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        customer_id=row["customer_id"],
        content=row["content"],
        source_ref=row["source_ref"],
        source_type=SourceType(row["source_type"]),
        sensitivity=Sensitivity(row["sensitivity"]),
        pii_fields=json.loads(row["pii_fields"]),
        retention_days=row["retention_days"],
        allowed_roles=[AgentRole(r) for r in json.loads(row["allowed_roles"])],
        confidence=row["confidence"],
        tags=json.loads(row["tags"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        is_stale=bool(row["is_stale"]),
        stale_reason=row["stale_reason"],
    )


def add_memory(req: MemoryIngestRequest) -> MemoryRecord:
    record = MemoryRecord(**req.model_dump())
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record.id,
                record.customer_id,
                record.content,
                record.source_ref,
                record.source_type.value,
                record.sensitivity.value,
                json.dumps(record.pii_fields),
                record.retention_days,
                json.dumps([r.value for r in record.allowed_roles]),
                record.confidence,
                json.dumps(record.tags),
                record.created_at.isoformat(),
                record.expires_at.isoformat(),
                int(record.is_stale),
                record.stale_reason,
            ),
        )
        conn.commit()
    return record


def get_memories_for_customer(customer_id: str) -> List[MemoryRecord]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM memories WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def get_memory_by_id(memory_id: str) -> Optional[MemoryRecord]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_record(row) if row else None


def delete_memory(memory_id: str) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
    return cursor.rowcount > 0


def mark_stale(memory_id: str, reason: str):
    with _get_conn() as conn:
        conn.execute(
            "UPDATE memories SET is_stale = 1, stale_reason = ? WHERE id = ?",
            (reason, memory_id),
        )
        conn.commit()


def get_all_stats() -> dict:
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        customers = conn.execute("SELECT COUNT(DISTINCT customer_id) FROM memories").fetchone()[0]
    return {"total_memories": total, "total_customers": customers}
