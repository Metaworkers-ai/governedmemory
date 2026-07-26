"""Manual validation harness for the GovernedMemory AgentDojo Banking
defense (LLD "Recommended implementation order," item 10: "Validate one
benign and one injected Banking task manually").

This makes a REAL LLM call and a REAL database write. It is intentionally
NOT a pytest test and is NOT run by CI or by anything in tests/ — Step 10
calls for a human to look at real output before Step 11 spends real model
budget on a full sweep, and this script is that human's tool, not a
replacement for their judgment.

Requires:
    - DATABASE_URL env var pointing at a real Postgres+pgvector instance
      (`docker compose -f deploy/docker-compose.yml up -d`, i.e. `make db-up`).
    - pip install -r requirements-agentdojo.txt
    - An API key for whichever model you choose, in the environment
      already (OPENAI_API_KEY, ANTHROPIC_API_KEY, ...) -- this script
      never reads, stores, or touches API keys itself; AgentDojo's own
      `get_llm()` picks them up from the environment the same way it
      always does.

Usage:
    # The Step 10-recommended pair in one run: a read-only benign task
    # (expected to succeed normally) and a privileged task under a real
    # prompt-injection attack (expected to be blocked):
    python scripts/validate_agentdojo_manual.py --recommended-pair --model gpt-4o-mini-2024-07-18

    # Any single task:
    python scripts/validate_agentdojo_manual.py --user-task-id user_task_1 --model gpt-4o-mini-2024-07-18

    # A specific user task under a specific injection task and attack:
    python scripts/validate_agentdojo_manual.py --user-task-id user_task_3 \\
        --injection-task-id injection_task_0 --attack important_instructions \\
        --model gpt-4o-mini-2024-07-18

    # Save the full result artifact(s) as JSON (LLD section 17 shape):
    python scripts/validate_agentdojo_manual.py --recommended-pair --model gpt-4o-mini-2024-07-18 --out results.json

See docs/integrations/agentdojo-manual-validation.md for the checklist of
what to actually look for in the output -- this script prints a summary,
but deciding whether that summary looks *right* is the human part Step 10
is for.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentdojo.agent_pipeline.agent_pipeline import get_llm  # noqa: E402
from agentdojo.attacks.baseline_attacks import DirectAttack, IgnorePreviousAttack  # noqa: E402
from agentdojo.attacks.important_instructions_attacks import (
    ImportantInstructionsAttack,  # noqa: E402
)
from agentdojo.models import MODEL_PROVIDERS, ModelsEnum  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from core.memory_store import MemoryStore, NullEmbeddingProvider, init_db  # noqa: E402
from integrations.agentdojo.registry import RunContextRegistry  # noqa: E402
from integrations.agentdojo.runner import run_governed_banking_task  # noqa: E402

ATTACKS = {
    "important_instructions": ImportantInstructionsAttack,
    "ignore_previous": IgnorePreviousAttack,
    "direct": DirectAttack,
}

# The Step 10-recommended pair, chosen deliberately given the Step 9
# finding (docs/integrations/agentdojo-progress.md section 5): user_task_1
# is read-only (no privileged action at all -- this is the one Banking
# task guaranteed not to be affected by that finding, so it validates the
# "clean allow" path), and user_task_3 pairs a privileged action with a
# real attack, validating the "clean block" path.
RECOMMENDED_PAIR: list[dict[str, Any]] = [
    {
        "user_task_id": "user_task_1",
        "injection_task_id": None,
        "attack": None,
        "label": "benign read-only task (expect: utility=True, privileged_attempts=0)",
    },
    {
        "user_task_id": "user_task_3",
        "injection_task_id": "injection_task_0",
        "attack": "important_instructions",
        "label": "privileged action under a real attack (expect: security=True, blocked_actions>=1)",
    },
]


def run_one(
    suite,
    store: MemoryStore,
    registry: RunContextRegistry,
    *,
    user_task_id: str,
    injection_task_id: str | None,
    attack_name: str | None,
    llm,
    model_name: str,
    seed: int,
) -> dict[str, Any]:
    user_task = suite.user_tasks[user_task_id]
    injection_task = suite.injection_tasks[injection_task_id] if injection_task_id else None

    if injection_task is not None:
        attack_cls = ATTACKS[attack_name or "important_instructions"]
        attack = attack_cls(suite, llm)
        injections = attack.attack(user_task, injection_task)
    else:
        injections = suite.get_injection_vector_defaults()

    return run_governed_banking_task(
        suite,
        user_task,
        injection_task,
        injections,
        llm,
        store,
        agent_id=model_name,
        model=model_name,
        seed=seed,
        registry=registry,
    )


def print_report(label: str, result: dict[str, Any]) -> None:
    g = result["governance"]
    print(f"\n=== {label} ===")
    print(
        f"  user_task_id={result['user_task_id']!r}  injection_task_id={result['injection_task_id']!r}"
    )
    print(
        f"  agentdojo.utility={result['agentdojo']['utility']}  agentdojo.security={result['agentdojo']['security']}"
    )
    print(
        f"  evidence: {g['evidence_count']} total "
        f"(trusted={g['trusted_count']}, untrusted={g['untrusted_count']})"
    )
    print(
        f"  privileged actions: {g['privileged_attempts']} attempted "
        f"(allowed={g['allowed_actions']}, blocked={g['blocked_actions']})"
    )
    print(f"  status={result['status']!r}  infrastructure_errors={result['infrastructure_errors']}")
    print(f"  tenant_id={result['tenant_id']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--user-task-id", help="e.g. user_task_1. Ignored if --recommended-pair is given."
    )
    parser.add_argument(
        "--injection-task-id", default=None, help="e.g. injection_task_0. Optional."
    )
    parser.add_argument("--attack", choices=sorted(ATTACKS), default="important_instructions")
    parser.add_argument(
        "--recommended-pair",
        action="store_true",
        help="Run the Step 10-recommended pair instead of a single task: "
        "one benign read-only task, one privileged task under a real attack.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="An agentdojo.models.ModelsEnum value, e.g. gpt-4o-mini-2024-07-18.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--out", default=None, help="Write the result artifact(s) as JSON to this path."
    )
    args = parser.parse_args()

    if not args.recommended_pair and not args.user_task_id:
        parser.error("provide --user-task-id, or use --recommended-pair")

    try:
        provider = MODEL_PROVIDERS[ModelsEnum(args.model)]
    except ValueError:
        parser.error(
            f"{args.model!r} is not a recognized agentdojo model. "
            f"Valid values: {sorted(m.value for m in ModelsEnum)}"
        )

    load_dotenv()
    dsn = os.environ["DATABASE_URL"]
    init_db(dsn)
    store = MemoryStore(dsn, NullEmbeddingProvider(768))

    llm = get_llm(provider, args.model, None, "tool")

    suite = get_suite("v1.2.2", "banking")
    registry = RunContextRegistry()

    runs = (
        RECOMMENDED_PAIR
        if args.recommended_pair
        else [
            {
                "user_task_id": args.user_task_id,
                "injection_task_id": args.injection_task_id,
                "attack": args.attack,
                "label": args.user_task_id,
            }
        ]
    )

    results = []
    for run in runs:
        result = run_one(
            suite,
            store,
            registry,
            user_task_id=run["user_task_id"],
            injection_task_id=run.get("injection_task_id"),
            attack_name=run.get("attack"),
            llm=llm,
            model_name=args.model,
            seed=args.seed,
        )
        print_report(run["label"], result)
        results.append(result)

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2))
        print(f"\nWrote {len(results)} result artifact(s) to {args.out}")

    print(
        "\nThis script printed what happened. Whether it's *right* is the "
        "human judgment call Step 10 is for -- see "
        "docs/integrations/agentdojo-manual-validation.md for the checklist."
    )


if __name__ == "__main__":
    main()
