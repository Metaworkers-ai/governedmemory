"""Transport-neutral governance evaluation models.

Native GovernedMemory writes and external-memory adapters both construct the
same request and receive the same decision.  Persistence and HTTP layers add
operation/binding identifiers around these models; the policy decision itself
stays in this domain boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.models.memory_record import Provenance, SourceType, Taint

OperationType = Literal[
    "native_write",
    "external_add",
    "external_candidate",
    "external_quarantine",
    "external_update",
    "external_delete",
]
StorageDecision = Literal["allow", "allow_quarantined", "deny"]
RetrievalDecision = Literal["allow", "exclude", "purpose_restricted"]
EvaluationStatus = Literal[
    "evaluated",
    "denied",
    "external_succeeded",
    "binding_pending",
    "completed",
    "failed",
]


class GovernanceEvaluationRequest(BaseModel):
    """Input shared by native writes and external-memory operations."""

    operation: OperationType
    tenant_id: str
    customer_id: str | None = None
    agent_id: str = "system"
    session_id: str = "system"
    purpose: str | None = None
    provenance: Provenance | None = None
    source_type: SourceType | None = None
    content: str | None = None
    external_system: str | None = None
    external_memory_id: str | None = None
    idempotency_key: str | None = None


class GovernanceDecision(BaseModel):
    """Canonical governance result returned by every integration boundary."""

    operation_id: str | None = None
    correlation_id: str
    storage: StorageDecision
    retrieval: RetrievalDecision
    taint: Taint
    taint_reason: str | None = None
    injection_score: float = Field(default=0.0, ge=0.0, le=1.0)
    injection_labels: list[str] = Field(default_factory=list)
    policy_id: str = "default"
    evaluation_audit_id: str | None = None
    binding_audit_ids: list[str] = Field(default_factory=list)
    external_memory_ids: list[str] = Field(default_factory=list)
    status: EvaluationStatus = "evaluated"
    failure_reason: str | None = None
    evaluated_at: datetime | None = None
    external_write_claimed: bool = False
    external_write_in_progress: bool = False
    external_write_claim_token: str | None = None
    external_write_claim_expires_at: datetime | None = None
