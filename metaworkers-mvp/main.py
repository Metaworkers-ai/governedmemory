"""
Metaworkers.AI — Governed Customer Memory API
FastAPI entry point.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from models import (
    MemoryIngestRequest, IngestResponse, ForgetResponse,
    CustomerMemoryCard, MemoryQuery, HealthResponse, AgentRole
)
from memory_store import init_db, add_memory, delete_memory, get_memory_by_id, get_all_stats
from retrieval import build_memory_card

app = FastAPI(
    title="Metaworkers.AI — Governed Customer Memory",
    description=(
        "Persistent, policy-controlled memory layer for enterprise AI support agents. "
        "Ingest CX data, govern access, retrieve cited customer context at runtime."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ---- Ingest ----

@app.post("/ingest", response_model=IngestResponse, tags=["Memory"])
def ingest_memory(req: MemoryIngestRequest):
    """
    Ingest a new memory from any CX source (ticket, CRM, chat, voice, KB).
    Attaches governance metadata: sensitivity, PII fields, retention, ACL.
    """
    record = add_memory(req)
    return IngestResponse(
        memory_id=record.id,
        message=f"Memory stored for customer '{req.customer_id}' from {req.source_ref}",
        expires_at=record.expires_at,
    )


# ---- Memory Card ----

@app.get("/memory-card/{customer_id}", response_model=CustomerMemoryCard, tags=["Memory"])
def get_memory_card(
    customer_id: str,
    agent_role: AgentRole = Query(default=AgentRole.SUPPORT),
    query: Optional[str] = Query(default="", description="Optional agent query to rank memories"),
    max_results: int = Query(default=10, ge=1, le=20),
):
    """
    Generate a governed Customer Memory Card for a support agent.
    Applies ACL, retention policy, PII masking, and staleness detection.
    Returns only memories the agent's role is allowed to see.
    """
    card = build_memory_card(customer_id, agent_role, query, max_results)
    if card.governance.total_memories == 0:
        raise HTTPException(status_code=404, detail=f"No memories found for customer '{customer_id}'")
    return card


# ---- Agent Query ----

@app.post("/query", response_model=CustomerMemoryCard, tags=["Memory"])
def query_memories(req: MemoryQuery):
    """
    Agent runtime query: retrieve the most relevant governed memories for a customer.
    Combines keyword relevance, confidence, and recency scoring.
    """
    card = build_memory_card(req.customer_id, req.agent_role, req.query_text, req.max_results)
    if card.governance.total_memories == 0:
        raise HTTPException(status_code=404, detail=f"No memories found for customer '{req.customer_id}'")
    return card


# ---- Forget (GDPR / Right to Delete) ----

@app.delete("/memories/{memory_id}", response_model=ForgetResponse, tags=["Governance"])
def forget_memory(memory_id: str):
    """
    Delete a specific memory (GDPR right-to-erasure, policy enforcement).
    """
    record = get_memory_by_id(memory_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")
    deleted = delete_memory(memory_id)
    return ForgetResponse(
        deleted=deleted,
        memory_id=memory_id,
        message=f"Memory deleted for customer '{record.customer_id}'",
    )


# ---- Health ----

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    stats = get_all_stats()
    return HealthResponse(status="ok", **stats)
