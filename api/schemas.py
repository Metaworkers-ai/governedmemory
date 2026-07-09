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

from core.models import Access, Provenance, Purpose, Temporal


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
