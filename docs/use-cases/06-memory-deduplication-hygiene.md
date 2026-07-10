# Use Case: Memory Hygiene — Dedup and Supersede

**The problem in one sentence:** agents that write to memory every session tend to re-write the same fact repeatedly, which quietly bloats storage and retrieval latency — and worse, lets a stale fact keep answering queries after it's been corrected, because nothing told the store the old version was superseded.

## The scenario

A billing agent writes "Customer is on the Team plan" every time it touches the account, across dozens of sessions. Then the customer upgrades to Business. If the new fact is just appended alongside the old ones, a retrieval for "what plan is this customer on" can return either — and a naive "most similar chunk" ranking has no reason to prefer the newer, correct one.

## How Governed Memory handles it

The Write Governor's dedup stage (`core/write_governor/dedup.py`) runs on every write, scoped to `(tenant_id, customer_id)`: it normalizes content (whitespace/case) and checks for an existing match.

- **Exact resubmission** of the same fact: the new write supersedes the old one (`Temporal.superseded_by` set on the prior record, `version` incremented on the new one) instead of creating a duplicate row.
- Retrieval methods already filter `WHERE superseded_by IS NULL`, so superseded versions quietly stop being retrieved without being deleted — you keep the history (useful for the audit trail and provenance graph) without it polluting live results.

```python
from core.models import WriteRequest, Provenance, SourceType

v1 = store.write(WriteRequest(
    tenant_id="acme-corp", customer_id="cust-jane-001",
    agent_id="billing-agent-1", session_id="sess-1",
    content="Customer is on the Team plan.",
    provenance=Provenance(source_type=SourceType.TRUSTED_SYSTEM, source_ref="billing-sync"),
))

v2 = store.write(WriteRequest(
    tenant_id="acme-corp", customer_id="cust-jane-001",
    agent_id="billing-agent-1", session_id="sess-2",
    content="Customer is on the Team plan.",   # same fact, written again
    provenance=Provenance(source_type=SourceType.TRUSTED_SYSTEM, source_ref="billing-sync"),
))

fetched_v1 = store.get(v1.id, "acme-corp")
print(fetched_v1.temporal.superseded_by)  # -> v2.id
print(fetched_v1.temporal.version)        # -> 1

results = store.retrieve(query="what plan", tenant_id="acme-corp",
                          agent_id="billing-agent-1", session_id="sess-3")
# only v2 shows up — v1 is superseded, not deleted
```

## Try it in the demo

```bash
pytest tests/unit/test_dedup.py -v
```

Or write the same content twice through the **Write** tab in the Streamlit demo and check the **Browse** tab — you'll see one live record, not two, with the version history intact if you inspect the raw record.

## Why this matters now

This is the least dramatic use case here, but it compounds silently: agent memory that grows unbounded gets slower to search and — more importantly — accumulates contradictory "facts" that a retrieval-ranking algorithm has no principled way to arbitrate between. Handling this automatically at write time means callers never have to remember to check "does this fact already exist" before writing, which is exactly the kind of discipline that erodes across a team over time if left to application code.

## Related use cases

- [Tamper-Evident Audit Trail](05-tamper-evident-audit-trail.md) — superseded versions remain visible in history, not erased

---

Try it yourself: see the [Quickstart](../../README.md#quickstart-populate-the-db--run-the-demo-frontend).
