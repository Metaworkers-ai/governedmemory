"""
Memory retrieval engine: keyword scoring + recency ranking + governance filtering.
"""
from typing import List, Tuple
from models import (
    MemoryRecord, MemoryQuery, CustomerMemoryCard,
    GovernedMemoryItem, GovernanceSummary, AgentRole
)
from memory_store import get_memories_for_customer
from governance import check_access, mask_pii, is_stale, apply_retention_purge


def _keyword_score(content: str, query: str) -> float:
    """Simple term-overlap score, normalized 0-1."""
    if not query:
        return 1.0
    query_terms = set(query.lower().split())
    content_terms = set(content.lower().split())
    overlap = query_terms & content_terms
    return len(overlap) / len(query_terms) if query_terms else 0.0


def _rank_memories(memories: List[MemoryRecord], query_text: str) -> List[Tuple[MemoryRecord, float]]:
    """Score and sort memories by relevance + confidence + recency."""
    from datetime import datetime
    now = datetime.utcnow()
    scored = []
    for m in memories:
        kw = _keyword_score(m.content, query_text)
        # Recency decay: full score for <30 days, halves every 90 days
        age_days = max(0, (now - m.created_at).days)
        recency = max(0.1, 1.0 - (age_days / 365))
        score = (kw * 0.5) + (m.confidence * 0.3) + (recency * 0.2)
        scored.append((m, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def build_memory_card(customer_id: str, agent_role: AgentRole, query_text: str = "", max_results: int = 10) -> CustomerMemoryCard:
    all_memories = get_memories_for_customer(customer_id)
    live_memories = apply_retention_purge(all_memories)

    blocked_acl = 0
    expired_count = len(all_memories) - len(live_memories)
    stale_count = 0
    pii_masked_count = 0
    allowed_items: List[GovernedMemoryItem] = []

    ranked = _rank_memories(live_memories, query_text)

    for memory, _score in ranked:
        allowed, reason = check_access(memory, agent_role)
        if not allowed:
            blocked_acl += 1
            continue

        stale, stale_reason = is_stale(memory, live_memories)
        if stale:
            stale_count += 1

        content, was_masked = mask_pii(memory.content, memory.pii_fields)
        if was_masked:
            pii_masked_count += 1

        allowed_items.append(GovernedMemoryItem(
            id=memory.id,
            content=content,
            source_ref=memory.source_ref,
            source_type=memory.source_type,
            confidence=memory.confidence,
            created_at=memory.created_at,
            expires_at=memory.expires_at,
            tags=memory.tags,
            stale_warning=stale_reason if stale else None,
            pii_masked=was_masked,
        ))

    top_items = allowed_items[:max_results]
    citations = list(dict.fromkeys(item.source_ref for item in top_items))

    return CustomerMemoryCard(
        customer_id=customer_id,
        agent_role=agent_role,
        memories=top_items,
        governance=GovernanceSummary(
            total_memories=len(all_memories),
            allowed_memories=len(allowed_items),
            blocked_by_acl=blocked_acl,
            expired_count=expired_count,
            stale_count=stale_count,
            pii_masked_count=pii_masked_count,
        ),
        citations=citations,
    )
