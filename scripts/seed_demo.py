"""
Populate the demo tenant with the 50-memory dataset from demo_data.py.

Usage:
    python scripts/seed_demo.py            # add demo data (skips if already seeded)
    python scripts/seed_demo.py --reset     # wipe the demo tenant first, then reseed

Run this before showing the frontend to a customer, then open:
    streamlit run frontend/app.py
and set Tenant ID to "solstice-cloud" in the sidebar (it's now the default).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from core.memory_store import MemoryStore, NullEmbeddingProvider, init_db
from core.models import Provenance, Purpose, Temporal, WriteRequest
from scripts.demo_data import CUSTOMERS, DEMO_POLICY, MEMORIES, TENANT_ID


def get_embedder():
    try:
        from core.memory_store import SentenceTransformerProvider
        print("Using SentenceTransformerProvider for real semantic embeddings (this loads a model, ~5-10s)...")
        return SentenceTransformerProvider()
    except ImportError:
        print("sentence-transformers not installed — using NullEmbeddingProvider (zero vectors).")
        print("For real vector search in the demo: pip install -r requirements-embed-local.txt")
        return NullEmbeddingProvider()


def reset_tenant(dsn: str, tenant_id: str) -> None:
    import psycopg2
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM memory WHERE tenant_id = %s", (tenant_id,))
        deleted_memories = cur.rowcount
        cur.execute("DELETE FROM audit WHERE tenant_id = %s", (tenant_id,))
        deleted_audit = cur.rowcount
    conn.close()
    print(f"Reset: deleted {deleted_memories} memories and {deleted_audit} audit events for tenant '{tenant_id}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Delete existing demo tenant data before seeding.")
    args = parser.parse_args()

    load_dotenv()
    dsn = os.environ["DATABASE_URL"]
    print(dsn)
    init_db(dsn)

    if args.reset:
        reset_tenant(dsn, TENANT_ID)

    store = MemoryStore(dsn, get_embedder())

    taint_counts = {"trusted": 0, "untrusted": 0, "quarantined": 0}
    for m in MEMORIES:
        req = WriteRequest(
            tenant_id=TENANT_ID,
            customer_id=m["customer_id"],
            agent_id=m["agent_id"],
            session_id=m["session_id"],
            content=m["content"],
            provenance=Provenance(
                source_type=m["source_type"],
                source_ref=m["source_ref"],
                confidence=m["confidence"],
            ),
            purpose=Purpose(allowed_purposes=m["purposes"]),
            temporal=Temporal(valid_until=m.get("valid_until")),
        )
        record = store.write(req)
        taint_counts[record.trust.taint.value] += 1

    store.upsert_policy(DEMO_POLICY)

    print(f"\nSeeded {len(MEMORIES)} memories for tenant '{TENANT_ID}' across {len(CUSTOMERS)} customers.")
    print(f"  trusted:     {taint_counts['trusted']}")
    print(f"  untrusted:   {taint_counts['untrusted']}  (auto-tainted — untrusted_email / untrusted_web sources)")
    print(f"  quarantined: {taint_counts['quarantined']}")
    print("\nConfigured a policy (E4): purpose='sales' now only allows user/trusted_system source")
    print("types — retrieve() with purpose='sales' will exclude the two agent-generated sales summaries.")
    print("\nRun scripts/categorize_demo.py for a full breakdown, or open the frontend:")
    print("  streamlit run frontend/app.py")


if __name__ == "__main__":
    main()
