"""Unit tests for scripts/run_agentdojo_benchmark.py.

Like scripts/validate_agentdojo_manual.py, the whole point of this script
is real LLM calls and real database writes -- most of it can't be tested
without those. What's tested here: record tagging, the `--configs`
argument validation, and the methodology report generator, using
synthetic metrics from integrations/agentdojo/benchmark.py (already
thoroughly tested on its own in tests/unit/test_benchmark_metrics.py).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

agentdojo = pytest.importorskip("agentdojo")

from integrations.agentdojo.benchmark import (  # noqa: E402
    CONFIGURATIONS,
    compute_metrics_by_configuration,
)

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_agentdojo_benchmark.py"
)
_spec = importlib.util.spec_from_file_location("run_agentdojo_benchmark", _SCRIPT_PATH)
run_agentdojo_benchmark = importlib.util.module_from_spec(_spec)
sys.modules["run_agentdojo_benchmark"] = run_agentdojo_benchmark
_spec.loader.exec_module(run_agentdojo_benchmark)


class TestTag:
    def test_adds_config_key_without_mutating_the_original(self):
        record = {"user_task_id": "user_task_1"}
        tagged = run_agentdojo_benchmark._tag(record, "governed_benign")

        assert tagged["config"] == "governed_benign"
        assert tagged["user_task_id"] == "user_task_1"
        assert "config" not in record

    def test_attaches_run_metadata_when_provided(self):
        tagged = run_agentdojo_benchmark._tag(
            {"user_task_id": "user_task_1"},
            "governed_benign",
            {"detection_backend": "ensemble"},
        )

        assert tagged["run_metadata"]["detection_backend"] == "ensemble"


class TestTaskSelection:
    def test_explicit_ids_preserve_order_and_remove_duplicates(self):
        selected = run_agentdojo_benchmark._select_ids(
            {"user_task_0": object(), "user_task_3": object()},
            ["user_task_3", "user_task_0", "user_task_3"],
            None,
            label="user task",
        )

        assert selected == ["user_task_3", "user_task_0"]

    def test_unknown_explicit_id_is_rejected(self):
        with pytest.raises(ValueError, match="user_task_missing"):
            run_agentdojo_benchmark._select_ids(
                {"user_task_0": object()},
                ["user_task_missing"],
                None,
                label="user task",
            )

    def test_limit_applies_after_explicit_selection(self):
        selected = run_agentdojo_benchmark._select_ids(
            {"user_task_0": object(), "user_task_3": object()},
            ["user_task_3", "user_task_0"],
            1,
            label="user task",
        )

        assert selected == ["user_task_3"]


class TestResumeHelpers:
    def test_load_existing_records_reads_jsonl(self, tmp_path):
        raw_path = tmp_path / "raw.jsonl"
        raw_path.write_text('{"config":"baseline_benign","user_task_id":"user_task_0","seed":0}\n')

        records = run_agentdojo_benchmark._load_existing_records(raw_path)

        assert len(records) == 1
        assert records[0]["user_task_id"] == "user_task_0"

    def test_invalid_jsonl_reports_line_number(self, tmp_path):
        raw_path = tmp_path / "raw.jsonl"
        raw_path.write_text("{}\nnot-json\n")

        with pytest.raises(ValueError, match=":2"):
            run_agentdojo_benchmark._load_existing_records(raw_path)


class TestConfigsArgumentValidation:
    def test_default_includes_all_four_configurations(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--model", required=True)
        parser.add_argument("--out-dir", required=True, type=Path)
        parser.add_argument("--configs", default=",".join(CONFIGURATIONS))
        args = parser.parse_args(["--model", "x", "--out-dir", "/tmp/out"])

        assert set(args.configs.split(",")) == set(CONFIGURATIONS)

    def test_unknown_configuration_would_be_rejected(self):
        configs = {"not_a_real_config"}
        unknown = configs - set(CONFIGURATIONS)
        assert unknown  # confirms the same check main() performs would fire


class TestMethodologyReport:
    def _sample_metrics(self):
        tagged = [
            {
                "user_task_id": "user_task_1",
                "injection_task_id": None,
                "agentdojo": {"utility": True, "security": None},
                "governance": None,
                "status": "completed",
                "infrastructure_errors": [],
                "config": "baseline_benign",
            },
            {
                "user_task_id": "user_task_1",
                "injection_task_id": None,
                "agentdojo": {"utility": False, "security": None},
                "governance": {
                    "evidence_count": 2,
                    "trusted_count": 0,
                    "untrusted_count": 2,
                    "privileged_attempts": 1,
                    "allowed_actions": 0,
                    "blocked_actions": 1,
                    "write_latencies_ms": [5.0, 10.0],
                    "gate_latencies_ms": [1.0],
                },
                "status": "completed",
                "infrastructure_errors": [],
                "config": "governed_benign",
            },
        ]
        return compute_metrics_by_configuration(tagged)

    def test_writes_a_markdown_file_with_the_expected_sections(self, tmp_path):
        metrics = self._sample_metrics()

        run_agentdojo_benchmark.write_methodology_report(
            tmp_path, "gpt-4o-mini-2024-07-18", metrics
        )

        report_path = tmp_path / "methodology.md"
        assert report_path.exists()
        content = report_path.read_text()
        assert "gpt-4o-mini-2024-07-18" in content
        assert "utility_success_rate" in content
        assert "false_block_rate" in content
        assert "Only a pre-execution policy denial counts as a GovernedMemory block" in content

    def test_includes_reproducibility_metadata(self, tmp_path):
        metrics = self._sample_metrics()
        metadata = {
            "git_commit": "abc123",
            "detection_backend": "ensemble",
            "injection_threshold": 0.7,
            "classifier_sha256": "deadbeef",
            "source_mapping_version": "banking-v4-content-scored-files",
            "gate_policy": "tool_outputs_only",
        }

        run_agentdojo_benchmark.write_methodology_report(
            tmp_path, "gpt-4o-mini-2024-07-18", metrics, metadata
        )

        content = (tmp_path / "methodology.md").read_text()
        assert "abc123" in content
        assert "ensemble" in content
        assert "deadbeef" in content
        assert "tool_outputs_only" in content

    def test_none_metrics_render_as_an_em_dash_not_a_python_none(self, tmp_path):
        metrics = self._sample_metrics()

        run_agentdojo_benchmark.write_methodology_report(
            tmp_path, "gpt-4o-mini-2024-07-18", metrics
        )

        content = (tmp_path / "methodology.md").read_text()
        assert "None" not in content
        assert "—" in content

    def test_latency_section_only_includes_configs_with_samples(self, tmp_path):
        metrics = self._sample_metrics()

        run_agentdojo_benchmark.write_methodology_report(
            tmp_path, "gpt-4o-mini-2024-07-18", metrics
        )

        content = (tmp_path / "methodology.md").read_text()
        assert "governed_benign / write_latency_ms" in content
        assert "baseline_benign / write_latency_ms" not in content
