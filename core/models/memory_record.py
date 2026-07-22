"""
Core MemoryRecord data model — matches the engineering plan §4 exactly.

Design notes:
- tenant_id: the enterprise/company using Metaworkers (row-level isolation key)
- customer_id: the end-customer whose memory this is (the CX subject)
- agent_id: which AI agent wrote or retrieved this memory
- Trust/taint fields are populated by the Write Governor (E2); E1 defines the schema only
- Embedding is stored in Postgres, not in this Pydantic model (it's a DB concern)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SourceType(str, Enum):
    USER = "user"
    TRUSTED_SYSTEM = "trusted_system"
    TOOL_OUTPUT = "tool_output"
    UNTRUSTED_WEB = "untrusted_web"
    UNTRUSTED_EMAIL = "untrusted_email"
    AGENT_DERIVED = "agent_derived"


class Taint(str, Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    QUARANTINED = "quarantined"


class Provenance(BaseModel):
    """Where did this memory come from?"""

    source_type: SourceType
    source_ref: str  # e.g. "Zendesk #4821", "email-thread-abc123"
    ingested_at: datetime = Field(default_factory=_utcnow)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    parent_ids: list[str] = Field(default_factory=list)  # provenance graph edges (E6)


class Trust(BaseModel):
    """Taint status assigned by the Write Governor (E2). Defaults to trusted."""

    taint: Taint = Taint.TRUSTED
    taint_reason: str | None = None
    injection_score: float = Field(default=0.0, ge=0.0, le=1.0)


class Purpose(BaseModel):
    """Which agent actions may use this memory?"""

    allowed_purposes: list[str] = Field(default_factory=list)
    policy_id: str = "default"


class Temporal(BaseModel):
    """Versioning and TTL — prevents stale memory from poisoning future reads."""

    valid_from: datetime = Field(default_factory=_utcnow)
    valid_until: datetime | None = None  # None = no expiry
    superseded_by: str | None = None  # UUID of replacement record
    version: int = 1


class Access(BaseModel):
    """Coarse-grained access control list (role names or agent IDs)."""

    acl: list[str] = Field(default_factory=list)  # empty = open to all within tenant


class MemoryRecord(BaseModel):
    """
    The canonical in-memory representation of a governed memory record.
    Persisted to Postgres; embedding stored separately in the vector column.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str  # isolation key — on every query
    customer_id: str  # subject of the memory (the end-customer)
    agent_id: str  # agent that created this record
    session_id: str  # conversation session that created this record
    content: str  # the raw memory text
    provenance: Provenance
    trust: Trust = Field(default_factory=Trust)
    purpose: Purpose = Field(default_factory=Purpose)
    temporal: Temporal = Field(default_factory=Temporal)
    access: Access = Field(default_factory=Access)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    # The append-only audit event associated with the operation that returned
    # this record.  This is response metadata, not a persisted memory column.
    audit_id: str | None = None


class WriteRequest(BaseModel):
    """
    Caller-supplied input to MemoryStore.write().
    The store's Write Governor fills in trust/taint based on provenance + detection score.
    """

    tenant_id: str
    customer_id: str
    agent_id: str
    session_id: str
    content: str
    provenance: Provenance
    purpose: Purpose = Field(default_factory=Purpose)
    temporal: Temporal = Field(default_factory=Temporal)
    access: Access = Field(default_factory=Access)
