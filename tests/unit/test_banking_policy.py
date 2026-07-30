"""Unit tests for integrations/agentdojo/banking_policy.py.

These use a minimal fake store rather than a real MemoryStore, so they run
without Docker. The behavioral claim that matters most here -- that an
*unconfigured* tenant would leave send_money ungated, and that
ensure_banking_policy() fixes that -- is proven against the real
MemoryStore + Postgres in
tests/integration/test_banking_policy.py, because it depends on the real
`evaluate_privileged_action()` / `check_privilege()` path, not just on what
get_policy()/upsert_policy() were called with.
"""

from core.models import Policy, PrivilegeRules
from integrations.agentdojo.banking_mapping import PRIVILEGED_ACTIONS
from integrations.agentdojo.banking_policy import ensure_banking_policy


class FakeStore:
    """Records upsert_policy() calls and echoes back what a real
    MemoryStore.upsert_policy() returns: the same Policy object it was
    given (see store.py: 'return policy')."""

    def __init__(self) -> None:
        self.upserted: list[Policy] = []

    def upsert_policy(self, policy: Policy) -> Policy:
        self.upserted.append(policy)
        return policy


class TestEnsureBankingPolicy:
    def test_upserts_exactly_once(self):
        store = FakeStore()
        ensure_banking_policy(store, tenant_id="tenant-1")
        assert len(store.upserted) == 1

    def test_policy_id_defaults_to_default(self):
        store = FakeStore()
        policy = ensure_banking_policy(store, tenant_id="tenant-1")
        assert policy.id == "default"

    def test_policy_id_can_be_overridden(self):
        store = FakeStore()
        policy = ensure_banking_policy(store, tenant_id="tenant-1", policy_id="banking-eval")
        assert policy.id == "banking-eval"

    def test_tenant_id_is_passed_through(self):
        store = FakeStore()
        policy = ensure_banking_policy(store, tenant_id="tenant-xyz")
        assert policy.tenant_id == "tenant-xyz"

    def test_privileged_actions_match_the_banking_mapping_table_exactly(self):
        store = FakeStore()
        policy = ensure_banking_policy(store, tenant_id="tenant-1")
        assert set(policy.privilege_rules.privileged_actions) == set(PRIVILEGED_ACTIONS)

    def test_require_trust_is_always_true(self):
        store = FakeStore()
        policy = ensure_banking_policy(store, tenant_id="tenant-1")
        assert policy.privilege_rules.require_trust is True

    def test_does_not_reuse_default_privilege_rules(self):
        """Guards against accidentally passing PrivilegeRules() with no
        arguments, which would silently fall back to the product defaults
        (send_email/refund/escalate) instead of the Banking action set."""
        store = FakeStore()
        policy = ensure_banking_policy(store, tenant_id="tenant-1")
        assert policy.privilege_rules != PrivilegeRules()

    def test_calling_twice_for_the_same_tenant_upserts_twice_with_identical_content(self):
        """Documents the idempotency claim in the docstring: calling this
        defensively more than once for the same tenant is safe -- it just
        re-sends the same policy content, it does not error or duplicate
        state (upsert_policy's ON CONFLICT DO UPDATE handles the actual
        persistence side of this; this test only proves this function's
        own inputs stay identical across calls)."""
        store = FakeStore()
        first = ensure_banking_policy(store, tenant_id="tenant-1")
        second = ensure_banking_policy(store, tenant_id="tenant-1")
        assert len(store.upserted) == 2
        assert first.privilege_rules == second.privilege_rules
        assert first.id == second.id
        assert first.tenant_id == second.tenant_id
