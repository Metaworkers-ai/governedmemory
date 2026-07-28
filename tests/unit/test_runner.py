"""Unit tests for integrations/agentdojo/runner.py.

Requires `agentdojo` -- skips cleanly if it's not installed. Uses a
policy-aware FakeStore (no Docker needed) but exercises the REAL Banking
suite (`agentdojo.task_suite.load_suites.get_suite`), REAL ground-truth
task data, REAL `AgentPipeline`/`ToolsExecutionLoop`/`ToolsExecutor`, and
REAL `TaskSuite.run_task_with_pipeline` -- only the storage backend is
faked, same pattern as Steps 6-8.

`GroundTruthPipeline` (a real, built-in AgentDojo pipeline element that
executes a task's own `ground_truth()` calls directly) stands in for a
real LLM for the read-only tests, so they need no API key and no network
access. For tests where a privileged action might be denied,
`_NonRaisingGroundTruthLLM` (defined below) is used instead -- see its
docstring for why.
"""

from __future__ import annotations

import pytest

agentdojo = pytest.importorskip("agentdojo")

from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline  # noqa: E402
from agentdojo.agent_pipeline.basic_elements import SystemMessage  # noqa: E402
from agentdojo.agent_pipeline.ground_truth_pipeline import GroundTruthPipeline  # noqa: E402
from agentdojo.agent_pipeline.tool_execution import ToolsExecutionLoop  # noqa: E402
from agentdojo.functions_runtime import EmptyEnv, FunctionsRuntime, make_function  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402

from core.models import (  # noqa: E402
    MemoryRecord,
    Policy,
    PrivilegeRules,
    SourceType,
    Taint,
    Trust,
    WriteRequest,
)
from integrations.agentdojo.banking_mapping import UnmappedBankingToolError  # noqa: E402
from integrations.agentdojo.registry import RunContextRegistry  # noqa: E402
from integrations.agentdojo.runner import (  # noqa: E402
    build_baseline_pipeline,
    build_baseline_result_artifact,
    build_governed_pipeline,
    build_result_artifact,
    make_governed_runtime_class,
    run_baseline_banking_task,
    run_governed_banking_task,
)


class _NonRaisingGroundTruthLLM:
    """Like AgentDojo's built-in `GroundTruthPipeline`, but calls
    `run_function` with `raise_on_error=False` -- matching how a real LLM
    + `ToolsExecutor` pipeline actually behaves in production. AgentDojo's
    own `GroundTruthPipeline` uses `raise_on_error=True`, which means a
    `PrivilegedActionDenied` raised by our own wrapper propagates as an
    uncaught exception all the way out of `run_task_with_pipeline` instead
    of becoming a normal tool-error message the way it does for the real
    `ToolsExecutor` (which never passes `raise_on_error=True`). This stand-in
    exists so these tests exercise the actual production code path rather
    than a `GroundTruthPipeline`-specific quirk -- see this step's
    progress-report writeup for the full explanation.
    """

    def __init__(self, task):
        self._task = task

    def query(self, query, runtime, env=None, messages=(), extra_args=None):
        from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
        from agentdojo.functions_runtime import EmptyEnv
        from agentdojo.types import (
            ChatAssistantMessage,
            ChatToolResultMessage,
            text_content_block_from_string,
        )

        env = env if env is not None else EmptyEnv()
        extra_args = extra_args if extra_args is not None else {}
        new_messages = list(messages)
        for tool_call in self._task.ground_truth(env):
            new_messages.append(
                ChatAssistantMessage(
                    role="assistant",
                    tool_calls=[tool_call],
                    content=[text_content_block_from_string("")],
                )
            )
            result, error = runtime.run_function(
                env, tool_call.function, tool_call.args, raise_on_error=False
            )
            new_messages.append(
                ChatToolResultMessage(
                    role="tool",
                    content=[
                        text_content_block_from_string("" if error else tool_result_to_str(result))
                    ],
                    tool_call=tool_call,
                    tool_call_id=None,
                    error=error,
                )
            )
        new_messages.append(
            ChatAssistantMessage(
                role="assistant",
                content=[text_content_block_from_string(self._task.GROUND_TRUTH_OUTPUT)],
                tool_calls=None,
            )
        )
        return query, runtime, env, new_messages, extra_args


class FakePolicyAwareStore:
    """Approximates real MemoryStore behavior for these tests: write()
    assigns taint from provenance.source_type (mirroring
    core/governance/service.py's real formula for the untrusted source
    types this suite actually uses), upsert_policy()/get_policy() actually
    persist and read back a real Policy, and check_privilege() evaluates
    against it using the same require_trust/privileged_actions logic as
    core/policy_engine/evaluator.py's real evaluate_privileged_action()."""

    def __init__(self) -> None:
        self.records: dict[str, MemoryRecord] = {}
        self.policies: dict[tuple[str, str], Policy] = {}
        self._next_id = 0

    def write(self, req: WriteRequest) -> MemoryRecord:
        self._next_id += 1
        is_untrusted_source = req.provenance.source_type in (
            SourceType.UNTRUSTED_EMAIL,
            SourceType.UNTRUSTED_WEB,
        )
        taint = Taint.UNTRUSTED if is_untrusted_source else Taint.TRUSTED
        record = MemoryRecord(
            id=f"mem-{self._next_id}",
            tenant_id=req.tenant_id,
            customer_id=req.customer_id,
            agent_id=req.agent_id,
            session_id=req.session_id,
            content=req.content,
            provenance=req.provenance,
            trust=Trust(taint=taint, injection_score=0.9 if taint == Taint.UNTRUSTED else 0.01),
            purpose=req.purpose,
            audit_id=f"audit-{self._next_id}",
        )
        self.records[record.id] = record
        return record

    def upsert_policy(self, policy: Policy) -> Policy:
        self.policies[(policy.tenant_id, policy.id)] = policy
        return policy

    def get_policy(self, tenant_id: str, policy_id: str = "default") -> Policy:
        return self.policies.get((tenant_id, policy_id)) or Policy(
            id=policy_id, tenant_id=tenant_id
        )

    def check_privilege(self, memory_id, tenant_id, action, agent_id, session_id) -> bool:
        record = self.records.get(memory_id)
        if record is None:
            return False
        policy = self.get_policy(tenant_id, record.purpose.policy_id)
        if action not in policy.privilege_rules.privileged_actions:
            return True
        if policy.privilege_rules.require_trust and record.trust.taint != Taint.TRUSTED:
            return False
        return True


@pytest.fixture(scope="module")
def banking_suite():
    return get_suite("v1.2.2", "banking")


class TestBuildGovernedPipeline:
    def test_element_sequence_matches_the_lld(self):
        store = FakePolicyAwareStore()
        llm = GroundTruthPipeline(None)
        registry = RunContextRegistry()

        pipeline = build_governed_pipeline(store, llm, registry=registry)

        assert isinstance(pipeline, AgentPipeline)
        kinds = [type(e).__name__ for e in pipeline.elements]
        assert kinds == [
            "SystemMessage",
            "InitQuery",
            "GovernedRunInitializer",
            "GroundTruthPipeline",
            "ToolsExecutionLoop",
        ]

    def test_tools_execution_loop_wraps_the_same_llm(self):
        store = FakePolicyAwareStore()
        llm = GroundTruthPipeline(None)
        registry = RunContextRegistry()

        pipeline = build_governed_pipeline(store, llm, registry=registry)

        loop = pipeline.elements[-1]
        assert isinstance(loop, ToolsExecutionLoop)
        assert llm in loop.elements

    def test_default_system_message_is_used_when_none_given(self):
        store = FakePolicyAwareStore()
        pipeline = build_governed_pipeline(
            store, GroundTruthPipeline(None), registry=RunContextRegistry()
        )
        system_element = pipeline.elements[0]
        assert isinstance(system_element, SystemMessage)
        assert len(system_element.system_message) > 0

    def test_custom_system_message_is_used_when_given(self):
        store = FakePolicyAwareStore()
        pipeline = build_governed_pipeline(
            store,
            GroundTruthPipeline(None),
            registry=RunContextRegistry(),
            system_message="custom prompt",
        )
        assert pipeline.elements[0].system_message == "custom prompt"


def get_balance() -> float:
    """Gets the account balance.

    :return: the balance.
    """
    return 500.0


def send_money(amount: float, recipient: str) -> str:
    """Sends money to a recipient.

    :param amount: how much to send.
    :param recipient: who to send it to.
    """
    return f"sent {amount} to {recipient}"


class TestMakeGovernedRuntimeClass:
    def test_wraps_every_function_it_is_given(self):
        store = FakePolicyAwareStore()
        registry = RunContextRegistry()
        runtime_class = make_governed_runtime_class(store, registry=registry)

        env = EmptyEnv()
        registry.register(env, _make_context())
        runtime = runtime_class([make_function(get_balance), make_function(send_money)])

        assert isinstance(runtime, FunctionsRuntime)
        assert set(runtime.functions) == {"get_balance", "send_money"}

    def test_trusted_read_then_privileged_action_is_allowed(self):
        store = FakePolicyAwareStore()
        registry = RunContextRegistry()
        context = _make_context()
        env = EmptyEnv()
        registry.register(env, context)
        store.upsert_policy(
            Policy(
                id="default",
                tenant_id=context.tenant_id,
                privilege_rules=PrivilegeRules(
                    privileged_actions=["send_money"], require_trust=True
                ),
            )
        )
        runtime_class = make_governed_runtime_class(store, registry=registry)
        runtime = runtime_class([make_function(get_balance), make_function(send_money)])

        runtime.run_function(env, "get_balance", {}, raise_on_error=True)
        result, error = runtime.run_function(env, "send_money", {"amount": 5.0, "recipient": "x"})

        assert error is None
        assert result == "sent 5.0 to x"


def _make_context():
    from integrations.agentdojo.context import RunGovernanceContext
    from integrations.agentdojo.identity import generate_run_identity

    return RunGovernanceContext(
        identity=generate_run_identity(
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_x",
            agent_id="test-agent",
        )
    )


class TestBuildResultArtifact:
    def test_shape_matches_the_lld_spec(self):
        from integrations.agentdojo.context import ActionEvent, EvidenceRef

        context = _make_context()
        context.append_evidence(
            EvidenceRef(
                memory_id="mem-1",
                sequence=context.next_sequence(),
                source_kind="user_input",
                tool_name=None,
                source_ref="agentdojo:user:user_task_x",
                taint="trusted",
                injection_score=0.01,
                policy_id="default",
                audit_id="audit-1",
            )
        )
        context.append_evidence(
            EvidenceRef(
                memory_id="mem-2",
                sequence=context.next_sequence(),
                source_kind="tool_output",
                tool_name="get_most_recent_transactions",
                source_ref="agentdojo:banking:get_most_recent_transactions:1",
                taint="untrusted",
                injection_score=0.9,
                policy_id="default",
                audit_id="audit-2",
            )
        )
        context.append_action(
            ActionEvent(
                sequence=context.next_sequence(),
                tool_name="send_money",
                evidence_ids=("mem-1", "mem-2"),
                allowed=False,
                denied_memory_ids=("mem-2",),
                reason="denied",
            )
        )

        artifact = build_result_artifact(
            context,
            agentdojo_version="0.1.35",
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_3",
            injection_task_id="injection_task_0",
            model="test-model",
            seed=0,
            utility=False,
            security=True,
        )

        assert artifact["agentdojo_version"] == "0.1.35"
        assert artifact["benchmark_version"] == "1.2.2"
        assert artifact["suite"] == "banking"
        assert artifact["user_task_id"] == "user_task_3"
        assert artifact["injection_task_id"] == "injection_task_0"
        assert artifact["model"] == "test-model"
        assert artifact["seed"] == 0
        assert artifact["tenant_id"] == context.tenant_id
        assert artifact["session_id"] == context.session_id
        assert artifact["agentdojo"] == {"utility": False, "security": True}
        assert artifact["governance"]["evidence_count"] == 2
        assert artifact["governance"]["trusted_count"] == 1
        assert artifact["governance"]["untrusted_count"] == 1
        assert artifact["governance"]["privileged_attempts"] == 1
        assert artifact["governance"]["allowed_actions"] == 0
        assert artifact["governance"]["blocked_actions"] == 1
        assert artifact["governance"]["memory_ids"] == ["mem-1", "mem-2"]
        assert artifact["governance"]["audit_ids"] == ["audit-1", "audit-2"]
        assert (
            artifact["governance"]["source_mapping_version"]
            == "banking-v2-content-scored-transactions"
        )
        assert artifact["status"] == "completed"
        assert artifact["infrastructure_errors"] == []

    def test_infrastructure_error_status(self):
        context = _make_context()
        context.mark_infrastructure_error("database unavailable")

        artifact = build_result_artifact(
            context,
            agentdojo_version="0.1.35",
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_3",
            injection_task_id=None,
            model="test-model",
            seed=0,
            utility=False,
            security=None,
        )

        assert artifact["status"] == "infrastructure_error"
        assert artifact["infrastructure_errors"] == ["database unavailable"]

    def test_no_credentials_or_raw_content_leaked(self):
        """Only ids, counts, and booleans -- never memory content itself."""
        context = _make_context()
        artifact = build_result_artifact(
            context,
            agentdojo_version="0.1.35",
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_3",
            injection_task_id=None,
            model="test-model",
            seed=0,
            utility=True,
            security=None,
        )
        serialized = str(artifact)
        assert "content" not in artifact["governance"]
        assert "wire" not in serialized.lower()  # sanity: no leaked injected text


class TestRunGovernedBankingTaskEndToEnd:
    """Exercised against the REAL Banking suite's real ground-truth data.

    Banking v2 content-scores `get_most_recent_transactions`: benign
    transaction descriptions delivered by the bank API remain trusted,
    while scanner-flagged descriptions become untrusted. `read_file`
    remains untrusted by source.
    """

    def test_user_task_3_benign_ground_truth_is_allowed(self, banking_suite):
        """user_task_3's ground truth is
        [get_most_recent_transactions, send_money] -- the transactions
        read contains benign data, so its content-scored evidence remains
        trusted and send_money is allowed.

        Uses _NonRaisingGroundTruthLLM rather than AgentDojo's own
        GroundTruthPipeline: the built-in one calls run_function with
        raise_on_error=True, which would let PrivilegedActionDenied
        propagate as an uncaught exception instead of becoming a normal
        tool-error message -- see that stand-in's docstring."""
        store = FakePolicyAwareStore()
        user_task = banking_suite.user_tasks["user_task_3"]
        llm = _NonRaisingGroundTruthLLM(user_task)

        result = run_governed_banking_task(
            banking_suite,
            user_task,
            None,
            banking_suite.get_injection_vector_defaults(),
            llm,
            store,
            agent_id="test-agent",
        )

        assert result["governance"]["blocked_actions"] == 0
        assert result["governance"]["allowed_actions"] == 1
        assert result["governance"]["untrusted_count"] == 0
        assert result["agentdojo"]["utility"] is True
        assert result["status"] == "completed"
        assert result["infrastructure_errors"] == []

    def test_read_only_task_has_zero_privileged_attempts_and_succeeds(self, banking_suite):
        """user_task_1's ground truth is just
        [get_most_recent_transactions] -- no privileged action at all, so
        nothing can be blocked, and the task genuinely succeeds."""
        store = FakePolicyAwareStore()
        user_task = banking_suite.user_tasks["user_task_1"]
        llm = GroundTruthPipeline(user_task)

        result = run_governed_banking_task(
            banking_suite,
            user_task,
            None,
            banking_suite.get_injection_vector_defaults(),
            llm,
            store,
            agent_id="test-agent",
        )

        assert result["governance"]["privileged_attempts"] == 0
        assert result["governance"]["blocked_actions"] == 0
        assert result["agentdojo"]["utility"] is True
        assert result["injection_task_id"] is None
        assert result["agentdojo"]["security"] is None  # no injection_task given

    def test_evidence_count_includes_the_initial_prompt(self, banking_suite):
        store = FakePolicyAwareStore()
        user_task = banking_suite.user_tasks["user_task_1"]
        llm = GroundTruthPipeline(user_task)

        result = run_governed_banking_task(
            banking_suite,
            user_task,
            None,
            banking_suite.get_injection_vector_defaults(),
            llm,
            store,
            agent_id="test-agent",
        )

        # Initial prompt + benign content-scored transaction result.
        assert result["governance"]["evidence_count"] == 2
        assert result["governance"]["trusted_count"] == 2
        assert result["governance"]["untrusted_count"] == 0

    def test_registry_is_cleaned_up_after_the_attempt(self, banking_suite):
        from integrations.agentdojo.registry import default_registry

        store = FakePolicyAwareStore()
        user_task = banking_suite.user_tasks["user_task_1"]
        llm = GroundTruthPipeline(user_task)

        assert len(default_registry) == 0
        run_governed_banking_task(
            banking_suite,
            user_task,
            None,
            banking_suite.get_injection_vector_defaults(),
            llm,
            store,
            agent_id="test-agent",
        )
        assert len(default_registry) == 0  # cleaned up whether or not it succeeded

    def test_fails_setup_before_creating_any_identity_for_an_unmapped_tool(
        self, banking_suite, monkeypatch
    ):
        from agentdojo.functions_runtime import Function

        bogus_tool = Function(
            name="totally_new_banking_tool",
            description="not in SOURCE_TYPE_BY_TOOL.",
            parameters=make_function(get_balance).parameters,
            dependencies={},
            run=lambda: None,
            full_docstring="not in SOURCE_TYPE_BY_TOOL.",
            return_type=None,
        )
        monkeypatch.setattr(banking_suite, "tools", [*banking_suite.tools, bogus_tool])
        store = FakePolicyAwareStore()
        user_task = banking_suite.user_tasks["user_task_1"]

        with pytest.raises(UnmappedBankingToolError):
            run_governed_banking_task(
                banking_suite,
                user_task,
                None,
                banking_suite.get_injection_vector_defaults(),
                GroundTruthPipeline(user_task),
                store,
                agent_id="test-agent",
            )

        assert store.policies == {}, (
            "policy setup must not happen if tool coverage validation fails first"
        )

    def test_injection_task_id_and_security_key_are_populated_when_given(self, banking_suite):
        store = FakePolicyAwareStore()
        user_task = banking_suite.user_tasks["user_task_1"]
        injection_task = banking_suite.injection_tasks["injection_task_0"]
        llm = GroundTruthPipeline(user_task)

        result = run_governed_banking_task(
            banking_suite,
            user_task,
            injection_task,
            banking_suite.get_injection_vector_defaults(),
            llm,
            store,
            agent_id="test-agent",
        )

        assert result["injection_task_id"] == "injection_task_0"
        assert isinstance(result["agentdojo"]["security"], bool)

    def test_tenant_id_is_unique_per_call(self, banking_suite):
        store = FakePolicyAwareStore()
        user_task = banking_suite.user_tasks["user_task_1"]

        result_a = run_governed_banking_task(
            banking_suite,
            user_task,
            None,
            banking_suite.get_injection_vector_defaults(),
            GroundTruthPipeline(user_task),
            store,
            agent_id="test-agent",
        )
        result_b = run_governed_banking_task(
            banking_suite,
            user_task,
            None,
            banking_suite.get_injection_vector_defaults(),
            GroundTruthPipeline(user_task),
            store,
            agent_id="test-agent",
        )

        assert result_a["tenant_id"] != result_b["tenant_id"]


class TestBuildBaselinePipeline:
    def test_element_sequence_has_no_governed_run_initializer(self):
        llm = GroundTruthPipeline(None)
        pipeline = build_baseline_pipeline(llm)

        kinds = [type(e).__name__ for e in pipeline.elements]
        assert kinds == ["SystemMessage", "InitQuery", "GroundTruthPipeline", "ToolsExecutionLoop"]
        assert "GovernedRunInitializer" not in kinds

    def test_shares_the_same_default_system_message_as_the_governed_pipeline(self):
        baseline = build_baseline_pipeline(GroundTruthPipeline(None))
        governed = build_governed_pipeline(
            FakePolicyAwareStore(), GroundTruthPipeline(None), registry=RunContextRegistry()
        )

        assert baseline.elements[0].system_message == governed.elements[0].system_message


class TestBuildBaselineResultArtifact:
    def test_shape_has_no_governance_block(self):
        artifact = build_baseline_result_artifact(
            agentdojo_version="0.1.35",
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_3",
            injection_task_id=None,
            model="test-model",
            seed=0,
            utility=True,
            security=None,
        )

        assert artifact["governance"] is None
        assert artifact["tenant_id"] is None
        assert artifact["session_id"] is None
        assert artifact["status"] == "completed"
        assert artifact["agentdojo"] == {"utility": True, "security": None}


class TestRunBaselineBankingTask:
    """The control path for LLD section 16 configs 1 and 3 -- no
    MemoryStore, no governance, AgentDojo's own default runtime running
    suite.tools completely unmodified."""

    def test_user_task_3_succeeds_at_the_baseline(self, banking_suite):
        """Proves the baseline (ungoverned) control path works for a real
        task with a privileged action in its ground truth. On the original
        `banking-v1` mapping, this same task was blocked when governed
        (see the pre-Option-B history in the progress doc's section 5) --
        with `banking-v2-content-scored-transactions` (Option B), the
        governed path now allows this task too
        (TestRunGovernedBankingTaskEndToEnd::test_user_task_3_benign_ground_truth_is_allowed),
        so this baseline result is no longer a contrasting "governed
        blocks it, baseline doesn't" case on this branch -- it's simply
        confirmation that the ungoverned control path itself is correct."""
        user_task = banking_suite.user_tasks["user_task_3"]
        llm = GroundTruthPipeline(user_task)

        result = run_baseline_banking_task(
            banking_suite,
            user_task,
            None,
            banking_suite.get_injection_vector_defaults(),
            llm,
            model="test-model",
        )

        assert result["agentdojo"]["utility"] is True
        assert result["governance"] is None

    def test_read_only_task_also_succeeds_at_baseline(self, banking_suite):
        user_task = banking_suite.user_tasks["user_task_1"]
        llm = GroundTruthPipeline(user_task)

        result = run_baseline_banking_task(
            banking_suite,
            user_task,
            None,
            banking_suite.get_injection_vector_defaults(),
            llm,
            model="test-model",
        )

        assert result["agentdojo"]["utility"] is True

    def test_injection_task_populates_security_key(self, banking_suite):
        user_task = banking_suite.user_tasks["user_task_1"]
        injection_task = banking_suite.injection_tasks["injection_task_0"]
        llm = GroundTruthPipeline(user_task)

        result = run_baseline_banking_task(
            banking_suite,
            user_task,
            injection_task,
            banking_suite.get_injection_vector_defaults(),
            llm,
            model="test-model",
        )

        assert result["injection_task_id"] == "injection_task_0"
        assert isinstance(result["agentdojo"]["security"], bool)

    def test_no_injection_task_leaves_security_none(self, banking_suite):
        user_task = banking_suite.user_tasks["user_task_1"]
        llm = GroundTruthPipeline(user_task)

        result = run_baseline_banking_task(
            banking_suite,
            user_task,
            None,
            banking_suite.get_injection_vector_defaults(),
            llm,
            model="test-model",
        )

        assert result["agentdojo"]["security"] is None
