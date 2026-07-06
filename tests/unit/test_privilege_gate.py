from core.models import MemoryRecord, Provenance, Purpose, SourceType, Taint, Trust
from core.retrieval_engine import apply_privilege_gate


def _record(
    taint: Taint = Taint.TRUSTED, allowed_purposes: list[str] | None = None
) -> MemoryRecord:
    return MemoryRecord(
        tenant_id="tenant-1",
        customer_id="cust-1",
        agent_id="agent-1",
        session_id="sess-1",
        content="some memory",
        provenance=Provenance(source_type=SourceType.USER, source_ref="ref-1"),
        trust=Trust(taint=taint),
        purpose=Purpose(allowed_purposes=allowed_purposes or []),
    )


class TestApplyPrivilegeGate:
    def test_trusted_passes_by_default(self):
        records = [_record(taint=Taint.TRUSTED)]
        assert apply_privilege_gate(records) == records

    def test_untrusted_excluded_by_default(self):
        records = [_record(taint=Taint.UNTRUSTED)]
        assert apply_privilege_gate(records) == []

    def test_quarantined_excluded_by_default(self):
        records = [_record(taint=Taint.QUARANTINED)]
        assert apply_privilege_gate(records) == []

    def test_include_untrusted_bypasses_taint_filter(self):
        records = [_record(taint=Taint.UNTRUSTED), _record(taint=Taint.QUARANTINED)]
        assert apply_privilege_gate(records, include_untrusted=True) == records

    def test_empty_allowed_purposes_is_open_to_any_purpose(self):
        records = [_record(allowed_purposes=[])]
        assert apply_privilege_gate(records, purpose="billing") == records

    def test_matching_purpose_passes(self):
        records = [_record(allowed_purposes=["billing", "cx_support"])]
        assert apply_privilege_gate(records, purpose="billing") == records

    def test_non_matching_purpose_excluded(self):
        records = [_record(allowed_purposes=["billing"])]
        assert apply_privilege_gate(records, purpose="sales") == []

    def test_no_purpose_argument_skips_purpose_filtering(self):
        records = [_record(allowed_purposes=["billing"])]
        assert apply_privilege_gate(records, purpose=None) == records

    def test_preserves_input_order(self):
        r1 = _record(taint=Taint.TRUSTED)
        r2 = _record(taint=Taint.TRUSTED)
        assert apply_privilege_gate([r1, r2]) == [r1, r2]

    def test_both_filters_apply_together(self):
        matches = _record(taint=Taint.TRUSTED, allowed_purposes=["billing"])
        wrong_purpose = _record(taint=Taint.TRUSTED, allowed_purposes=["sales"])
        wrong_taint = _record(taint=Taint.UNTRUSTED, allowed_purposes=["billing"])
        result = apply_privilege_gate([matches, wrong_purpose, wrong_taint], purpose="billing")
        assert result == [matches]
