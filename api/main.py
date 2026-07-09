"""
FastAPI REST server (E7) -- the self-hosted surface for GovernedMemory.

Wraps the existing MemoryStore pipeline (E1-E4) behind the six routes from
the engineering plan's REST API section (Sec 5.8). Two are intentionally
thin stubs for now:

  - DELETE /v1/memory/{id}?cascade=true
  - GET    /v1/provenance/{id}

Both need the provenance graph traversal that's E6's job -- `parent_ids`
already exists on every record's Provenance, but nothing populates or
walks it yet (core/models/memory_record.py marks it "provenance graph
edges (E6)"). Plain (non-cascade) delete works today.

Run locally:
    make db-up
    make install-api
    make api
Run in Docker (server + Postgres together):
    docker compose -f deploy/docker-compose.yml up -d
Auth:
    export GOVERNEDMEMORY_API_KEYS="t1:some-secret-key"
    curl -H "Authorization: Bearer some-secret-key" http://localhost:8000/v1/audit
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status

from api.auth import require_tenant
from api.deps import get_store
from api.schemas import QuarantineBody, RetrieveBody, SuccessResponse, WriteBody
from core.memory_store import MemoryStore, NullEmbeddingProvider, init_db
from core.models import MemoryRecord, Provenance, WriteRequest


def _build_embedder():
    """Prefer SentenceTransformerProvider; fall back to NullEmbeddingProvider
    if the optional embed-local extras aren't installed -- the same fallback
    frontend/app.py uses, so vector search degrades instead of the server
    failing to start."""
    try:
        from core.memory_store import SentenceTransformerProvider

        return SentenceTransformerProvider()
    except ImportError:
        return NullEmbeddingProvider()


@asynccontextmanager
async def lifespan(app: FastAPI):
    dsn = os.environ["DATABASE_URL"]
    init_db(dsn)
    app.state.store = MemoryStore(dsn, _build_embedder())
    yield


app = FastAPI(title="GovernedMemory API", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/memory", response_model=MemoryRecord, status_code=status.HTTP_201_CREATED)
def write_memory(
    body: WriteBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> MemoryRecord:
    req = WriteRequest(tenant_id=tenant_id, **body.model_dump())
    return store.write(req)


@app.post("/v1/retrieve", response_model=list[MemoryRecord])
def retrieve(
    body: RetrieveBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> list[MemoryRecord]:
    return store.retrieve(
        query=body.query,
        tenant_id=tenant_id,
        agent_id=body.agent_id,
        session_id=body.session_id,
        purpose=body.purpose,
        k=body.k,
        include_untrusted=body.include_untrusted,
    )


@app.post("/v1/quarantine", response_model=SuccessResponse)
def quarantine(
    body: QuarantineBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> SuccessResponse:
    found = store.quarantine(body.memory_id, tenant_id, reason=body.reason)
    if not found:
        raise HTTPException(status_code=404, detail="memory not found")
    return SuccessResponse(success=True)


@app.delete("/v1/memory/{memory_id}", response_model=SuccessResponse)
def delete_memory(
    memory_id: str,
    cascade: bool = False,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> SuccessResponse:
    if cascade:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "cascade purge needs E6's provenance graph traversal -- not built yet, "
                "call without ?cascade=true for a plain delete"
            ),
        )
    found = store.delete(memory_id, tenant_id)
    if not found:
        raise HTTPException(status_code=404, detail="memory not found")
    return SuccessResponse(success=True)


@app.get("/v1/audit", response_model=list[dict])
def list_audit(
    limit: int = 50,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> list[dict]:
    return store.list_audit(tenant_id, limit=limit)


@app.get("/v1/provenance/{memory_id}")
def provenance(
    memory_id: str,
    tenant_id: str = Depends(require_tenant),
) -> Provenance:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "provenance tree traversal is E6 work (parent_ids exists on every record "
            "but nothing populates/walks it yet) -- not built yet"
        ),
    )
