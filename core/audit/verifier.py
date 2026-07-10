"""
Hash-chain verifier (E6).

MemoryStore._audit() (E1) computes hash = SHA-256(prev_hash + payload) for
every audit event, chaining each event to the one written before it for the
same tenant. CONTRIBUTING.md has said since E1 that "E6 will add a formal
verifier" — this module is that verifier.

Why "formal" matters: scripts/categorize_demo.py's pre-E6 chain check only
confirmed prev_hash[i] == hash[i-1], i.e. that the chain *links up*. That
catches a deleted or reordered event but not an in-place *tamper*: the audit
table has no DB-level trigger stopping an UPDATE (it's "append-only by
convention", not by enforcement — see CONTRIBUTING.md), so someone could
UPDATE an existing row's outcome/reason/memory_ids directly and the linkage
would still look fine, because prev_hash/hash themselves weren't touched.

verify_chain() recomputes each event's hash from its own stored fields and
compares it to the stored hash, in addition to checking linkage — so a
same-row tamper is caught, not just a missing/reordered one.

compute_event_hash() mirrors MemoryStore._audit()'s payload format exactly.
For this to be verifiable at all, the exact `ts` string folded into that
payload has to be the one actually persisted — previously `_audit()` used a
Python-side timestamp for the hash but a separate `NOW()` for the stored
`ts` column, so the two could never be reconciled after the fact. E6 fixes
that alongside adding this verifier: `_audit()` now stores the same ts
string it hashes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def compute_event_hash(
    prev_hash: str,
    event_id: str,
    tenant_id: str,
    ts: str,
    op: str,
    memory_ids: list[str],
    outcome: str,
) -> str:
    """
    Recompute an audit event's hash from its stored fields.

    Must exactly match the payload format built inline in
    MemoryStore._audit():
        f"{event_id}{tenant_id}{ts}{op}{json.dumps(sorted(memory_ids))}{outcome}"
    If that format ever changes, update both places together.
    """
    payload = f"{event_id}{tenant_id}{ts}{op}{json.dumps(sorted(memory_ids))}{outcome}"
    return hashlib.sha256((prev_hash + payload).encode()).hexdigest()


@dataclass(frozen=True)
class AuditVerificationResult:
    """
    Result of verifying a tenant's audit chain.

    `events_checked` is how many events were confirmed intact before a
    break (or the full count if `valid` is True) — useful for reporting
    "the chain is good up through event N" even when it's broken later.
    """

    valid: bool
    events_checked: int
    total_events: int
    broken_event_id: str | None = None
    broken_index: int | None = None
    reason: str = "chain intact"


def verify_chain(events: list[dict]) -> AuditVerificationResult:
    """
    Verify a tenant's full audit chain.

    `events` must be in chronological order (oldest first) — the order
    they were originally written in. MemoryStore.list_audit() returns
    newest-first, so callers typically do:

        events = list(reversed(store.list_audit(tenant_id, limit=10_000)))
        result = verify_chain(events)

    Each dict needs: id, tenant_id, ts, op, memory_ids, outcome, hash,
    prev_hash — exactly what list_audit() returns per row.
    """
    total = len(events)
    if total == 0:
        return AuditVerificationResult(valid=True, events_checked=0, total_events=0)

    expected_prev = ""
    for i, event in enumerate(events):
        if event["prev_hash"] != expected_prev:
            return AuditVerificationResult(
                valid=False,
                events_checked=i,
                total_events=total,
                broken_event_id=str(event["id"]),
                broken_index=i,
                reason=(
                    f"prev_hash mismatch at index {i} (event {event['id']}) — an event "
                    "was likely deleted, reordered, or inserted out of band"
                ),
            )

        recomputed = compute_event_hash(
            expected_prev,
            str(event["id"]),
            event["tenant_id"],
            _ts_str(event["ts"]),
            event["op"],
            _memory_ids(event["memory_ids"]),
            event["outcome"],
        )
        if recomputed != event["hash"]:
            return AuditVerificationResult(
                valid=False,
                events_checked=i,
                total_events=total,
                broken_event_id=str(event["id"]),
                broken_index=i,
                reason=(
                    f"hash mismatch at index {i} (event {event['id']}) — its stored fields "
                    "don't reproduce its recorded hash, i.e. it was modified in place"
                ),
            )
        expected_prev = event["hash"]

    return AuditVerificationResult(valid=True, events_checked=total, total_events=total)


def _ts_str(ts) -> str:
    return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)


def _memory_ids(v) -> list[str]:
    return v if isinstance(v, list) else json.loads(v)
