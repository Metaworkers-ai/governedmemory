"""Run native AgentDojo defenses on the pinned Banking suite.

This complements ``run_agentdojo_benchmark.py`` by producing normalized
benign utility, attacked utility, and targeted ASR for AgentDojo's own
defenses under the same task/attack matrix used for GovernedMemory.

Example:

    GEMINI_FORCE_IPV4=1 python scripts/run_agentdojo_defense_comparison.py \
        --model gemini-2.5-flash \
        --defenses repeat_user_prompt,spotlighting_with_delimiting \
        --out-dir results/gemini-native-defenses-r1
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentdojo.agent_pipeline.agent_pipeline import (  # noqa: E402
    DEFENSES,
    AgentPipeline,
    PipelineConfig,
)
from agentdojo.attacks.important_instructions_attacks import (  # noqa: E402
    ImportantInstructionsAttack,
)
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from scripts.run_agentdojo_benchmark import (  # noqa: E402
    ATTACK_PIPELINE_NAMES,
    build_llm,
)

GEMINI_COMPATIBLE_DEFENSES = frozenset(
    {
        "repeat_user_prompt",
        "spotlighting_with_delimiting",
        "transformers_pi_detector",
    }
)


def _key(record: dict[str, Any]) -> tuple[str, str, str | None]:
    return record["defense"], record["user_task_id"], record.get("injection_task_id")


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def compute_comparison_metrics(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for defense in sorted({record["defense"] for record in records}):
        selected = [record for record in records if record["defense"] == defense]
        valid = [record for record in selected if record["status"] == "completed"]
        benign = [record for record in valid if record["injection_task_id"] is None]
        attacked = [record for record in valid if record["injection_task_id"] is not None]
        metrics[defense] = {
            "record_count": len(selected),
            "valid_record_count": len(valid),
            "benign_utility_success_rate": (
                sum(record["utility"] is True for record in benign) / len(benign)
                if benign
                else None
            ),
            "attacked_utility_success_rate": (
                sum(record["utility"] is True for record in attacked) / len(attacked)
                if attacked
                else None
            ),
            "targeted_asr": (
                sum(record["security"] is True for record in attacked) / len(attacked)
                if attacked
                else None
            ),
            "security_success_rate": (
                sum(record["security"] is False for record in attacked) / len(attacked)
                if attacked
                else None
            ),
            "infrastructure_error_rate": (
                sum(record["status"] != "completed" for record in selected) / len(selected)
                if selected
                else None
            ),
        }
    return metrics


def _pipeline(model: str, defense: str) -> AgentPipeline:
    llm = build_llm(model)
    llm.name = ATTACK_PIPELINE_NAMES.get(model, model)
    return AgentPipeline.from_config(
        PipelineConfig(
            llm=llm,
            model_id=None,
            defense=defense,
            system_message_name=None,
            system_message=None,
            tool_output_format=None,
        )
    )


def run_comparison(
    *,
    model: str,
    defenses: list[str],
    out_dir: Path,
    resume: bool,
) -> list[dict[str, Any]]:
    suite = get_suite("v1.2.2", "banking")
    if importlib.metadata.version("agentdojo") != "0.1.35":
        raise RuntimeError("comparison is pinned to agentdojo==0.1.35")

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "raw.jsonl"
    records = _load_records(raw_path) if resume else []
    completed_keys = {_key(record) for record in records}

    with raw_path.open("a" if resume else "w") as stream:
        for defense in defenses:
            pipeline = _pipeline(model, defense)
            attack = ImportantInstructionsAttack(suite, pipeline)
            defaults = suite.get_injection_vector_defaults()
            total = len(suite.user_tasks) * (1 + len(suite.injection_tasks))
            position = 0

            for user_task in suite.user_tasks.values():
                attempts = [(None, defaults)]
                attempts.extend(
                    (injection_task, attack.attack(user_task, injection_task))
                    for injection_task in suite.injection_tasks.values()
                )

                for injection_task, injections in attempts:
                    position += 1
                    injection_task_id = injection_task.ID if injection_task is not None else None
                    key = (defense, user_task.ID, injection_task_id)
                    if key in completed_keys:
                        print(f"[skip] {defense} {user_task.ID} x {injection_task_id or 'none'}")
                        continue
                    print(
                        f"[{position}/{total}] {defense} {user_task.ID} x "
                        f"{injection_task_id or 'none'}"
                    )
                    try:
                        utility, security = suite.run_task_with_pipeline(
                            pipeline,
                            user_task,
                            injection_task,
                            injections,
                        )
                        record = {
                            "defense": defense,
                            "model": model,
                            "suite": "banking",
                            "benchmark_version": "1.2.2",
                            "agentdojo_version": "0.1.35",
                            "attack": "ImportantInstructionsAttack",
                            "user_task_id": user_task.ID,
                            "injection_task_id": injection_task_id,
                            "utility": utility,
                            "security": security if injection_task is not None else None,
                            "status": "completed",
                            "infrastructure_errors": [],
                        }
                    except Exception as exc:
                        record = {
                            "defense": defense,
                            "model": model,
                            "suite": "banking",
                            "benchmark_version": "1.2.2",
                            "agentdojo_version": "0.1.35",
                            "attack": "ImportantInstructionsAttack",
                            "user_task_id": user_task.ID,
                            "injection_task_id": injection_task_id,
                            "utility": None,
                            "security": None,
                            "status": "infrastructure_error",
                            "infrastructure_errors": [f"{type(exc).__name__}: {exc}"],
                        }
                    records.append(record)
                    stream.write(json.dumps(record) + "\n")
                    stream.flush()

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--defenses", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    defenses = list(dict.fromkeys(args.defenses.split(",")))
    unknown = set(defenses) - set(DEFENSES)
    if unknown:
        parser.error(f"unknown defenses: {sorted(unknown)}")
    incompatible = set(defenses) - GEMINI_COMPATIBLE_DEFENSES
    if args.model == "gemini-2.5-flash" and incompatible:
        parser.error(
            f"these AgentDojo defenses are not Gemini-compatible in 0.1.35: {sorted(incompatible)}"
        )

    load_dotenv()
    started = time.time()
    records = run_comparison(
        model=args.model,
        defenses=defenses,
        out_dir=args.out_dir,
        resume=args.resume,
    )
    metrics = compute_comparison_metrics(records)
    (args.out_dir / "summary.json").write_text(json.dumps(metrics, indent=2))
    (args.out_dir / "run-metadata.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "suite": "banking",
                "benchmark_version": "1.2.2",
                "agentdojo_version": "0.1.35",
                "attack": "ImportantInstructionsAttack",
                "defenses": defenses,
                "repetitions": 1,
            },
            indent=2,
        )
    )
    print(f"\n{len(records)} records in {time.time() - started:.0f}s")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
