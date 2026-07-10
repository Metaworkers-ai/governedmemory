# Use Case: Multi-Tenant Isolation for Agent Platforms

**The problem in one sentence:** if you're building an agent product that serves more than one customer, a single cross-tenant memory leak — Company A's agent surfacing Company B's data — is a company-ending incident, not a bug ticket.

## The scenario

You run a support-agent platform. Tenant `acme-corp` and tenant `initech` both use your product. An engineer forgets a `WHERE tenant_id = ?` clause in one query path, or a caching layer keys on `customer_id` alone instead of `(tenant_id, customer_id)`. Now Initech's agent can retrieve Acme's customer memory. This is the single most common way B2B AI platforms end up in a breach disclosure.

## How Governed Memory prevents it

Every table (`memory`, `policy`, `audit`) is keyed on `tenant_id`, and every read/write method requires it as an explicit argument — there is no "default tenant" and no method that queries without one. `_require_tenant()` guards every entry point in `MemoryStore`.

```python
from core.memory_store import MemoryStore, NullEmbeddingProvider
from core.models import WriteRequest, Provenance, SourceType

store = MemoryStore(dsn, NullEmbeddingProvider())

rec_a = store.write(WriteRequest(
    tenant_id="tenant-a", customer_id="cust-001",
    agent_id="agent-1", session_id="sess-1",
    content="Confidential info for tenant A",
    provenance=Provenance(source_type=SourceType.TRUSTED_SYSTEM, source_ref="crm"),
))

# Try to read it as tenant B — the record simply does not exist from this tenant's view
result = store.get(rec_a.id, "tenant-b")
print(result)   # -> None

# The correct tenant reads it fine
result = store.get(rec_a.id, "tenant-a")
print(result.content)  # -> "Confidential info for tenant A"
```

This isn't a filter applied after the fact — `get()`, `retrieve()`, `vector_search()`, `lexical_search()`, `quarantine()`, `delete()`, `get_policy()`, and `check_privilege()` all scope their SQL by `tenant_id` directly, so there's no code path that can accidentally return another tenant's rows. `quarantine()`/`delete()` on the wrong tenant simply affect zero rows (`rowcount == 0`) rather than silently succeeding or erroring.

## Try it in the demo

The integration test suite has a dedicated `TestTenantIsolation` class (4 tests) that runs against a real Postgres instance on every CI run — including cross-tenant `get`, `quarantine`, and `delete` attempts. Run it yourself:

```bash
pytest tests/integration/test_memory_store.py -v -k TestTenantIsolation
```

Or try it live: open the **Tenant Isolation** tab in the Streamlit demo, write as one tenant, and attempt to read it as another.

## Why this matters now

Multi-tenant isolation is the first thing a security questionnaire asks about for any SaaS product, and it's the hardest thing to retrofit correctly once agent memory has grown organically across a codebase with dozens of call sites. Enforcing it at the storage layer — one place, not application-code discipline scattered across every feature — is what makes it possible to actually prove, not just claim, in a SOC2 audit or customer security review.

## Related use cases

- [Purpose-Limited Retrieval](04-purpose-limited-memory-compliance.md) — isolation *within* a tenant, by purpose
- [Tamper-Evident Audit Trail](05-tamper-evident-audit-trail.md) — every audit event is also tenant-scoped

---

Try it yourself: see the [Quickstart](../../README.md#quickstart-populate-the-db--run-the-demo-frontend). Need SSO/RBAC on top of tenant isolation, or help integrating this into an existing multi-tenant platform? See [Enterprise](../../README.md#enterprise).
