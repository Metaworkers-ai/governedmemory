"""
Policy engine: ACL checks, PII masking, retention enforcement, staleness detection.
"""
import re
from datetime import datetime
from typing import List, Tuple
from models import MemoryRecord, AgentRole, Sensitivity


# Role hierarchy: higher index = more access
_ROLE_LEVEL = {
    AgentRole.SUPPORT: 1,
    AgentRole.BILLING: 2,
    AgentRole.MANAGER: 3,
    AgentRole.LEGAL: 3,
    AgentRole.ADMIN: 4,
}

# Sensitivity → minimum role level required
_SENSITIVITY_GATE = {
    Sensitivity.PUBLIC: 1,
    Sensitivity.INTERNAL: 1,
    Sensitivity.CONFIDENTIAL: 2,
    Sensitivity.PII: 3,
}

# Simple PII patterns (extend for production)
_PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
}


def check_access(memory: MemoryRecord, agent_role: AgentRole) -> Tuple[bool, str]:
    """Returns (allowed, reason)."""
    if memory.is_expired:
        return False, "memory expired (retention policy)"

    # Sensitivity gate
    required_level = _SENSITIVITY_GATE.get(memory.sensitivity, 1)
    agent_level = _ROLE_LEVEL.get(agent_role, 0)
    if agent_level < required_level:
        return False, f"sensitivity={memory.sensitivity.value} requires role level {required_level}, agent has {agent_level}"

    # Explicit ACL check
    if agent_role not in memory.allowed_roles and agent_role != AgentRole.ADMIN:
        return False, f"role '{agent_role.value}' not in allowed_roles {[r.value for r in memory.allowed_roles]}"

    return True, "allowed"


def mask_pii(content: str, pii_fields: List[str]) -> Tuple[str, bool]:
    """
    Mask PII in content. Returns (masked_content, was_masked).
    pii_fields hints which patterns to apply; always run all patterns as safety net.
    """
    masked = content
    was_masked = False
    for name, pattern in _PII_PATTERNS.items():
        new = pattern.sub(f"[{name.upper()}_REDACTED]", masked)
        if new != masked:
            was_masked = True
            masked = new
    return masked, was_masked


def is_stale(memory: MemoryRecord, all_customer_memories: List[MemoryRecord]) -> Tuple[bool, str]:
    """
    Detect if this memory is superseded by a newer one covering the same topic.
    Simple heuristic: same tags + newer record exists.
    """
    if memory.is_stale:
        return True, memory.stale_reason or "marked stale"

    if not memory.tags:
        return False, ""

    for other in all_customer_memories:
        if other.id == memory.id:
            continue
        shared_tags = set(memory.tags) & set(other.tags)
        if shared_tags and other.created_at > memory.created_at:
            return True, f"superseded by newer record on topic(s): {', '.join(shared_tags)}"

    return False, ""


def apply_retention_purge(memories: List[MemoryRecord]) -> List[MemoryRecord]:
    """Filter out expired memories (call before returning to agent)."""
    now = datetime.utcnow()
    return [m for m in memories if m.expires_at > now]
