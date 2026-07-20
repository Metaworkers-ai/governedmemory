"""Models for governance metadata attached to external memory systems."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExternalMemoryCandidate(BaseModel):
    """A Mem0 search candidate identified by its native external ID."""

    external_memory_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class ExternalCandidateDecision(BaseModel):
    external_memory_id: str | None = None
    status: Literal[
        "governed",
        "untracked",
        "untrusted",
        "quarantined",
        "purpose_restricted",
        "scope_restricted",
        "missing_id",
    ]
    decision: Literal["allow", "exclude"]
    reason: str


class ExternalCandidateEvaluation(BaseModel):
    operation_id: str
    correlation_id: str
    decisions: list[ExternalCandidateDecision]
    audit_id: str | None = None


class ExternalMemoryGovernance(BaseModel):
    external_system: str
    external_memory_id: str
    operation_id: str
    tenant_id: str
    customer_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    purpose: str | None = None
    provenance: dict = Field(default_factory=dict)
    taint: str
    quarantine_status: bool
    policy_id: str
    lifecycle_state: str
    binding_audit_id: str | None = None
    quarantine_audit_id: str | None = None
