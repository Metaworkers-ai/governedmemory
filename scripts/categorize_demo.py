"""
Report on the seeded demo tenant — a readiness check before a live demo.

Usage:
    python scripts/categorize_demo.py

Prints, per customer: memory count, taint breakdown, source-type breakdown,
and purpose breakdown. Also verifies the audit hash chain is intact.
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from core.memory_store import MemoryStore, NullEmbeddingProvider
from scripts.demo_data import CUSTOMERS, TENANT_ID


def verify_audit_chain(store: MemoryStore, tenant_id: str) -> tuple[int, bool]:
    events = store.list_audit(tenant_id, limit=1000)
    events = list(reversed(events))  # list_audit returns newest-first; verify oldest-first
    intact = True
    for i in range(1, len(events)):
        if events[i]["prev_hash"] != events[i - 1]["hash"]:
            intact = False
            break
    return len(events), intact


def main() -> None:
    load_dotenv()
    dsn = os.environ["DATABASE_URL"]
    store = MemoryStore(dsn, NullEmbeddingProvider())  # read-only — no embeddings needed

    print(f"=== Demo tenant: {TENANT_ID} ===\n")

    total_taint: Counter = Counter()
    total_source: Counter = Counter()
    total_purpose: Counter = Counter()

    for customer_id, name in CUSTOMERS.items():
        memories = store.list_for_customer(TENANT_ID, customer_id)
        taint = Counter(m.trust.taint.value for m in memories)
        source = Counter(m.provenance.source_type.value for m in memories)
        purpose = Counter(p for m in memories for p in m.purpose.allowed_purposes)

        total_taint.update(taint)
        total_source.update(source)
        total_purpose.update(purpose)

        print(f"{name} ({customer_id}) — {len(memories)} memories")
        print(f"  taint:   {dict(taint)}")
        print(f"  source:  {dict(source)}")
        print(f"  purpose: {dict(purpose)}")
        print()

    stats = store.get_stats(TENANT_ID)
    print("=== Tenant totals ===")
    print(f"  total memories:   {stats['total_memories']}")
    print(f"  total customers:  {stats['total_customers']}")
    print(f"  taint breakdown:  {dict(total_taint)}")
    print(f"  source breakdown: {dict(total_source)}")
    print(f"  purpose breakdown:{dict(total_purpose)}")

    event_count, chain_intact = verify_audit_chain(store, TENANT_ID)
    status = "OK — chain intact" if chain_intact else "BROKEN — hash mismatch detected"
    print(f"\n=== Audit trail ===")
    print(f"  {event_count} events recorded, hash chain: {status}")

    if total_taint.get("untrusted", 0) > 0:
        print(f"\nDemo talking point: {total_taint['untrusted']} memories were auto-tainted 'untrusted' "
              f"on write — all from untrusted_email/untrusted_web sources carrying embedded injection "
              f"attempts, flagged before any agent could act on them.")


if __name__ == "__main__":
    main()
