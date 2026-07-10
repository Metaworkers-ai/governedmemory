# Use Case: Purpose-Limited Retrieval (Need-to-Know AI)

**The problem in one sentence:** a memory collected for one purpose (support, a call log) shouldn't silently become the evidence base for a different, higher-stakes purpose (a sales pitch, a pricing decision) — but once everything lands in the same vector store, nothing stops it from doing exactly that.

This is the agent-memory analogue of GDPR/CCPA's purpose-limitation principle: data collected for X shouldn't be reused for Y without a deliberate decision that Y is an acceptable use.

## The scenario

A sales agent for account `David Okafor` has memory from several sources: a call log, a CRM sync, a usage-analytics tool — and its own prior summary of David, written by the sales agent itself:

> Sales agent summary: David is price-sensitive but values security features; lead with SOC2 compliance messaging.

That's the agent's own inference, not something David said or a system verified. If the next sales agent instance treats its predecessor's inference as equally authoritative to CRM data, you get compounding hallucination — one agent's guess becomes "known fact" for the next.

## How Governed Memory enforces this

Two layers, at different granularities:

**Record-level** (`Purpose.allowed_purposes`, enforced in the Retrieval Engine's privilege gate, E3): a memory can declare which purposes it's usable for. Empty means open to any purpose.

**Tenant-level policy** (`PurposeBinding`, enforced by the Policy Engine, E4): the tenant can additionally restrict which *source types* are acceptable evidence for a given purpose — independent of what any individual record claims about itself.

```python
from core.models import Policy, PurposeBinding

store.upsert_policy(Policy(
    id="default",
    tenant_id="solstice-cloud",
    purpose_bindings=[
        PurposeBinding(purpose="sales", allowed_source_types=["user", "trusted_system"]),
    ],
))
```

This says: for the `sales` purpose, only memories sourced directly from the user or a trusted system count — not `agent_derived` inferences, no matter what purpose tag they carry. Now:

```python
results = store.retrieve(
    query="pricing sensitivity and objections",
    tenant_id="solstice-cloud",
    agent_id="sales-agent-2",
    session_id="sess-david-05",
    purpose="sales",
)
# the AGENT_DERIVED "sales agent summary" record is excluded — even though
# it's fully trusted and even though its own allowed_purposes includes "sales"
```

Nothing was deleted or quarantined — the record is fine, just not eligible evidence for this particular purpose. Ask without a purpose, or ask for a purpose without a binding configured, and it's included as normal; this is opt-in governance, not a blanket restriction.

## Try it in the demo

```bash
python scripts/seed_demo.py --reset       # seeds this exact policy
streamlit run frontend/app.py
```

Open **Search**, query anything relevant to David Okafor or Fatima Ali with purpose = `sales`. Compare results with and without the purpose set — the two `agent_derived` "sales agent summary" records disappear when purpose-limited. The "why excluded" panel shows `excluded by policy engine (E4)` versus `excluded by privilege gate (E3)` versus simply cut by the result-count limit, so you can see exactly which layer made the call.

## Why this matters now

As agents get wired into more workflows, the same memory store increasingly backs multiple purposes — support, sales, billing, retention — often for the same customer. Without purpose limitation, whichever agent writes first effectively sets the "ground truth" for every agent that reads after it, including agents doing something much more consequential than the one that wrote it. This is also a direct, concrete answer to a compliance reviewer asking how purpose limitation is enforced for AI-driven decisions — not a policy document, a query-time gate you can point to.

## Related use cases

- [Stop Agents From Acting on Poisoned Memory](01-privileged-action-fraud-prevention.md) — the taint-based counterpart to purpose-based gating
- [Multi-Tenant Isolation](03-multi-tenant-isolation.md) — isolation across tenants; this is isolation across purposes within one tenant

---

Try it yourself: see the [Quickstart](../../README.md#quickstart-populate-the-db--run-the-demo-frontend). Need a managed policy console or RBAC on top of purpose bindings? See [Enterprise](../../README.md#enterprise).
