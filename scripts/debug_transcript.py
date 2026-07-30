"""One-off debug script: prints the actual model transcript for one task.

This exists because agentdojo==0.1.35's TaskSuite.run_task_with_pipeline
has a `verbose` parameter that's documented but never actually used in
the function body -- and the full conversation (`messages`) is a local
variable inside that function, never returned or exposed. This script
calls the pipeline directly, the same way run_task_with_pipeline does
internally, but prints messages instead of discarding them.

Not part of the shipped integration -- delete this file when you're done
debugging, or keep it around for future manual checks.

Usage:
    python scripts/debug_transcript.py --user-task-id user_task_3 --model gpt-4o-2024-05-13
    python scripts/debug_transcript.py --user-task-id user_task_3 --injection-task-id injection_task_0 --model gpt-4o-2024-05-13
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from agentdojo.agent_pipeline.agent_pipeline import get_llm
from agentdojo.attacks.important_instructions_attacks import ImportantInstructionsAttack
from agentdojo.models import MODEL_PROVIDERS, ModelsEnum
from agentdojo.task_suite.load_suites import get_suite

from core.memory_store import MemoryStore, NullEmbeddingProvider, init_db
from integrations.agentdojo.banking_policy import ensure_banking_policy
from integrations.agentdojo.context import RunGovernanceContext
from integrations.agentdojo.identity import generate_run_identity
from integrations.agentdojo.registry import RunContextRegistry
from integrations.agentdojo.runner import build_governed_pipeline, make_governed_runtime_class


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-task-id", required=True)
    parser.add_argument("--injection-task-id", default=None)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    load_dotenv()
    dsn = os.environ["DATABASE_URL"]
    init_db(dsn)
    store = MemoryStore(dsn, NullEmbeddingProvider(768))

    provider = MODEL_PROVIDERS[ModelsEnum(args.model)]
    llm = get_llm(provider, args.model, None, "tool")
    llm.name = args.model  # required for ImportantInstructionsAttack's model-name lookup

    suite = get_suite("v1.2.2", "banking")
    user_task = suite.user_tasks[args.user_task_id]
    injection_task = suite.injection_tasks[args.injection_task_id] if args.injection_task_id else None

    if injection_task is not None:
        attack = ImportantInstructionsAttack(suite, llm)
        injections = attack.attack(user_task, injection_task)
    else:
        injections = suite.get_injection_vector_defaults()

    identity = generate_run_identity(
        benchmark_version="1.2.2",
        suite=suite.name,
        user_task_id=user_task.ID,
        agent_id=args.model,
        injection_task_id=injection_task.ID if injection_task else None,
    )
    ensure_banking_policy(store, identity.tenant_id)
    context = RunGovernanceContext(identity=identity)

    raw_environment = suite.load_and_inject_default_environment(injections)
    task_environment = user_task.init_environment(raw_environment)

    registry = RunContextRegistry()
    pipeline = build_governed_pipeline(store, llm, registry=registry)
    runtime_class = make_governed_runtime_class(store, registry=registry)
    runtime = runtime_class(suite.tools)

    with registry.run(task_environment, context):
        _, _, _, messages, _ = pipeline.query(user_task.PROMPT, runtime, task_environment)

    print(f"\n{'=' * 70}\nTRANSCRIPT for {args.user_task_id}\n{'=' * 70}")
    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            text = "".join(block.get("content", "") for block in (msg.get("content") or []) if block)
            print(f"\n--- assistant ---\n{text}")
            for call in msg.get("tool_calls") or []:
                print(f"  [tool_call] {call.function}({call.args})")
        elif role == "tool":
            error = msg.get("error")
            text = "".join(block.get("content", "") for block in (msg.get("content") or []) if block)
            print(f"\n--- tool result (error={error}) ---\n{text[:500]}")
        elif role == "user":
            text = "".join(block.get("content", "") for block in (msg.get("content") or []) if block)
            print(f"\n--- user ---\n{text}")
        elif role == "system":
            print("\n--- system --- (prompt omitted)")

    print(f"\n{'=' * 70}")
    print(f"Evidence written: {len(context.evidence)}, Actions: {len(context.actions)}")
    for action in context.actions:
        print(f"  action: {action.tool_name} allowed={action.allowed} reason={action.reason!r}")


if __name__ == "__main__":
    main()