"""
Verify a tenant's audit hash chain, and (optionally) inspect the
provenance lineage of a specific memory (E6).

Usage:
    python scripts/verify_audit.py                              # verify the demo tenant
    python scripts/verify_audit.py --tenant my-tenant
    python scripts/verify_audit.py --tenant my-tenant --provenance <memory_id>

Exits with status 1 if the chain is broken (or the given --provenance id
doesn't exist), so this can be wired into CI or a cron job that should
fail loudly on tampering rather than require someone to read the output.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from core.memory_store import MemoryStore, NullEmbeddingProvider
from scripts.demo_data import TENANT_ID


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--tenant", default=TENANT_ID, help=f"tenant to verify (default: {TENANT_ID}, the demo tenant)"
    )
    parser.add_argument(
        "--limit", type=int, default=100_000, help="max audit events to check (default: 100000)"
    )
    parser.add_argument(
        "--provenance",
        metavar="MEMORY_ID",
        help="also print the provenance lineage (ancestors/descendants) for this memory id",
    )
    args = parser.parse_args()

    dsn = os.environ["DATABASE_URL"]
    store = MemoryStore(dsn, NullEmbeddingProvider())  # read-only — no embeddings needed

    print(f"=== Verifying audit chain: tenant '{args.tenant}' ===\n")
    result = store.verify_audit_chain(args.tenant, limit=args.limit)

    ok = result.valid
    if ok:
        print(f"OK — chain intact across all {result.total_events} event(s).")
    else:
        print(f"BROKEN at event index {result.broken_index} (id={result.broken_event_id})")
        print(f"  {result.events_checked}/{result.total_events} event(s) verified before the break.")
        print(f"  reason: {result.reason}")

    if args.provenance:
        print(f"\n=== Provenance for memory '{args.provenance}' ===\n")
        record = store.get(args.provenance, args.tenant)
        if record is None:
            print("  not found in this tenant.")
            ok = False
        else:
            lineage = store.get_provenance(args.provenance, args.tenant)
            print(f"  content:     {record.content[:80]!r}")
            print(f"  ancestors   ({len(lineage['ancestors'])}): {lineage['ancestors']}")
            print(f"  descendants ({len(lineage['descendants'])}): {lineage['descendants']}")

            plan = store.preview_cascade_purge(args.provenance, args.tenant)
            if plan.descendant_count:
                print(
                    f"\n  Note: purge_cascade('{args.provenance}', ...) would also remove "
                    f"{plan.descendant_count} descendant(s): {plan.descendant_ids}"
                )

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
