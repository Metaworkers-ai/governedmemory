"""Unit tests for integrations/agentdojo/benchmark.py.

Pure computation over synthetic records -- no agentdojo, no Docker, no API
key. This is the module computing whatever numbers eventually get
published for Step 11, so it gets the most thorough test treatment in
this whole project: every metric is tested for its exact arithmetic, its
None-vs-zero distinction, and its behavior on an empty record set.
"""

from __future__ import annotations

import pytest

from integrations.agentdojo.benchmark import (
    CONFIGURATIONS,
    compute_metrics,
    compute_metrics_by_configuration,
)


def _governed_record(
    *,
    utility: bool,
    security: bool | None = None,
    injection_task_id: str | None = None,
    evidence_count: int = 2,
    trusted_count: int = 1,
    privileged_attempts: int = 1,
    allowed_actions: int = 0,
    blocked_actions: int = 1,
    write_latencies_ms: list[float] | None = None,
    gate_latencies_ms: list[float] | None = None,
    status: str = "completed",
) -> dict:
    return {
        "user_task_id": "user_task_x",
        "injection_task_id": injection_task_id,
        "agentdojo": {"utility": utility, "security": security},
        "governance": {
            "evidence_count": evidence_count,
            "trusted_count": trusted_count,
            "untrusted_count": evidence_count - trusted_count,
            "privileged_attempts": privileged_attempts,
            "allowed_actions": allowed_actions,
            "blocked_actions": blocked_actions,
            "write_latencies_ms": write_latencies_ms or [],
            "gate_latencies_ms": gate_latencies_ms or [],
        },
        "status": status,
        "infrastructure_errors": [] if status == "completed" else ["simulated failure"],
    }


def _baseline_record(
    *, utility: bool, security: bool | None = None, injection_task_id: str | None = None
) -> dict:
    return {
        "user_task_id": "user_task_x",
        "injection_task_id": injection_task_id,
        "agentdojo": {"utility": utility, "security": security},
        "governance": None,
        "status": "completed",
        "infrastructure_errors": [],
    }


class TestEmptyRecordSet:
    def test_every_metric_is_none_not_zero(self):
        metrics = compute_metrics([])

        assert metrics["record_count"] == 0
        assert metrics["valid_record_count"] == 0
        for key in (
            "utility_success_rate",
            "security_success_rate",
            "targeted_asr",
            "governance_block_rate",
            "untrusted_evidence_rate",
            "false_block_rate",
            "infrastructure_error_rate",
            "write_latency_ms",
            "gate_latency_ms",
        ):
            assert metrics[key] is None, (
                f"{key} should be None for an empty record set, not a fake zero"
            )


class TestUtilitySuccessRate:
    def test_all_succeed(self):
        records = [_baseline_record(utility=True) for _ in range(4)]
        assert compute_metrics(records)["utility_success_rate"] == 1.0

    def test_all_fail(self):
        records = [_baseline_record(utility=False) for _ in range(4)]
        assert compute_metrics(records)["utility_success_rate"] == 0.0

    def test_exact_fraction(self):
        records = [_baseline_record(utility=True)] * 3 + [_baseline_record(utility=False)]
        assert compute_metrics(records)["utility_success_rate"] == pytest.approx(0.75)


class TestSecuritySuccessRateAndTargetedAsr:
    def test_none_when_no_attacked_runs(self):
        records = [_baseline_record(utility=True, injection_task_id=None) for _ in range(3)]
        metrics = compute_metrics(records)
        assert metrics["security_success_rate"] is None
        assert metrics["targeted_asr"] is None

    def test_ignores_benign_records_mixed_in_with_attacked_ones(self):
        records = [
            _baseline_record(utility=True, injection_task_id=None),
            _baseline_record(utility=True, security=True, injection_task_id="inj_0"),
            _baseline_record(utility=True, security=False, injection_task_id="inj_1"),
        ]
        metrics = compute_metrics(records)
        assert metrics["security_success_rate"] == pytest.approx(0.5)

    def test_security_and_targeted_asr_are_complementary(self):
        records = [
            _baseline_record(utility=True, security=True, injection_task_id="inj_0"),
            _baseline_record(utility=True, security=True, injection_task_id="inj_1"),
            _baseline_record(utility=True, security=False, injection_task_id="inj_2"),
            _baseline_record(utility=True, security=False, injection_task_id="inj_3"),
        ]
        metrics = compute_metrics(records)
        assert metrics["security_success_rate"] == pytest.approx(0.5)
        assert metrics["targeted_asr"] == pytest.approx(0.5)
        assert metrics["security_success_rate"] + metrics["targeted_asr"] == pytest.approx(1.0)

    def test_all_attacks_blocked(self):
        """security=False means the injection did NOT succeed -- per
        AgentDojo's own BaseInjectionTask.security() docstring ('Returns
        True if the injection was executed correctly'). 'Blocked' means
        False here, not True -- getting this backwards was a real bug
        found during manual validation."""
        records = [_baseline_record(utility=True, security=False, injection_task_id="inj_0")] * 3
        metrics = compute_metrics(records)
        assert metrics["security_success_rate"] == 1.0
        assert metrics["targeted_asr"] == 0.0

    def test_all_attacks_succeed(self):
        """security=True means the injection DID succeed."""
        records = [_baseline_record(utility=False, security=True, injection_task_id="inj_0")] * 3
        metrics = compute_metrics(records)
        assert metrics["security_success_rate"] == 0.0
        assert metrics["targeted_asr"] == 1.0


class TestGovernanceBlockRate:
    def test_none_when_no_governed_records(self):
        records = [_baseline_record(utility=True) for _ in range(3)]
        assert compute_metrics(records)["governance_block_rate"] is None

    def test_none_when_governed_records_have_zero_privileged_attempts(self):
        records = [_governed_record(utility=True, privileged_attempts=0, blocked_actions=0)]
        assert compute_metrics(records)["governance_block_rate"] is None

    def test_pools_privileged_attempts_across_records(self):
        records = [
            _governed_record(
                utility=False, privileged_attempts=1, blocked_actions=1, allowed_actions=0
            ),
            _governed_record(
                utility=True, privileged_attempts=1, blocked_actions=0, allowed_actions=1
            ),
        ]
        assert compute_metrics(records)["governance_block_rate"] == pytest.approx(0.5)

    def test_baseline_records_are_excluded_from_the_pool(self):
        records = [
            _baseline_record(utility=True),
            _governed_record(
                utility=False, privileged_attempts=2, blocked_actions=2, allowed_actions=0
            ),
        ]
        assert compute_metrics(records)["governance_block_rate"] == 1.0


class TestUntrustedEvidenceRate:
    def test_pools_evidence_across_governed_records_only(self):
        records = [
            _baseline_record(utility=True),
            _governed_record(utility=True, evidence_count=4, trusted_count=1),
            _governed_record(utility=True, evidence_count=2, trusted_count=2),
        ]
        assert compute_metrics(records)["untrusted_evidence_rate"] == pytest.approx(0.5)

    def test_none_when_no_governed_records(self):
        records = [_baseline_record(utility=True)]
        assert compute_metrics(records)["untrusted_evidence_rate"] is None


class TestFalseBlockRate:
    def test_only_counts_benign_governed_runs(self):
        records = [
            _governed_record(
                utility=False,
                injection_task_id=None,
                privileged_attempts=1,
                blocked_actions=1,
                allowed_actions=0,
            ),
            _governed_record(
                utility=False,
                security=False,  # attack correctly did NOT succeed, consistent with being blocked
                injection_task_id="inj_0",
                privileged_attempts=1,
                blocked_actions=1,
                allowed_actions=0,
            ),
        ]
        metrics = compute_metrics(records)
        assert metrics["false_block_rate"] == 1.0

    def test_none_when_no_benign_governed_runs_with_privileged_attempts(self):
        records = [
            _governed_record(
                utility=False,
                security=False,
                injection_task_id="inj_0",
                privileged_attempts=1,
                blocked_actions=1,
            ),
        ]
        assert compute_metrics(records)["false_block_rate"] is None

    def test_zero_when_benign_privileged_actions_are_never_blocked(self):
        records = [
            _governed_record(
                utility=True,
                injection_task_id=None,
                privileged_attempts=1,
                blocked_actions=0,
                allowed_actions=1,
            ),
        ]
        assert compute_metrics(records)["false_block_rate"] == 0.0

    def test_matches_the_step_9_finding_shape(self):
        records = [
            _governed_record(
                utility=False,
                injection_task_id=None,
                privileged_attempts=1,
                blocked_actions=1,
                allowed_actions=0,
            )
            for _ in range(5)
        ]
        assert compute_metrics(records)["false_block_rate"] == 1.0


class TestInfrastructureErrorRate:
    def test_counts_non_completed_status_across_all_records(self):
        records = [
            _baseline_record(utility=True),
            _governed_record(utility=False, status="infrastructure_error"),
            _governed_record(utility=True),
        ]
        assert compute_metrics(records)["infrastructure_error_rate"] == pytest.approx(1 / 3)

    def test_zero_when_everything_completed(self):
        records = [_baseline_record(utility=True), _governed_record(utility=True)]
        assert compute_metrics(records)["infrastructure_error_rate"] == 0.0

    def test_invalid_attempts_are_excluded_from_every_other_metric(self):
        records = [
            _governed_record(
                utility=True,
                security=False,
                injection_task_id="inj_0",
                evidence_count=2,
                trusted_count=2,
                privileged_attempts=1,
                allowed_actions=1,
                blocked_actions=0,
                write_latencies_ms=[10.0],
                gate_latencies_ms=[5.0],
            ),
            _governed_record(
                utility=False,
                security=True,
                injection_task_id="inj_0",
                evidence_count=10,
                trusted_count=0,
                privileged_attempts=10,
                allowed_actions=0,
                blocked_actions=10,
                write_latencies_ms=[999.0],
                gate_latencies_ms=[999.0],
                status="infrastructure_error",
            ),
        ]

        metrics = compute_metrics(records)

        assert metrics["record_count"] == 2
        assert metrics["valid_record_count"] == 1
        assert metrics["utility_success_rate"] == 1.0
        assert metrics["security_success_rate"] == 1.0
        assert metrics["targeted_asr"] == 0.0
        assert metrics["governance_block_rate"] == 0.0
        assert metrics["untrusted_evidence_rate"] == 0.0
        assert metrics["write_latency_ms"]["mean_ms"] == 10.0
        assert metrics["gate_latency_ms"]["mean_ms"] == 5.0
        assert metrics["infrastructure_error_rate"] == 0.5


class TestLatencySummaries:
    def test_none_when_no_samples_at_all(self):
        records = [_governed_record(utility=True, write_latencies_ms=[], gate_latencies_ms=[])]
        metrics = compute_metrics(records)
        assert metrics["write_latency_ms"] is None
        assert metrics["gate_latency_ms"] is None

    def test_pools_samples_across_records_not_per_record_averages(self):
        records = [
            _governed_record(utility=True, write_latencies_ms=[10.0]),
            _governed_record(utility=True, write_latencies_ms=[20.0] * 9),
        ]
        summary = compute_metrics(records)["write_latency_ms"]
        assert summary["mean_ms"] == pytest.approx(19.0)
        assert summary["count"] == 10

    def test_median_and_p95_and_bounds(self):
        records = [
            _governed_record(utility=True, write_latencies_ms=[float(x) for x in range(1, 21)])
        ]
        summary = compute_metrics(records)["write_latency_ms"]
        assert summary["count"] == 20
        assert summary["min_ms"] == 1.0
        assert summary["max_ms"] == 20.0
        assert summary["median_ms"] == pytest.approx(10.5)

    def test_gate_latency_pools_separately_from_write_latency(self):
        records = [
            _governed_record(
                utility=True, write_latencies_ms=[1.0], gate_latencies_ms=[100.0, 200.0]
            )
        ]
        metrics = compute_metrics(records)
        assert metrics["write_latency_ms"]["mean_ms"] == pytest.approx(1.0)
        assert metrics["gate_latency_ms"]["mean_ms"] == pytest.approx(150.0)


class TestComputeMetricsByConfiguration:
    def test_splits_records_by_config_tag(self):
        tagged = [
            {**_baseline_record(utility=True), "config": "baseline_benign"},
            {**_baseline_record(utility=False), "config": "baseline_benign"},
            {**_governed_record(utility=False), "config": "governed_benign"},
        ]
        result = compute_metrics_by_configuration(tagged)

        assert set(result) == set(CONFIGURATIONS)
        assert result["baseline_benign"]["record_count"] == 2
        assert result["baseline_benign"]["valid_record_count"] == 2
        assert result["governed_benign"]["record_count"] == 1
        assert result["baseline_attacked"]["record_count"] == 0
        assert result["governed_attacked"]["record_count"] == 0

    def test_empty_configurations_still_get_an_all_none_entry(self):
        result = compute_metrics_by_configuration([])
        for config in CONFIGURATIONS:
            assert result[config]["record_count"] == 0
            assert result[config]["utility_success_rate"] is None

    def test_invalid_config_tag_raises(self):
        tagged = [{**_baseline_record(utility=True), "config": "not_a_real_configuration"}]
        with pytest.raises(ValueError, match="not_a_real_configuration"):
            compute_metrics_by_configuration(tagged)

    def test_missing_config_tag_raises(self):
        tagged = [_baseline_record(utility=True)]
        with pytest.raises(ValueError):
            compute_metrics_by_configuration(tagged)
