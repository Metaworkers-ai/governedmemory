"""One-off inspection script: dumps a memory record's full content, taint,
and injection score -- exactly what verify_audit.py's --provenance flag
doesn't show (it truncates content to 80 chars and doesn't print
trust/injection_score at all).

Usage:
    python scripts/inspect_memory.py --tenant agentdojo:1.2.2:banking:69c3f47f35b0409eabb8dd1fbdc4066b \\
        --memory-id ac7dda98-1491-42df-b947-9c64037ff545 ac109368-e9d8-460a-b8a8-a637b9ade400

Not part of the shipped integration -- a debugging tool, same category as
scripts/debug_transcript.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from core.memory_store import MemoryStore, NullEmbeddingProvider


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--memory-id", nargs="+", required=True, help="one or more memory ids to inspect")
    args = parser.parse_args()

    dsn = os.environ["DATABASE_URL"]
    store = MemoryStore(dsn, NullEmbeddingProvider())  # read-only -- no embeddings needed

    for memory_id in args.memory_id:
        record = store.get(memory_id, args.tenant)
        print(f"\n{'=' * 70}")
        print(f"memory_id: {memory_id}")
        if record is None:
            print("  NOT FOUND in this tenant.")
            continue

        print(f"  source_type:     {record.provenance.source_type.value}")
        print(f"  source_ref:      {record.provenance.source_ref}")
        print(f"  taint:           {record.trust.taint.value}")
        print(f"  injection_score: {record.trust.injection_score}")
        print(f"  policy_id:       {record.purpose.policy_id}")
        print("  content:")
        print("  " + "-" * 68)
        for line in record.content.splitlines():
            print(f"  | {line}")
        print("  " + "-" * 68)


if __name__ == "__main__":
    main()