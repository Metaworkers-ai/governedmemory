"""
AuditEvent model — append-only, hash-chained for tamper evidence.

Every write, retrieve, quarantine, purge, and policy decision emits one event.
The store computes hash = SHA-256(prev_hash + event_payload) and stores it.
This gives a verifiable chain: any tampering breaks the hash sequence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List
from pydantic import BaseModel, Field
import uuid


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditOp(str, Enum):
    WRITE = "write"
    RETRIEVE = "retrieve"
    QUARANTINE = "quarantine"
    PURGE = "purge"
    POLICY_DECISION = "policy_decision"


class AuditOutcome(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    GATED = "gated"


class AuditActor(BaseModel):
    agent_id: str
    session_id: str


class AuditDecision(BaseModel):
    outcome: AuditOutcome
    reason: str
    policy_id: str = "default"


class AuditEvent(BaseModel):
    """
    One audit log entry. Never updated after creation.
    hash and prev_hash are set by MemoryStore._emit_audit(), not the caller.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    ts: datetime = Field(default_factory=_utcnow)
    actor: AuditActor
    op: AuditOp
    memory_ids: List[str]
    decision: AuditDecision
    hash: str = ""       # computed by store before INSERT
    prev_hash: str = ""  # last audit event's hash for this tenant
