"""Unit tests for integrations/agentdojo/banking_mapping.py.

Pure Python, no Docker, no AgentDojo install required -- the expected tool
set here is hardcoded independently of tests/contract/'s
EXPECTED_BANKING_TOOL_NAMES so this file has no import-time dependency on
`agentdojo` being installed. The two lists are cross-checked against each
other in tests/contract/test_agentdojo_contract.py, which does require
`agentdojo` and is skipped when it's absent.
"""

import pytest

from core.models import SourceType
from integrations.agentdojo.banking_mapping import (
    PRIVILEGED_ACTIONS,
    SOURCE_MAPPING_VERSION,
    SOURCE_TYPE_BY_TOOL,
    UnmappedBankingToolError,
    validate_tool_coverage,
)

# Mirrors tests/contract/test_agentdojo_contract.py's
# EXPECTED_BANKING_TOOL_NAMES. Kept as a separate literal here (rather than
# imported) so this unit test suite never needs agentdojo installed.
EXPECTED_BANKING_TOOL_NAMES = frozenset(
    {
        "get_iban",
        "send_money",
        "schedule_transaction",
        "update_scheduled_transaction",
        "get_balance",
        "get_most_recent_transactions",
        "get_scheduled_transactions",
        "read_file",
        "get_user_info",
        "update_password",
        "update_user_info",
    }
)


class TestSourceTypeByTool:
    def test_covers_every_expected_banking_tool(self):
        assert set(SOURCE_TYPE_BY_TOOL) == EXPECTED_BANKING_TOOL_NAMES

    def test_every_value_is_a_source_type(self):
        assert all(isinstance(v, SourceType) for v in SOURCE_TYPE_BY_TOOL.values())

    @pytest.mark.parametrize(
        "tool_name,expected",
        [
            ("get_most_recent_transactions", SourceType.TRUSTED_SYSTEM),
            ("read_file", SourceType.UNTRUSTED_WEB),
            ("get_balance", SourceType.TRUSTED_SYSTEM),
            ("get_iban", SourceType.TRUSTED_SYSTEM),
            ("get_scheduled_transactions", SourceType.TRUSTED_SYSTEM),
            ("get_user_info", SourceType.TRUSTED_SYSTEM),
            ("send_money", SourceType.TRUSTED_SYSTEM),
            ("schedule_transaction", SourceType.TRUSTED_SYSTEM),
            ("update_scheduled_transaction", SourceType.TRUSTED_SYSTEM),
            ("update_password", SourceType.TRUSTED_SYSTEM),
            ("update_user_info", SourceType.TRUSTED_SYSTEM),
        ],
    )
    def test_specific_mappings_match_the_lld_table(self, tool_name, expected):
        assert SOURCE_TYPE_BY_TOOL[tool_name] == expected

    def test_only_read_file_is_untrusted_by_source(self):
        """Banking v2 content-scores transaction descriptions instead of
        auto-tainting every transaction response by source."""
        untrusted = {
            "untrusted_email",
            "untrusted_web",
        }
        untrusted_tools = {
            name for name, st in SOURCE_TYPE_BY_TOOL.items() if st.value in untrusted
        }
        assert untrusted_tools == {"read_file"}


class TestPrivilegedActions:
    def test_matches_lld_section_12_exactly(self):
        assert set(PRIVILEGED_ACTIONS) == {
            "send_money",
            "schedule_transaction",
            "update_scheduled_transaction",
            "update_password",
            "update_user_info",
        }

    def test_does_not_reuse_governedmemory_product_defaults(self):
        """The shipped PrivilegeRules default is
        ["send_email", "refund", "escalate"] -- none of those are Banking
        tool names. Asserting disjointness catches a copy-paste regression
        where someone accidentally restores the product defaults."""
        assert set(PRIVILEGED_ACTIONS).isdisjoint({"send_email", "refund", "escalate"})

    def test_every_privileged_action_is_a_mapped_banking_tool(self):
        assert set(PRIVILEGED_ACTIONS).issubset(set(SOURCE_TYPE_BY_TOOL))

    def test_read_tools_are_not_privileged(self):
        read_tools = {
            "get_most_recent_transactions",
            "read_file",
            "get_balance",
            "get_iban",
            "get_scheduled_transactions",
            "get_user_info",
        }
        assert read_tools.isdisjoint(set(PRIVILEGED_ACTIONS))


class TestValidateToolCoverage:
    def test_exact_installed_set_passes(self):
        validate_tool_coverage(EXPECTED_BANKING_TOOL_NAMES)  # should not raise

    def test_subset_of_installed_tools_passes(self):
        validate_tool_coverage(["get_balance", "send_money"])  # should not raise

    def test_unmapped_tool_raises(self):
        with pytest.raises(UnmappedBankingToolError, match="new_experimental_tool"):
            validate_tool_coverage(["get_balance", "new_experimental_tool"])

    def test_error_lists_every_unmapped_tool(self):
        with pytest.raises(UnmappedBankingToolError) as exc_info:
            validate_tool_coverage(["unmapped_a", "unmapped_b", "get_balance"])
        message = str(exc_info.value)
        assert "unmapped_a" in message
        assert "unmapped_b" in message

    def test_empty_input_passes(self):
        validate_tool_coverage([])  # should not raise


def test_source_mapping_version_is_a_non_empty_string():
    assert isinstance(SOURCE_MAPPING_VERSION, str)
    assert SOURCE_MAPPING_VERSION.strip() != ""


def test_source_mapping_version_identifies_content_scored_transactions():
    assert SOURCE_MAPPING_VERSION == "banking-v2-content-scored-transactions"
