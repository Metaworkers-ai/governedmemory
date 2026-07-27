"""Full pinned Banking benchmark run (LLD "Recommended implementation
order," item 11 -- docs/traction-roadmap.md Ticket 4).

Runs all four LLD section 16 configurations against real user/injection
tasks and a real model, and writes:

    <out-dir>/raw.jsonl       one line per task attempt (build_result_artifact shape + "config" tag)
    <out-dir>/summary.json    the nine metrics per configuration (compute_metrics_by_configuration)
    <out-dir>/methodology.md  a human-readable write-up of what ran and what came out

This makes many real LLM calls and real database writes -- it is
intentionally NOT a pytest test. Read
docs/integrations/agentdojo-progress.md section 5 before running this:
the false-block finding there predicts what configuration 2's numbers
will look like, and Step 10's manual validation should have already been
run at least once before this.

Usage:
    # Smoke test: 2 benign tasks, 1 attacked pair, both baseline and governed.
    python scripts/run_agentdojo_benchmark.py --model gpt-4o-mini-2024-07-18 \\
        --max-user-tasks 2 --max-injection-tasks 1 --out-dir results/smoke

    # Full sweep: every user task, every injection task, all four configurations.
    python scripts/run_agentdojo_benchmark.py --model gpt-4o-mini-2024-07-18 \\
        --out-dir results/full

    # Only the governed configurations (skip the two baseline ones):
    python scripts/run_agentdojo_benchmark.py --model gpt-4o-mini-2024-07-18 \\
        --configs governed_benign,governed_attacked --out-dir results/governed-only

Requires DATABASE_URL, an API key for --model's provider, and
pip install -r requirements-agentdojo.txt -- same as
scripts/validate_agentdojo_manual.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentdojo.agent_pipeline.agent_pipeline import get_llm  # noqa: E402
from agentdojo.attacks.important_instructions_attacks import (
    ImportantInstructionsAttack,  # noqa: E402
)
from agentdojo.models import MODEL_PROVIDERS, ModelsEnum  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from core.memory_store import MemoryStore, NullEmbeddingProvider, init_db  # noqa: E402
from integrations.agentdojo.benchmark import (  # noqa: E402
    CONFIGURATIONS,
    compute_metrics_by_configuration,
)
from integrations.agentdojo.registry import RunContextRegistry  # noqa: E402
from integrations.agentdojo.runner import (  # noqa: E402
    run_baseline_banking_task,
    run_governed_banking_task,
)


def _tag(record: dict[str, Any], config: str) -> dict[str, Any]:
    return {**record, "config": config}


def run_sweep(
    *,
    model: str,
    store: MemoryStore,
    out_dir: Path,
    configs: set[str],
    max_user_tasks: int | None,
    max_injection_tasks: int | None,
    seed: int,
) -> list[dict[str, Any]]:
    provider = MODEL_PROVIDERS[ModelsEnum(model)]
    llm = get_llm(provider, model, None, "tool")
    # See scripts/validate_agentdojo_manual.py's comment on this same line:
    # attacks like ImportantInstructionsAttack require pipeline.name to be
    # set, which AgentPipeline.from_config() normally does but our direct
    # pipeline construction doesn't.
    llm.name = model
    suite = get_suite("v1.2.2", "banking")
    registry = RunContextRegistry()

    user_task_ids = list(suite.user_tasks)[:max_user_tasks]
    injection_task_ids = list(suite.injection_tasks)[:max_injection_tasks]

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "raw.jsonl"
    records: list[dict[str, Any]] = []

    with raw_path.open("w") as raw_file:

        def emit(record: dict[str, Any]) -> None:
            records.append(record)
            raw_file.write(json.dumps(record) + "\n")
            raw_file.flush()

        total = len(user_task_ids) * (
            ("baseline_benign" in configs) + ("governed_benign" in configs)
        ) + len(user_task_ids) * len(injection_task_ids) * (
            ("baseline_attacked" in configs) + ("governed_attacked" in configs)
        )
        done = 0

        for user_task_id in user_task_ids:
            user_task = suite.user_tasks[user_task_id]
            defaults = suite.get_injection_vector_defaults()

            if "baseline_benign" in configs:
                done += 1
                print(f"[{done}/{total}] baseline_benign {user_task_id}")
                record = run_baseline_banking_task(
                    suite, user_task, None, defaults, llm, model=model, seed=seed
                )
                emit(_tag(record, "baseline_benign"))

            if "governed_benign" in configs:
                done += 1
                print(f"[{done}/{total}] governed_benign {user_task_id}")
                record = run_governed_banking_task(
                    suite,
                    user_task,
                    None,
                    defaults,
                    llm,
                    store,
                    agent_id=model,
                    model=model,
                    seed=seed,
                    registry=registry,
                )
                emit(_tag(record, "governed_benign"))

            for injection_task_id in injection_task_ids:
                injection_task = suite.injection_tasks[injection_task_id]

                if "baseline_attacked" in configs:
                    done += 1
                    print(
                        f"[{done}/{total}] baseline_attacked {user_task_id} x {injection_task_id}"
                    )
                    attack = ImportantInstructionsAttack(suite, llm)
                    injections = attack.attack(user_task, injection_task)
                    record = run_baseline_banking_task(
                        suite, user_task, injection_task, injections, llm, model=model, seed=seed
                    )
                    emit(_tag(record, "baseline_attacked"))

                if "governed_attacked" in configs:
                    done += 1
                    print(
                        f"[{done}/{total}] governed_attacked {user_task_id} x {injection_task_id}"
                    )
                    attack = ImportantInstructionsAttack(suite, llm)
                    injections = attack.attack(user_task, injection_task)
                    record = run_governed_banking_task(
                        suite,
                        user_task,
                        injection_task,
                        injections,
                        llm,
                        store,
                        agent_id=model,
                        model=model,
                        seed=seed,
                        registry=registry,
                    )
                    emit(_tag(record, "governed_attacked"))

    return records


def write_methodology_report(out_dir: Path, model: str, metrics: dict[str, dict[str, Any]]) -> None:
    lines = [
        "# GovernedMemory AgentDojo Banking benchmark — results",
        "",
        f"Model: `{model}`",
        "Suite: Banking v1.2.2, agentdojo==0.1.35",
        "",
        "Only a pre-execution policy denial counts as a GovernedMemory block "
        "(LLD section 16) — injection detection or taint assignment alone does not.",
        "",
        "| Metric | 1. baseline_benign | 2. governed_benign | 3. baseline_attacked | 4. governed_attacked |",
        "|---|---|---|---|---|",
    ]
    metric_names = [
        "record_count",
        "utility_success_rate",
        "security_success_rate",
        "targeted_asr",
        "governance_block_rate",
        "untrusted_evidence_rate",
        "false_block_rate",
        "infrastructure_error_rate",
    ]
    for name in metric_names:
        row = [name]
        for config in CONFIGURATIONS:
            value = metrics[config][name]
            row.append(
                "—"
                if value is None
                else (f"{value:.3f}" if isinstance(value, float) else str(value))
            )
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("## Latency")
    lines.append("")
    for config in CONFIGURATIONS:
        for latency_name in ("write_latency_ms", "gate_latency_ms"):
            summary = metrics[config][latency_name]
            if summary is None:
                continue
            lines.append(
                f"- **{config} / {latency_name}**: mean={summary['mean_ms']:.1f}ms, "
                f"median={summary['median_ms']:.1f}ms, p95={summary['p95_ms']:.1f}ms, "
                f"n={summary['count']}"
            )

    (out_dir / "methodology.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--configs",
        default=",".join(CONFIGURATIONS),
        help=f"Comma-separated subset of {CONFIGURATIONS} to run.",
    )
    parser.add_argument("--max-user-tasks", type=int, default=None, help="Limit for a smoke test.")
    parser.add_argument(
        "--max-injection-tasks", type=int, default=None, help="Limit for a smoke test."
    )
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    configs = set(args.configs.split(","))
    unknown = configs - set(CONFIGURATIONS)
    if unknown:
        parser.error(f"unknown configuration(s) {sorted(unknown)}; valid: {CONFIGURATIONS}")

    load_dotenv()
    dsn = os.environ["DATABASE_URL"]
    init_db(dsn)
    store = MemoryStore(dsn, NullEmbeddingProvider(768))

    started = time.time()
    records = run_sweep(
        model=args.model,
        store=store,
        out_dir=args.out_dir,
        configs=configs,
        max_user_tasks=args.max_user_tasks,
        max_injection_tasks=args.max_injection_tasks,
        seed=args.seed,
    )
    elapsed = time.time() - started

    metrics = compute_metrics_by_configuration(records)
    (args.out_dir / "summary.json").write_text(json.dumps(metrics, indent=2))
    write_methodology_report(args.out_dir, args.model, metrics)

    print(f"\n{len(records)} task attempts in {elapsed:.0f}s. Wrote:")
    print(f"  {args.out_dir / 'raw.jsonl'}")
    print(f"  {args.out_dir / 'summary.json'}")
    print(f"  {args.out_dir / 'methodology.md'}")


if __name__ == "__main__":
    main()