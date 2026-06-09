"""
Core data models for Metaworkers governed memory layer.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class SourceType(str, Enum):
    TICKET = "ticket"
    CRM = "crm"
    CHAT = "chat"
    VOICE = "voice"
    KB = "kb"
    MANUAL = "manual"


class Sensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"


class AgentRole(str, Enum):
    SUPPORT = "support"
    MANAGER = "manager"
    ADMIN = "admin"
    BILLING = "billing"
    LEGAL = "legal"


# --- Ingestion ---

class MemoryIngestRequest(BaseModel):
    customer_id: str
    content: str
    source_ref: str  # e.g. "Zendesk #1842", "Salesforce CRM", "Call transcript"
    source_type: SourceType = SourceType.MANUAL
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    pii_fields: List[str] = Field(default_factory=list, description="Fields/patterns that are PII")
    retention_days: int = Field(default=365, ge=1)
    allowed_roles: List[AgentRole] = Field(default_factory=lambda: [AgentRole.SUPPORT])
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    content: str
    source_ref: str
    source_type: SourceType
    sensitivity: Sensitivity
    pii_fields: List[str]
    retention_days: int
    allowed_roles: List[AgentRole]
    confidence: float
    tags: List[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default=None)
    is_stale: bool = False
    stale_reason: Optional[str] = None

    def model_post_init(self, __context):
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(days=self.retention_days)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


# --- Query ---

class MemoryQuery(BaseModel):
    customer_id: str
    query_text: str
    agent_role: AgentRole = AgentRole.SUPPORT
    max_results: int = Field(default=5, ge=1, le=20)


# --- Memory Card (the core product output) ---

class GovernedMemoryItem(BaseModel):
    id: str
    content: str
    source_ref: str
    source_type: SourceType
    confidence: float
    created_at: datetime
    expires_at: datetime
    tags: List[str]
    stale_warning: Optional[str] = None
    pii_masked: bool = False


class GovernanceSummary(BaseModel):
    total_memories: int
    allowed_memories: int
    blocked_by_acl: int
    expired_count: int
    stale_count: int
    pii_masked_count: int


class CustomerMemoryCard(BaseModel):
    customer_id: str
    agent_role: AgentRole
    memories: List[GovernedMemoryItem]
    governance: GovernanceSummary
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    citations: List[str] = Field(default_factory=list)


# --- API responses ---

class IngestResponse(BaseModel):
    memory_id: str
    message: str
    expires_at: datetime


class ForgetResponse(BaseModel):
    deleted: bool
    memory_id: str
    message: str


class HealthResponse(BaseModel):
    status: str
    total_memories: int
    total_customers: int
