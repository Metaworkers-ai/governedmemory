"""
FastAPI REST server (E7) -- the self-hosted surface for GovernedMemory.

Wraps the existing MemoryStore pipeline (E1-E6) behind the six routes from
the engineering plan's REST API section (Sec 5.8), plus /v1/customers and
/v1/memories (listing -- added for the Next.js frontend's Browse page,
since the original plan had no way to list what's stored without knowing
a search query). DELETE /v1/memory/{id}?cascade=true and
GET /v1/provenance/{id} are backed by E6's provenance graph
(core/audit/provenance_graph.py) via MemoryStore.purge_cascade() and
MemoryStore.get_provenance().

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
from api.schemas import (
    CascadePurgePlanResponse,
    ExternalBindingBody,
    ExternalCandidateEvaluationBody,
    ExternalFailureBody,
    ExternalQuarantineBody,
    ExternalWriteEvaluationBody,
    ProvenanceResponse,
    QuarantineBody,
    RetrieveBody,
    SuccessResponse,
    WriteBody,
)
from core.errors import ExternalGovernanceError
from core.governance import GovernanceEvaluationRequest
from core.memory_store import MemoryStore, NullEmbeddingProvider, init_db
from core.models import MemoryRecord, WriteRequest


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


@app.get("/v1/identity")
def identity(tenant_id: str = Depends(require_tenant)) -> dict[str, str]:
    return {"tenant_id": tenant_id}


def _external_error(exc: ExternalGovernanceError | ValueError) -> HTTPException:
    if isinstance(exc, ExternalGovernanceError):
        return HTTPException(status_code=exc.status_code, detail=exc.as_detail())
    return HTTPException(status_code=422, detail=str(exc))


@app.post("/v1/memory", response_model=MemoryRecord, status_code=status.HTTP_201_CREATED)
def write_memory(
    body: WriteBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> MemoryRecord:
    req = WriteRequest(tenant_id=tenant_id, **body.model_dump())
    return store.write(req)


@app.post("/v1/external-memories/evaluate-write")
def evaluate_external_write(
    body: ExternalWriteEvaluationBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
):
    request = GovernanceEvaluationRequest(
        operation="external_add",
        tenant_id=tenant_id,
        customer_id=body.customer_id,
        agent_id=body.agent_id,
        session_id=body.session_id,
        purpose=body.purpose,
        provenance=body.provenance,
        source_type=body.provenance.source_type,
        content=body.content,
        external_system="mem0",
        idempotency_key=body.idempotency_key,
    )
    try:
        return store.evaluate_external_write(
            request,
            idempotency_key=body.idempotency_key,
            strict_untrusted_write=body.strict_untrusted_write,
            correlation_id=body.correlation_id,
        )
    except (ExternalGovernanceError, ValueError) as exc:
        raise _external_error(exc) from exc


@app.post("/v1/external-memories/bind")
def bind_external_memories(
    body: ExternalBindingBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
):
    try:
        return store.bind_external_memories(
            tenant_id, body.correlation_id, body.external_memory_ids
        )
    except (ExternalGovernanceError, ValueError) as exc:
        raise _external_error(exc) from exc


@app.post("/v1/external-memories/retry-binding")
def retry_external_binding(
    body: ExternalBindingBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
):
    try:
        return store.retry_binding(tenant_id, body.correlation_id, body.external_memory_ids)
    except (ExternalGovernanceError, ValueError) as exc:
        raise _external_error(exc) from exc


@app.post("/v1/external-memories/evaluate-candidates")
def evaluate_external_candidates(
    body: ExternalCandidateEvaluationBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
):
    try:
        return store.evaluate_external_candidates(
            tenant_id,
            body.candidates,
            customer_id=body.customer_id,
            agent_id=body.agent_id,
            session_id=body.session_id,
            purpose=body.purpose,
            compatibility_mode=body.compatibility_mode,
            idempotency_key=body.idempotency_key,
        )
    except (ExternalGovernanceError, ValueError) as exc:
        raise _external_error(exc) from exc


@app.post("/v1/external-memories/fail")
def fail_external_write(
    body: ExternalFailureBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
):
    try:
        return store.mark_external_failure(
            tenant_id,
            body.correlation_id,
            body.reason,
            body.external_memory_ids,
        )
    except (ExternalGovernanceError, ValueError) as exc:
        raise _external_error(exc) from exc


@app.get("/v1/external-memories/{external_memory_id}/governance")
def get_external_governance(
    external_memory_id: str,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
):
    result = store.get_external_governance(tenant_id, external_memory_id)
    if result is None:
        raise HTTPException(status_code=404, detail="external memory binding not found")
    return result


@app.post("/v1/external-memories/{external_memory_id}/quarantine")
def quarantine_external_memory(
    external_memory_id: str,
    body: ExternalQuarantineBody,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
):
    result = store.quarantine_external_memory(
        tenant_id,
        external_memory_id,
        body.reason,
        actor_id=body.agent_id,
        session_id=body.session_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="external memory binding not found")
    return result


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
        if store.get(memory_id, tenant_id) is None:
            raise HTTPException(status_code=404, detail="memory not found")
        store.purge_cascade(memory_id, tenant_id)
        return SuccessResponse(success=True)
    found = store.delete(memory_id, tenant_id)
    if not found:
        raise HTTPException(status_code=404, detail="memory not found")
    return SuccessResponse(success=True)


@app.get("/v1/memory/{memory_id}/cascade-preview", response_model=CascadePurgePlanResponse)
def cascade_preview(
    memory_id: str,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> CascadePurgePlanResponse:
    """Dry-run preview of DELETE ?cascade=true (E6) -- what would be deleted
    without deleting anything, for a confirmation step before calling the
    real cascade delete."""
    plan = store.preview_cascade_purge(memory_id, tenant_id)
    return CascadePurgePlanResponse(
        root_id=plan.root_id,
        descendant_ids=plan.descendant_ids,
        descendant_count=plan.descendant_count,
    )


@app.get("/v1/audit", response_model=list[dict])
def list_audit(
    limit: int = 50,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> list[dict]:
    return store.list_audit(tenant_id, limit=limit)


@app.get("/v1/customers", response_model=list[dict])
def list_customers(
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> list[dict]:
    """Distinct customers for the authenticated tenant, with memory counts --
    listing/navigation wasn't part of the original six-route plan, but a
    frontend can't browse without it."""
    return store.list_customers(tenant_id)


@app.get("/v1/memories", response_model=list[MemoryRecord])
def list_memories(
    customer_id: str,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> list[MemoryRecord]:
    """All memories for one customer, newest first -- the plain listing
    frontend/app.py gets from MemoryStore.list_for_customer() directly.
    Unlike /v1/retrieve, this applies no query, ranking, or privilege gate:
    it is scoped by tenant_id (from the API key) and customer_id only."""
    return store.list_for_customer(tenant_id, customer_id)


@app.get("/v1/provenance/{memory_id}", response_model=ProvenanceResponse)
def provenance(
    memory_id: str,
    tenant_id: str = Depends(require_tenant),
    store: MemoryStore = Depends(get_store),
) -> ProvenanceResponse:
    """A memory's lineage (E6): what it was derived from (ancestors) and
    what has been derived from it (descendants), each walked transitively
    over parent_ids via the provenance graph."""
    return ProvenanceResponse(**store.get_provenance(memory_id, tenant_id))
