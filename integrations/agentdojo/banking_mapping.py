"""Banking-suite tool mapping tables (LLD sections 11 and 12).

Two explicit, validated tables instead of ad hoc inference while writing
adapter code -- this is exactly what docs/traction-roadmap.md's open
question 3 ("Source-type mapping per Banking tool") asked for:

- `SOURCE_TYPE_BY_TOOL`: which `SourceType` a Banking tool's OUTPUT should
  be written under when a source/read-tool wrapper governs it.
- `PRIVILEGED_ACTIONS`: which Banking tools mutate money, credentials,
  scheduled payments, or customer state, and therefore require
  `check_privilege()` before their side effects run.

Both tables were confirmed against `agentdojo==0.1.35`'s actual Banking
suite tool set -- see `tests/contract/test_agentdojo_contract.py`'s
`EXPECTED_BANKING_TOOL_NAMES` -- not assumed from AgentDojo's docs.
"""

from __future__ import annotations

from collections.abc import Iterable

from core.models import SourceType

# LLD section 11. Every installed Banking tool must have an entry here.
# `validate_tool_coverage()` below enforces this at runner setup time --
# an unmapped tool must fail setup, per the LLD's rule, "No tool silently
# defaults to trusted."
SOURCE_TYPE_BY_TOOL: dict[str, SourceType] = {
    # Read/source tools: the text written to GovernedMemory is the tool's
    # OUTPUT, and its source_type reflects where that output actually
    # originates -- not whether the tool call itself was requested by a
    # trusted user.
    # Banking v2 treats the bank API as a trusted delivery channel while
    # still scanning the formatted transaction descriptions for injection
    # content on every MemoryStore.write(). A flagged description is tainted
    # untrusted by GovernanceEvaluationService even with this source type.
    "get_most_recent_transactions": SourceType.TRUSTED_SYSTEM,
    "read_file": SourceType.UNTRUSTED_WEB,
    "get_balance": SourceType.TRUSTED_SYSTEM,
    "get_iban": SourceType.TRUSTED_SYSTEM,
    "get_scheduled_transactions": SourceType.TRUSTED_SYSTEM,
    "get_user_info": SourceType.TRUSTED_SYSTEM,
    # Privileged/mutating tools: by the time one of these actually runs,
    # check_privilege() has already allowed it (see the privileged-tool
    # wrapper flow, LLD section 9) -- so its confirmation output is the
    # result of an authorized internal operation, hence trusted.
    "send_money": SourceType.TRUSTED_SYSTEM,
    "schedule_transaction": SourceType.TRUSTED_SYSTEM,
    "update_scheduled_transaction": SourceType.TRUSTED_SYSTEM,
    "update_password": SourceType.TRUSTED_SYSTEM,
    "update_user_info": SourceType.TRUSTED_SYSTEM,
}

# LLD section 12. Exact AgentDojo function names. GovernedMemory's shipped
# PrivilegeRules defaults are ["send_email", "refund", "escalate"] -- none
# of those match a Banking tool name, so relying on the default policy
# would leave every Banking action ungated. See banking_policy.py, which
# upserts a tenant-scoped policy using exactly this tuple.
PRIVILEGED_ACTIONS: tuple[str, ...] = (
    "send_money",
    "schedule_transaction",
    "update_scheduled_transaction",
    "update_password",
    "update_user_info",
)

# Recorded in benchmark result artifacts (LLD section 17,
# `governance.source_mapping_version`) so a later change to either table
# above is traceable in historical results instead of silently altering
# what old numbers meant.
SOURCE_MAPPING_VERSION = "banking-v3-per-record-scored-outputs"


class UnmappedBankingToolError(Exception):
    """An installed Banking tool has no entry in `SOURCE_TYPE_BY_TOOL`.

    Per the LLD: "The runner fails during setup if the installed Banking
    suite contains an unmapped tool ... No tool silently defaults to
    trusted." Callers should let this propagate and stop the runner, not
    catch it and fall back to a default source type.
    """


def validate_tool_coverage(installed_tool_names: Iterable[str]) -> None:
    """Raise `UnmappedBankingToolError` if any installed tool name has no
    entry in `SOURCE_TYPE_BY_TOOL`.

    Call this once at runner setup, against the tool names AgentDojo
    actually reports for the pinned suite (e.g. via
    `agentdojo.task_suite.load_suites.get_suite(...).tools`) -- never
    assume this module's table is exhaustive without checking it against
    the installed package.
    """
    installed = set(installed_tool_names)
    unmapped = installed - set(SOURCE_TYPE_BY_TOOL)
    if unmapped:
        raise UnmappedBankingToolError(
            f"no source_type mapping for Banking tool(s): {sorted(unmapped)}. "
            "Add them to SOURCE_TYPE_BY_TOOL in "
            "integrations/agentdojo/banking_mapping.py before running -- "
            "do not default an unmapped tool to trusted."
        )
