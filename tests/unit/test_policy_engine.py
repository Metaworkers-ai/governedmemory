from core.models import (
    MemoryRecord,
    Policy,
    PrivilegeRules,
    Provenance,
    Purpose,
    PurposeBinding,
    SourceType,
    Taint,
)
from core.policy_engine import (
    evaluate_privileged_action,
    evaluate_purpose_binding,
    filter_by_purpose_binding,
)


def _policy(purpose_bindings=None, privilege_rules=None) -> Policy:
    return Policy(
        id="default",
        tenant_id="tenant-1",
        purpose_bindings=purpose_bindings or [],
        privilege_rules=privilege_rules or PrivilegeRules(),
    )


def _record(source_type: SourceType = SourceType.USER, policy_id: str = "default") -> MemoryRecord:
    return MemoryRecord(
        tenant_id="tenant-1",
        customer_id="cust-1",
        agent_id="agent-1",
        session_id="sess-1",
        content="some memory",
        provenance=Provenance(source_type=source_type, source_ref="ref-1"),
        purpose=Purpose(policy_id=policy_id),
    )


class TestEvaluatePurposeBinding:
    def test_no_binding_defaults_to_allow(self):
        policy = _policy()
        allowed, reason = evaluate_purpose_binding(policy, "sales", "agent_derived")
        assert allowed is True
        assert "no binding defined" in reason

    def test_binding_with_empty_source_types_allows_any(self):
        policy = _policy(
            purpose_bindings=[PurposeBinding(purpose="sales", allowed_source_types=[])]
        )
        allowed, _ = evaluate_purpose_binding(policy, "sales", "agent_derived")
        assert allowed is True

    def test_binding_allows_matching_source_type(self):
        policy = _policy(
            purpose_bindings=[
                PurposeBinding(purpose="sales", allowed_source_types=["user", "trusted_system"])
            ]
        )
        allowed, reason = evaluate_purpose_binding(policy, "sales", "user")
        assert allowed is True
        assert "allowed" in reason

    def test_binding_denies_non_matching_source_type(self):
        policy = _policy(
            purpose_bindings=[
                PurposeBinding(purpose="sales", allowed_source_types=["user", "trusted_system"])
            ]
        )
        allowed, reason = evaluate_purpose_binding(policy, "sales", "agent_derived")
        assert allowed is False
        assert "not in allowed_source_types" in reason

    def test_binding_for_different_purpose_does_not_apply(self):
        policy = _policy(
            purpose_bindings=[PurposeBinding(purpose="sales", allowed_source_types=["user"])]
        )
        allowed, reason = evaluate_purpose_binding(policy, "billing", "agent_derived")
        assert allowed is True
        assert "no binding defined for purpose 'billing'" in reason


class TestEvaluatePrivilegedAction:
    def test_non_privileged_action_always_allowed(self):
        policy = _policy()
        allowed, reason = evaluate_privileged_action(policy, "read", Taint.UNTRUSTED)
        assert allowed is True
        assert "not a privileged action" in reason

    def test_default_privileged_actions_require_trust(self):
        policy = _policy()
        for action in ["send_email", "refund", "escalate"]:
            allowed, reason = evaluate_privileged_action(policy, action, Taint.UNTRUSTED)
            assert allowed is False, f"{action} should be denied for untrusted memories"
            assert "requires a trusted memory" in reason

    def test_privileged_action_allowed_when_trusted(self):
        policy = _policy()
        allowed, _ = evaluate_privileged_action(policy, "refund", Taint.TRUSTED)
        assert allowed is True

    def test_quarantined_denied_same_as_untrusted(self):
        policy = _policy()
        allowed, _ = evaluate_privileged_action(policy, "refund", Taint.QUARANTINED)
        assert allowed is False

    def test_require_trust_false_allows_untrusted(self):
        policy = _policy(privilege_rules=PrivilegeRules(require_trust=False))
        allowed, _ = evaluate_privileged_action(policy, "refund", Taint.UNTRUSTED)
        assert allowed is True

    def test_custom_privileged_actions_list(self):
        policy = _policy(privilege_rules=PrivilegeRules(privileged_actions=["delete_account"]))
        allowed, reason = evaluate_privileged_action(policy, "refund", Taint.UNTRUSTED)
        assert allowed is True
        assert "not a privileged action" in reason


class TestFilterByPurposeBinding:
    def test_no_purpose_is_a_no_op(self):
        records = [_record()]
        result = filter_by_purpose_binding(records, None, lambda pid: _policy())
        assert result == records

    def test_filters_using_looked_up_policy(self):
        policy = _policy(
            purpose_bindings=[PurposeBinding(purpose="sales", allowed_source_types=["user"])]
        )
        matching = _record(source_type=SourceType.USER)
        non_matching = _record(source_type=SourceType.AGENT_DERIVED)
        result = filter_by_purpose_binding([matching, non_matching], "sales", lambda pid: policy)
        assert result == [matching]

    def test_policy_lookup_called_once_per_distinct_policy_id(self):
        calls = []

        def lookup(pid):
            calls.append(pid)
            return _policy()

        records = [
            _record(policy_id="default"),
            _record(policy_id="default"),
            _record(policy_id="strict"),
        ]
        filter_by_purpose_binding(records, "sales", lookup)
        assert calls == ["default", "strict"]
