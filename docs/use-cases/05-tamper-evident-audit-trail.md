# Use Case: Tamper-Evident Audit Trail for Agent Decisions

**The problem in one sentence:** "what did the agent know when it did that, and who approved it?" is the first question in every AI incident review and every enterprise security questionnaire — and if the answer lives in mutable application logs, it isn't a trustworthy answer.

## The scenario

An agent denies a refund, then three weeks later a customer disputes it. Or an agent approves a refund and finance wants to know what evidence justified it. Or a security review asks: "prove that quarantined/untrusted memories can't silently influence agent decisions." In all three cases, you need a record that (a) definitely captures every decision, not just the ones someone remembered to log, and (b) can't have been edited after the fact to cover up a mistake.

## How Governed Memory provides it

Every write, retrieval, quarantine, purge, and policy decision emits an `AuditEvent` — append-only, and hash-chained: each event's `hash` is computed over its own content plus the previous event's `hash`, so altering or deleting a past event breaks the chain for everything after it.

```python
events = store.list_audit("solstice-cloud", limit=10)
for e in events:
    print(e["op"], e["outcome"], e["reason"], e["hash"][:8], "<-", (e["prev_hash"] or "")[:8])
```

```
policy_decision  deny   taint=untrusted, action='refund' requires trust   a1b2c3d4 <- 9f8e7d6c
retrieve         gated  retrieved 4 of 9 fused candidates; 2 filtered...  9f8e7d6c <- 55443322
write            allow  taint=trusted                                    55443322 <- 11223344
```

Five operation types are tracked (`AuditOp`): `write`, `retrieve`, `quarantine`, `purge`, `policy_decision` — covering both what an agent read and what it was allowed or denied to do with it. `retrieve()` logs an event on *every* call, not just filtered ones, so "the agent asked and got nothing back" is as visible as "the agent asked and got a filtered result."

### Verifying the chain

Because each event embeds the prior event's hash, tampering with row N is detectable by anyone who recomputes hashes forward from N and finds a mismatch with what N+1 recorded as `prev_hash`. This is the same tamper-evidence principle used in certificate transparency logs and blockchain-adjacent audit systems, applied to "what did this agent know and do."

## Try it in the demo

```bash
python scripts/seed_demo.py --reset
python scripts/categorize_demo.py    # prints audit event counts + verifies the hash chain is intact
streamlit run frontend/app.py
```

Open the **Audit Log** tab — every write, search, quarantine, and privilege check from your session shows up in order, with `prev_hash`/`hash` visible so you can confirm the chain yourself.

## Why this matters now

As agents get real permissions, "we have logs somewhere" stops being an adequate answer — enterprise buyers and regulators increasingly want to know the log itself can't have been quietly edited after an incident. A hash-chained audit trail turns "trust us" into something a third party can independently verify, which shortens security review cycles and is table stakes for selling into regulated industries (finance, healthcare, insurance).

## Related use cases

- [Stop Agents From Acting on Poisoned Memory](01-privileged-action-fraud-prevention.md) — every allow/deny decision described there is what populates this log
- [Multi-Tenant Isolation](03-multi-tenant-isolation.md) — the audit log is tenant-scoped the same way memory is

---

Try it yourself: see the [Quickstart](../../README.md#quickstart-populate-the-db--run-the-demo-frontend). Need long-term audit-log export, SIEM integration, or a cascade-purge/provenance-tree view (on the roadmap as E6)? See [Enterprise](../../README.md#enterprise).
