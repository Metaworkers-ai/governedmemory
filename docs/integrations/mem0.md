# GovernedMemory + Mem0 OSS

GovernedMemory adds trust, policy, quarantine, provenance, and audit around an
existing synchronous Mem0 OSS `Memory` instance. Mem0 remains the system of
record for memory content, embeddings, native IDs, and semantic search.

Supported contract version: **`mem0ai==2.0.12`**. The adapter is intentionally
limited to the OSS Python client; Mem0 Platform `MemoryClient`, async APIs, and
automatic synchronization are not included.

Before using external-memory endpoints outside the local Quickstart, configure
`GOVERNEDMEMORY_OPERATION_SECRET` on the API with a stable, secret value. It
keys tenant-scoped idempotency signatures; changing it invalidates comparisons
for existing in-flight operation keys.

## Install

Start GovernedMemory with the [Quickstart](../../README.md#quickstart), then
install the SDK and its pinned Mem0 compatibility extra:

```bash
pip install -e sdk/python[mem0]
```

Mem0's default `Memory()` configuration uses OpenAI for embeddings and requires
an API key. Export it before running the examples below, or supply your own
Mem0 embedder/LLM configuration:

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

## Before and after

Existing Mem0 code can continue to use `Memory` directly:

```python
from mem0 import Memory

memory = Memory()
memory.add("Customer prefers email", user_id="customer-1")
```

Wrap the same object when the write and search need governance:

```python
from mem0 import Memory
from metaworkers import GovernedMemory, GovernedMem0, Source

memory = GovernedMem0(
    Memory(),
    GovernedMemory("http://localhost:8000", "demo-key"),
    tenant_id="solstice-cloud",
)
result = memory.add(
    "Customer prefers email", user_id="customer-1",
    source=Source(type="user", ref="crm:123"),
)
results = memory.search("contact preference", user_id="customer-1")
```

The adapter verifies that `tenant_id` matches the tenant resolved from the API
key before it performs a governed operation. The API key, not the request body,
is the source of tenant authority.

The adapter calls Mem0 for storage and semantic retrieval. GovernedMemory
evaluates proposed writes, binds the returned Mem0 IDs, and batch-evaluates
search candidates. It never performs a second embedding or semantic search.

## Context mapping

| Mem0 context | GovernedMemory context |
| --- | --- |
| `user_id` | `customer_id` |
| `agent_id` | `agent_id` |
| `run_id` | `session_id` |
| `purpose=` | purpose policy context |
| `Source(...)` | provenance/source type |
| Mem0 result `id` | external memory binding ID |

Pass an explicit `idempotency_key` for writes that may be retried. If omitted,
the adapter generates one and returns it in governance metadata.

The key also serializes the external side effect: exactly one concurrent caller
receives the external-write claim and may call `mem0.add()`. Other concurrent
callers receive `ExternalOperationInProgress`; after the owner completes, a
later call receives the normal completed replay envelope without another Mem0
write. Unrelated keys are not serialized with each other.

The claim window defaults to five minutes. For Mem0 calls that can legitimately
run longer, set `GOVERNEDMEMORY_EXTERNAL_WRITE_CLAIM_TTL_SECONDS` on the API
before starting the stack (allowed range: 30–3600 seconds).

## Governance behavior

- Trusted content is stored in Mem0 and eligible for governed retrieval.
- Untrusted content may be stored in Mem0 but is excluded from governed retrieval.
- Quarantined content remains in Mem0 but is excluded from governed retrieval.
- Explicit policy denial or severe injection does not call `mem0.add()`.
- `untrusted_write_mode="deny"` enables strict rejection of all untrusted writes.

Every result includes a `governance` section with the decision, taint, policy,
correlation ID, external IDs, and stable audit IDs.

Optional content fingerprints are disabled by default. If enabled, configure
`GOVERNEDMEMORY_FINGERPRINT_SECRET` as a private root secret; production never
uses a built-in fallback. Fingerprints are internal idempotency data and are
not returned by the public governance lookup.

## Compatibility modes

- `compatible` (default): preserve existing Mem0 behavior for untracked records,
  but mark them `governance.status="untracked"`.
- `observe`: return untracked records with explicit observations and audit data.
- `strict`: exclude all untracked records.

Known untrusted and quarantined records are excluded in every mode. A
GovernedMemory outage fails closed by default; the adapter never silently
bypasses governance because the API is unavailable.

## Quarantine and recovery

```python
memory.quarantine("mem0-native-id", reason="prompt injection review")
metadata = memory.get_governance("mem0-native-id")
```

Quarantine changes GovernedMemory state only. It does not delete the Mem0
record. If Mem0 succeeds but binding finalization fails, `ExternalBindingPending`
contains the correlation ID, idempotency key, and Mem0 IDs:

```python
memory.retry_binding(
    correlation_id=error.correlation_id,
    external_memory_ids=error.external_memory_ids,
    claim_token=error.claim_token,
)
```

Mem0 may legitimately return `{"results": []}` when no fact is extracted or a
duplicate is skipped. The adapter treats this as a successful governed no-op:
it completes and audits the operation without creating an external binding.

Replaying a completed idempotency key never calls `mem0.add()` again.
GovernedMemory deliberately does not store Mem0's original result payload, so
the replay envelope contains `results: []`,
`governance.idempotent_replay=true`, and
`governance.original_mem0_result_available=false`.

An exception raised after `mem0.add()` begins has an ambiguous external outcome:
Mem0 may have committed before the exception reached the adapter. To preserve
the at-most-once guarantee, that idempotency key becomes terminally failed
instead of automatically repeating the external write. Reconcile the Mem0 state
before choosing a new key. A claim abandoned by a crashed owner likewise expires
to a terminal failure rather than being reassigned and risking a duplicate.

## Troubleshooting

- **API connection refused:** run the Quickstart and verify `/healthz`.
- **401/tenant errors:** use the API key mapped to the configured tenant.
- **No Mem0 IDs:** non-empty result items must contain stable `id` fields.
  A valid empty `results` list is completed as an audited no-op.
- **Untracked search results:** use `strict` for fail-closed retrieval or keep
  `compatible` while migrating existing Mem0 records.
- **Binding pending:** retry using the same correlation ID and returned Mem0 IDs;
  do not call `mem0.add()` again.
- **Write already in progress:** another caller owns this idempotency key. Wait
  for it to complete, then replay the same key to obtain the governed result.
- **Mem0 add failure:** the key becomes terminally failed because the external
  outcome may be ambiguous. Reconcile Mem0 before using a new key; no automatic
  Mem0 delete or unsafe repeat is issued.

## Non-goals

This first adapter does not replace Mem0, add another vector store, create an
embedding pipeline, synchronize all legacy memories, delete Mem0 records
automatically, support Platform `MemoryClient`, support async APIs, or add a
durable worker/outbox.
