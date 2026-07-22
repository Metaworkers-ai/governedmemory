"""
Unit tests for core data models (E1 — data model gap fixes).

No database or network required. These tests verify:
  1. All required fields are present and typed correctly
  2. Enums have the correct values (matching engineering plan §4)
  3. Defaults are sane (taint=trusted, injection_score=0.0, etc.)
  4. Validation rejects bad inputs
  5. Nested models serialize/deserialize correctly
  6. Tenant isolation: tenant_id is always present and cannot be blank

Run: pytest tests/unit/test_models.py -v
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from core.models.audit_event import (
    AuditActor,
    AuditDecision,
    AuditEvent,
    AuditOp,
    AuditOutcome,
)
from core.models.memory_record import (
    MemoryRecord,
    Provenance,
    Purpose,
    SourceType,
    Taint,
    Temporal,
    Trust,
    WriteRequest,
)
from core.models.policy import Policy, PurposeBinding

# ============================================================
# Helpers
# ============================================================


def _make_provenance(**kwargs) -> Provenance:
    defaults = dict(source_type=SourceType.USER, source_ref="ticket-001")
    return Provenance(**(defaults | kwargs))


def _make_write_request(**kwargs) -> WriteRequest:
    defaults = dict(
        tenant_id="tenant-a",
        customer_id="cust-001",
        agent_id="cx-agent-1",
        session_id="session-42",
        content="Customer prefers email contact",
        provenance=_make_provenance(),
    )
    return WriteRequest(**(defaults | kwargs))


def _make_memory_record(**kwargs) -> MemoryRecord:
    defaults = dict(
        tenant_id="tenant-a",
        customer_id="cust-001",
        agent_id="cx-agent-1",
        session_id="session-42",
        content="Customer is on premium plan",
        provenance=_make_provenance(),
    )
    return MemoryRecord(**(defaults | kwargs))


# ============================================================
# SourceType enum
# ============================================================


class TestSourceType:
    def test_all_values_present(self):
        values = {st.value for st in SourceType}
        assert values == {
            "user",
            "trusted_system",
            "tool_output",
            "untrusted_web",
            "untrusted_email",
            "agent_derived",
        }

    def test_roundtrip_from_string(self):
        assert SourceType("untrusted_web") == SourceType.UNTRUSTED_WEB

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            SourceType("ticket")  # old MVP value — must be rejected


# ============================================================
# Taint enum
# ============================================================


class TestTaint:
    def test_all_values(self):
        assert {t.value for t in Taint} == {"trusted", "untrusted", "quarantined"}

    def test_default_is_trusted(self):
        trust = Trust()
        assert trust.taint == Taint.TRUSTED


# ============================================================
# Provenance model
# ============================================================


class TestProvenance:
    def test_minimal_construction(self):
        p = Provenance(source_type=SourceType.USER, source_ref="msg-1001")
        assert p.confidence == 1.0
        assert p.parent_ids == []
        assert p.ingested_at is not None

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            Provenance(source_type=SourceType.USER, source_ref="x", confidence=1.5)
        with pytest.raises(ValidationError):
            Provenance(source_type=SourceType.USER, source_ref="x", confidence=-0.1)

    def test_parent_ids_are_list(self):
        p = Provenance(
            source_type=SourceType.AGENT_DERIVED,
            source_ref="derived",
            parent_ids=["uuid-1", "uuid-2"],
        )
        assert len(p.parent_ids) == 2


# ============================================================
# Trust model
# ============================================================


class TestTrust:
    def test_defaults(self):
        t = Trust()
        assert t.taint == Taint.TRUSTED
        assert t.taint_reason is None
        assert t.injection_score == 0.0

    def test_injection_score_bounds(self):
        with pytest.raises(ValidationError):
            Trust(injection_score=-0.01)
        with pytest.raises(ValidationError):
            Trust(injection_score=1.01)

    def test_quarantined_with_reason(self):
        t = Trust(taint=Taint.QUARANTINED, taint_reason="manual review")
        assert t.taint == Taint.QUARANTINED
        assert t.taint_reason == "manual review"


# ============================================================
# MemoryRecord — the core model
# ============================================================


class TestMemoryRecord:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            MemoryRecord()  # missing everything

    def test_tenant_id_is_required(self):
        with pytest.raises(ValidationError):
            _make_memory_record(tenant_id=None)

    def test_customer_id_is_required(self):
        with pytest.raises(ValidationError):
            _make_memory_record(customer_id=None)

    def test_id_is_auto_generated(self):
        r1 = _make_memory_record()
        r2 = _make_memory_record()
        assert r1.id != r2.id
        assert len(r1.id) == 36  # UUID v4 format

    def test_defaults_applied(self):
        r = _make_memory_record()
        assert r.trust.taint == Taint.TRUSTED
        assert r.trust.injection_score == 0.0
        assert r.purpose.policy_id == "default"
        assert r.temporal.version == 1
        assert r.temporal.superseded_by is None
        assert r.access.acl == []

    def test_serialization_roundtrip(self):
        r = _make_memory_record()
        data = r.model_dump()
        r2 = MemoryRecord.model_validate(data)
        assert r.id == r2.id
        assert r.tenant_id == r2.tenant_id
        assert r.provenance.source_type == r2.provenance.source_type

    def test_different_tenants_have_separate_identities(self):
        r1 = _make_memory_record(tenant_id="tenant-a")
        r2 = _make_memory_record(tenant_id="tenant-b")
        assert r1.tenant_id != r2.tenant_id

    def test_untrusted_source_types(self):
        for st in [SourceType.UNTRUSTED_WEB, SourceType.UNTRUSTED_EMAIL]:
            p = _make_provenance(source_type=st)
            r = _make_memory_record(provenance=p)
            assert r.provenance.source_type == st


# ============================================================
# WriteRequest
# ============================================================


class TestWriteRequest:
    def test_minimal_request(self):
        req = _make_write_request()
        assert req.tenant_id == "tenant-a"
        assert req.purpose.policy_id == "default"

    def test_custom_purpose(self):
        req = _make_write_request(
            purpose=Purpose(allowed_purposes=["cx_support", "billing"], policy_id="pol-cx-001")
        )
        assert "cx_support" in req.purpose.allowed_purposes

    def test_temporal_with_expiry(self):
        future = datetime.now(UTC) + timedelta(days=90)
        req = _make_write_request(temporal=Temporal(valid_until=future))
        assert req.temporal.valid_until == future


# ============================================================
# AuditEvent
# ============================================================


class TestAuditEvent:
    def test_construction(self):
        evt = AuditEvent(
            tenant_id="tenant-a",
            actor=AuditActor(agent_id="cx-1", session_id="sess-1"),
            op=AuditOp.WRITE,
            memory_ids=["mem-uuid-1"],
            decision=AuditDecision(outcome=AuditOutcome.ALLOW, reason="accepted"),
        )
        assert evt.op == AuditOp.WRITE
        assert evt.hash == ""  # filled by store, not caller
        assert evt.prev_hash == ""

    def test_all_ops_present(self):
        ops = {op.value for op in AuditOp}
        assert ops == {
            "write",
            "retrieve",
            "quarantine",
            "purge",
            "policy_decision",
            "external_evaluation",
            "external_binding",
            "external_quarantine",
        }

    def test_all_outcomes_present(self):
        outcomes = {o.value for o in AuditOutcome}
        assert outcomes == {"allow", "deny", "gated"}


# ============================================================
# Policy model
# ============================================================


class TestPolicy:
    def test_default_privilege_rules(self):
        p = Policy(id="default", tenant_id="tenant-a")
        assert "send_email" in p.privilege_rules.privileged_actions
        assert p.privilege_rules.require_trust is True

    def test_rbac_is_empty_stub(self):
        p = Policy(id="default", tenant_id="tenant-a")
        assert p.rbac == []  # enterprise stub — always empty in OSS

    def test_purpose_bindings(self):
        p = Policy(
            id="cx-policy",
            tenant_id="tenant-a",
            purpose_bindings=[
                PurposeBinding(
                    purpose="cx_support",
                    allowed_source_types=["user", "trusted_system"],
                    allowed_actions=["read"],
                )
            ],
        )
        assert p.purpose_bindings[0].purpose == "cx_support"
