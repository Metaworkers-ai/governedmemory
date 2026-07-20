"""
Request/response models for the REST API (E7).

Deliberately NOT reusing core.models.WriteRequest as-is: that model carries
a tenant_id field, and this layer must never take tenant_id from the
caller -- it's resolved from the API key (see api/auth.py). These bodies
mirror WriteRequest's other fields exactly; route handlers in api/main.py
fill in tenant_id themselves from the authenticated identity.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.models import (
    Access,
    ExternalMemoryCandidate,
    Provenance,
    Purpose,
    Temporal,
)


class WriteBody(BaseModel):
    customer_id: str
    agent_id: str
    session_id: str
    content: str
    provenance: Provenance
    purpose: Purpose = Field(default_factory=Purpose)
    temporal: Temporal = Field(default_factory=Temporal)
    access: Access = Field(default_factory=Access)


class RetrieveBody(BaseModel):
    query: str
    agent_id: str
    session_id: str
    purpose: str | None = None
    k: int = 10
    include_untrusted: bool = False


class QuarantineBody(BaseModel):
    memory_id: str
    reason: str = "manual quarantine"


class SuccessResponse(BaseModel):
    success: bool


class ProvenanceResponse(BaseModel):
    """A memory's lineage (E6): what it was derived from and what has been
    derived from it, each walked transitively over parent_ids."""

    memory_id: str
    ancestors: list[str]
    descendants: list[str]


class CascadePurgePlanResponse(BaseModel):
    """What a cascade purge of root_id would delete (E6) -- root_id plus
    every transitive descendant. Returned by the dry-run preview and by the
    delete endpoint once a cascade purge has actually been applied."""

    root_id: str
    descendant_ids: list[str]
    descendant_count: int


class ExternalWriteEvaluationBody(BaseModel):
    customer_id: str
    agent_id: str
    session_id: str
    content: str
    provenance: Provenance
    purpose: str | None = None
    idempotency_key: str
    correlation_id: str | None = None
    strict_untrusted_write: bool = False


class ExternalBindingBody(BaseModel):
    correlation_id: str
    external_memory_ids: list[str]


class ExternalNoopCompletionBody(BaseModel):
    correlation_id: str


class ExternalFailureBody(BaseModel):
    correlation_id: str
    reason: str
    external_memory_ids: list[str] = Field(default_factory=list)


class ExternalCandidateEvaluationBody(BaseModel):
    candidates: list[ExternalMemoryCandidate]
    customer_id: str | None = None
    agent_id: str = "system"
    session_id: str = "system"
    purpose: str | None = None
    compatibility_mode: str = "compatible"
    idempotency_key: str | None = None


class ExternalQuarantineBody(BaseModel):
    reason: str = "manual quarantine"
    agent_id: str = "system"
    session_id: str = "external-quarantine"
