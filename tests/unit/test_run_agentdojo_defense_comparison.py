from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("agentdojo")

_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts"
    / "run_agentdojo_defense_comparison.py"
)
_SPEC = importlib.util.spec_from_file_location("run_agentdojo_defense_comparison", _SCRIPT)
comparison = importlib.util.module_from_spec(_SPEC)
sys.modules["run_agentdojo_defense_comparison"] = comparison
_SPEC.loader.exec_module(comparison)


def test_compute_comparison_metrics_uses_agentdojo_security_semantics():
    records = [
        {
            "defense": "repeat_user_prompt",
            "injection_task_id": None,
            "utility": True,
            "security": None,
            "status": "completed",
        },
        {
            "defense": "repeat_user_prompt",
            "injection_task_id": "injection_task_0",
            "utility": False,
            "security": True,
            "status": "completed",
        },
        {
            "defense": "repeat_user_prompt",
            "injection_task_id": "injection_task_1",
            "utility": True,
            "security": False,
            "status": "completed",
        },
    ]

    metrics = comparison.compute_comparison_metrics(records)["repeat_user_prompt"]

    assert metrics["benign_utility_success_rate"] == 1.0
    assert metrics["attacked_utility_success_rate"] == 0.5
    assert metrics["targeted_asr"] == 0.5
    assert metrics["security_success_rate"] == 0.5
    assert metrics["infrastructure_error_rate"] == 0.0


def test_compute_comparison_metrics_excludes_errors_from_outcomes():
    records = [
        {
            "defense": "spotlighting_with_delimiting",
            "injection_task_id": None,
            "utility": None,
            "security": None,
            "status": "infrastructure_error",
        }
    ]

    metrics = comparison.compute_comparison_metrics(records)["spotlighting_with_delimiting"]

    assert metrics["record_count"] == 1
    assert metrics["valid_record_count"] == 0
    assert metrics["benign_utility_success_rate"] is None
    assert metrics["infrastructure_error_rate"] == 1.0
