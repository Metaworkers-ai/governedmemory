"""Full pinned Banking benchmark run (LLD "Recommended implementation
order," item 11 -- docs/traction-roadmap.md Ticket 4).

Runs all four LLD section 16 configurations against real user/injection
tasks and a real model, and writes:

    <out-dir>/raw.jsonl       one line per task attempt (build_result_artifact shape + "config" tag)
    <out-dir>/summary.json    metrics per configuration (compute_metrics_by_configuration)
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

    # Targeted Option B regression: the same privileged task benign/attacked.
    python scripts/run_agentdojo_benchmark.py --model gpt-4o-mini-2024-07-18 \
        --user-task-ids user_task_3 --injection-task-ids injection_task_0 \
        --out-dir results/option-b

    # Full sweep: every user task, every injection task, all four configurations.
    python scripts/run_agentdojo_benchmark.py --model gpt-4o-mini-2024-07-18 \\
        --out-dir results/full

    # Only the governed configurations (skip the two baseline ones):
    python scripts/run_agentdojo_benchmark.py --model gpt-4o-mini-2024-07-18 \\
        --configs governed_benign,governed_attacked --out-dir results/governed-only

    # Continue an interrupted sweep without paying for completed attempts again.
    python scripts/run_agentdojo_benchmark.py --model gpt-4o-mini-2024-07-18 \
        --out-dir results/full --resume

Requires DATABASE_URL, an API key for --model's provider, and
pip install -r requirements-agentdojo.txt -- same as
scripts/validate_agentdojo_manual.py.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
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
from integrations.agentdojo.banking_mapping import SOURCE_MAPPING_VERSION  # noqa: E402
from integrations.agentdojo.benchmark import (  # noqa: E402
    CONFIGURATIONS,
    compute_metrics_by_configuration,
)
from integrations.agentdojo.registry import RunContextRegistry  # noqa: E402
from integrations.agentdojo.runner import (  # noqa: E402
    run_baseline_banking_task,
    run_governed_banking_task,
)


def _tag(
    record: dict[str, Any], config: str, run_metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    tagged = {**record, "config": config}
    if run_metadata is not None:
        tagged["run_metadata"] = run_metadata
    return tagged


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_run_metadata(*, include_user_input_in_gate: bool) -> dict[str, Any]:
    """Capture every configuration value needed to interpret/reproduce a run."""
    model_path_value = os.getenv("DETECTION_MODEL_PATH")
    model_path = Path(model_path_value).expanduser() if model_path_value else None
    if model_path is not None and model_path.is_file():
        classifier_source = str(model_path.resolve())
        classifier_sha256 = _sha256(model_path)
    else:
        dataset_path = Path(__file__).resolve().parent.parent / "core/detection/dataset.py"
        classifier_source = "bundled_dataset"
        classifier_sha256 = _sha256(dataset_path)

    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        git_commit = None

    try:
        installed_agentdojo_version = importlib.metadata.version("agentdojo")
    except importlib.metadata.PackageNotFoundError:
        installed_agentdojo_version = None

    return {
        "git_commit": git_commit,
        "agentdojo_version": installed_agentdojo_version,
        "detection_backend": os.getenv("DETECTION_BACKEND", "heuristic"),
        "injection_threshold": float(os.getenv("INJECTION_THRESHOLD", "0.7")),
        "severe_injection_threshold": float(os.getenv("SEVERE_INJECTION_THRESHOLD", "0.95")),
        "classifier_source": classifier_source,
        "classifier_sha256": classifier_sha256,
        "source_mapping_version": SOURCE_MAPPING_VERSION,
        "gate_policy": ("all_evidence" if include_user_input_in_gate else "tool_outputs_only"),
        "attack": "ImportantInstructionsAttack",
        "seed_applied_to_model": False,
        "model_determinism": "not guaranteed; use --repetitions for repeated attempts",
    }


def _attempt_key(record: dict[str, Any]) -> tuple[str, str, str | None, int]:
    return (
        record["config"],
        record["user_task_id"],
        record.get("injection_task_id"),
        int(record.get("seed", 0)),
    )


def _load_existing_records(raw_path: Path) -> list[dict[str, Any]]:
    if not raw_path.exists():
        return []
    records = []
    for line_number, line in enumerate(raw_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{raw_path}:{line_number} is not valid JSONL: {exc}") from exc
    return records


def _error_record(
    *,
    suite,
    model: str,
    seed: int,
    config: str,
    user_task_id: str,
    injection_task_id: str | None,
    exc: Exception,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    return _tag(
        {
            "agentdojo_version": run_metadata["agentdojo_version"],
            "benchmark_version": ".".join(str(part) for part in suite.benchmark_version),
            "suite": suite.name,
            "user_task_id": user_task_id,
            "injection_task_id": injection_task_id,
            "model": model,
            "seed": seed,
            "tenant_id": None,
            "session_id": None,
            "agentdojo": {"utility": None, "security": None},
            "governance": None,
            "status": "infrastructure_error",
            "infrastructure_errors": [f"{type(exc).__name__}: {exc}"],
        },
        config,
        run_metadata,
    )


def _select_ids(
    available: dict[str, Any],
    requested: list[str] | None,
    maximum: int | None,
    *,
    label: str,
) -> list[str]:
    if requested:
        unknown = set(requested) - set(available)
        if unknown:
            raise ValueError(f"unknown {label}(s): {sorted(unknown)}")
        selected = list(dict.fromkeys(requested))
    else:
        selected = list(available)
    return selected[:maximum]


def run_sweep(
    *,
    model: str,
    store: MemoryStore,
    out_dir: Path,
    configs: set[str],
    max_user_tasks: int | None,
    max_injection_tasks: int | None,
    seed: int,
    user_task_ids: list[str] | None = None,
    injection_task_ids: list[str] | None = None,
    resume: bool = False,
    retry_errors: bool = False,
    include_user_input_in_gate: bool = False,
    run_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    provider = MODEL_PROVIDERS[ModelsEnum(model)]
    llm = get_llm(provider, model, None, "tool")
    # See scripts/validate_agentdojo_manual.py's comment on this same line:
    # attacks like ImportantInstructionsAttack require pipeline.name to be
    # set, which AgentPipeline.from_config() normally does but our direct
    # pipeline construction doesn't.
    llm.name = model
    suite = get_suite("v1.2.2", "banking")
    if run_metadata is None:
        run_metadata = collect_run_metadata(include_user_input_in_gate=include_user_input_in_gate)
    if run_metadata["agentdojo_version"] != "0.1.35":
        raise RuntimeError(
            "Step 11 is pinned to agentdojo==0.1.35, but the installed version is "
            f"{run_metadata['agentdojo_version']!r}"
        )
    benchmark_version = ".".join(str(part) for part in suite.benchmark_version)
    if benchmark_version != "1.2.2":
        raise RuntimeError(
            f"Step 11 is pinned to Banking benchmark 1.2.2, got {benchmark_version!r}"
        )
    registry = RunContextRegistry()

    selected_user_task_ids = _select_ids(
        suite.user_tasks, user_task_ids, max_user_tasks, label="user task"
    )
    selected_injection_task_ids = _select_ids(
        suite.injection_tasks,
        injection_task_ids,
        max_injection_tasks,
        label="injection task",
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "raw.jsonl"
    records = _load_existing_records(raw_path) if resume else []
    if resume and retry_errors:

        def selected_error(record: dict[str, Any]) -> bool:
            if record.get("status") != "infrastructure_error":
                return False
            if record.get("seed", 0) != seed or record.get("config") not in configs:
                return False
            if record.get("user_task_id") not in selected_user_task_ids:
                return False
            injection_task_id = record.get("injection_task_id")
            return injection_task_id is None or injection_task_id in selected_injection_task_ids

        # Remove only the failed attempts selected by this invocation. Keep
        # errors from other seeds/configurations/task subsets in the JSONL.
        records = [record for record in records if not selected_error(record)]
        raw_path.write_text("".join(json.dumps(record) + "\n" for record in records))
    existing_keys = {_attempt_key(record) for record in records}

    with raw_path.open("a" if resume else "w") as raw_file:

        def emit(record: dict[str, Any]) -> None:
            records.append(record)
            raw_file.write(json.dumps(record) + "\n")
            raw_file.flush()

        total = len(selected_user_task_ids) * (
            ("baseline_benign" in configs) + ("governed_benign" in configs)
        ) + len(selected_user_task_ids) * len(selected_injection_task_ids) * (
            ("baseline_attacked" in configs) + ("governed_attacked" in configs)
        )
        done = 0

        def execute(config: str, user_task_id: str, injection_task_id: str | None, operation):
            nonlocal done
            key = (config, user_task_id, injection_task_id, seed)
            if key in existing_keys:
                print(f"[skip] {config} {user_task_id} x {injection_task_id or 'none'}")
                return
            done += 1
            print(f"[{done}/{total}] {config} {user_task_id} x {injection_task_id or 'none'}")
            try:
                record = _tag(operation(), config, run_metadata)
            except Exception as exc:
                record = _error_record(
                    suite=suite,
                    model=model,
                    seed=seed,
                    config=config,
                    user_task_id=user_task_id,
                    injection_task_id=injection_task_id,
                    exc=exc,
                    run_metadata=run_metadata,
                )
            emit(record)

        for user_task_id in selected_user_task_ids:
            user_task = suite.user_tasks[user_task_id]
            defaults = suite.get_injection_vector_defaults()

            if "baseline_benign" in configs:
                execute(
                    "baseline_benign",
                    user_task_id,
                    None,
                    lambda: run_baseline_banking_task(
                        suite, user_task, None, defaults, llm, model=model, seed=seed
                    ),
                )

            if "governed_benign" in configs:
                execute(
                    "governed_benign",
                    user_task_id,
                    None,
                    lambda: run_governed_banking_task(
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
                        include_user_input_in_gate=include_user_input_in_gate,
                    ),
                )

            for injection_task_id in selected_injection_task_ids:
                injection_task = suite.injection_tasks[injection_task_id]

                if "baseline_attacked" in configs:

                    def run_baseline_attacked():
                        attack = ImportantInstructionsAttack(suite, llm)
                        injections = attack.attack(user_task, injection_task)
                        return run_baseline_banking_task(
                            suite,
                            user_task,
                            injection_task,
                            injections,
                            llm,
                            model=model,
                            seed=seed,
                        )

                    execute(
                        "baseline_attacked",
                        user_task_id,
                        injection_task_id,
                        run_baseline_attacked,
                    )

                if "governed_attacked" in configs:

                    def run_governed_attacked():
                        attack = ImportantInstructionsAttack(suite, llm)
                        injections = attack.attack(user_task, injection_task)
                        return run_governed_banking_task(
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
                            include_user_input_in_gate=include_user_input_in_gate,
                        )

                    execute(
                        "governed_attacked",
                        user_task_id,
                        injection_task_id,
                        run_governed_attacked,
                    )

    return records


def write_methodology_report(
    out_dir: Path,
    model: str,
    metrics: dict[str, dict[str, Any]],
    run_metadata: dict[str, Any] | None = None,
) -> None:
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
    if run_metadata:
        lines[4:4] = [
            f"Git commit: `{run_metadata['git_commit']}`",
            f"Detection backend: `{run_metadata['detection_backend']}`",
            f"Injection threshold: `{run_metadata['injection_threshold']}`",
            f"Classifier SHA-256: `{run_metadata['classifier_sha256']}`",
            f"Source mapping: `{run_metadata['source_mapping_version']}`",
            f"Gate policy: `{run_metadata['gate_policy']}`",
            "",
        ]
    metric_names = [
        "record_count",
        "valid_record_count",
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
    parser.add_argument(
        "--detection-backend",
        choices=("heuristic", "classifier", "ensemble"),
        default="ensemble",
        help="Injection detector used by governed writes (default: ensemble).",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Repeat the sweep with incrementing recorded seeds; model determinism is not guaranteed.",
    )
    parser.add_argument(
        "--user-task-ids",
        default=None,
        help="Comma-separated explicit user task ids (for example user_task_0,user_task_3).",
    )
    parser.add_argument(
        "--injection-task-ids",
        default=None,
        help="Comma-separated explicit injection task ids.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Append to raw.jsonl and skip attempts already present.",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="With --resume, rerun prior infrastructure-error attempts.",
    )
    parser.add_argument(
        "--include-user-input-in-gate",
        action="store_true",
        help="Use strict all-evidence gating instead of AgentDojo's default tool-output-only gate.",
    )
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be >= 1")

    configs = set(args.configs.split(","))
    unknown = configs - set(CONFIGURATIONS)
    if unknown:
        parser.error(f"unknown configuration(s) {sorted(unknown)}; valid: {CONFIGURATIONS}")

    load_dotenv()
    os.environ["DETECTION_BACKEND"] = args.detection_backend
    dsn = os.environ["DATABASE_URL"]
    init_db(dsn)
    store = MemoryStore(dsn, NullEmbeddingProvider(768))
    run_metadata = collect_run_metadata(include_user_input_in_gate=args.include_user_input_in_gate)
    run_metadata["repetitions"] = args.repetitions
    run_metadata["starting_recorded_seed"] = args.seed
    (args.out_dir / "run-metadata.json").parent.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "run-metadata.json").write_text(json.dumps(run_metadata, indent=2))

    started = time.time()
    records: list[dict[str, Any]] = []
    for repetition in range(args.repetitions):
        records = run_sweep(
            model=args.model,
            store=store,
            out_dir=args.out_dir,
            configs=configs,
            max_user_tasks=args.max_user_tasks,
            max_injection_tasks=args.max_injection_tasks,
            seed=args.seed + repetition,
            user_task_ids=args.user_task_ids.split(",") if args.user_task_ids else None,
            injection_task_ids=(
                args.injection_task_ids.split(",") if args.injection_task_ids else None
            ),
            resume=args.resume or repetition > 0,
            retry_errors=args.retry_errors and repetition == 0,
            include_user_input_in_gate=args.include_user_input_in_gate,
            run_metadata=run_metadata,
        )
    elapsed = time.time() - started

    metrics = compute_metrics_by_configuration(records)
    (args.out_dir / "summary.json").write_text(json.dumps(metrics, indent=2))
    write_methodology_report(args.out_dir, args.model, metrics, run_metadata)

    print(f"\n{len(records)} task attempts in {elapsed:.0f}s. Wrote:")
    print(f"  {args.out_dir / 'raw.jsonl'}")
    print(f"  {args.out_dir / 'summary.json'}")
    print(f"  {args.out_dir / 'methodology.md'}")


if __name__ == "__main__":
    main()
