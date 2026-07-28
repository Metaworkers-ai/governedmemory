"""GovernedMemory <-> AgentDojo Banking-suite integration.

Status: identity + context + registry + policy + GovernedRunInitializer +
GovernedFunctionFactory + source-tool wrapper + privileged-tool wrapper +
custom benchmark runner + baseline (ungoverned) runner + benchmark metrics
(implementation order steps 2-11). See docs/integrations/agentdojo-progress.md
for the full history, including the Option B content-scoring fix and the
security-semantics bug found during Step 10 validation.
"""

from integrations.agentdojo.banking_mapping import (
    PRIVILEGED_ACTIONS,
    SOURCE_MAPPING_VERSION,
    SOURCE_TYPE_BY_TOOL,
    UnmappedBankingToolError,
    validate_tool_coverage,
)
from integrations.agentdojo.banking_policy import ensure_banking_policy
from integrations.agentdojo.benchmark import (
    CONFIGURATIONS,
    compute_metrics,
    compute_metrics_by_configuration,
)
from integrations.agentdojo.context import ActionEvent, EvidenceRef, RunGovernanceContext
from integrations.agentdojo.identity import RunIdentity, generate_run_identity
from integrations.agentdojo.registry import (
    RegistryCollisionError,
    RegistryMissError,
    RunContextRegistry,
    default_registry,
)

__all__ = [
    "ActionEvent",
    "EvidenceRef",
    "RunGovernanceContext",
    "RunIdentity",
    "generate_run_identity",
    "RegistryCollisionError",
    "RegistryMissError",
    "RunContextRegistry",
    "default_registry",
    "SOURCE_TYPE_BY_TOOL",
    "PRIVILEGED_ACTIONS",
    "SOURCE_MAPPING_VERSION",
    "UnmappedBankingToolError",
    "validate_tool_coverage",
    "ensure_banking_policy",
    "CONFIGURATIONS",
    "compute_metrics",
    "compute_metrics_by_configuration",
]

# function_factory.py and run_initializer.py both import real `agentdojo`
# classes at module level (Function/Depends/AbortAgentError,
# BasePipelineElement/AbortAgentError respectively), unlike everything
# else in this package. Guard both imports so `import integrations.agentdojo`
# -- and therefore every other submodule import, since Python runs this
# __init__ first -- still succeeds in an environment that hasn't installed
# `agentdojo` (e.g. running only tests/unit/test_agentdojo_context.py
# without requirements-agentdojo.txt).
try:
    from integrations.agentdojo.function_factory import (
        HIDDEN_ENV_DEPENDENCY_NAME,
        GovernanceInfrastructureError,
        GovernedFunctionFactory,
        GovernedRunHook,
        HiddenDependencyCollisionError,
    )

    __all__ += [
        "GovernedFunctionFactory",
        "GovernedRunHook",
        "GovernanceInfrastructureError",
        "HiddenDependencyCollisionError",
        "HIDDEN_ENV_DEPENDENCY_NAME",
    ]
except ImportError:
    GovernedFunctionFactory = None  # type: ignore[assignment]

try:
    from integrations.agentdojo.run_initializer import GovernedRunInitializer

    __all__.append("GovernedRunInitializer")
except ImportError:
    GovernedRunInitializer = None  # type: ignore[assignment]

try:
    from integrations.agentdojo.source_tool_wrapper import (
        PrivilegedToolMisuseError,
        ToolOutputFormatter,
        make_banking_source_tool_hook,
        make_source_tool_hook,
    )

    __all__ += [
        "PrivilegedToolMisuseError",
        "ToolOutputFormatter",
        "make_banking_source_tool_hook",
        "make_source_tool_hook",
    ]
except ImportError:
    make_source_tool_hook = None  # type: ignore[assignment]

try:
    from integrations.agentdojo.privileged_tool_wrapper import (
        NonPrivilegedToolMisuseError,
        PrivilegedActionDenied,
        make_banking_privileged_tool_hook,
        make_privileged_tool_hook,
    )

    __all__ += [
        "NonPrivilegedToolMisuseError",
        "PrivilegedActionDenied",
        "make_banking_privileged_tool_hook",
        "make_privileged_tool_hook",
    ]
except ImportError:
    make_privileged_tool_hook = None  # type: ignore[assignment]

try:
    from integrations.agentdojo.runner import (
        build_baseline_pipeline,
        build_baseline_result_artifact,
        build_governed_pipeline,
        build_result_artifact,
        make_banking_hook_selector,
        make_governed_runtime_class,
        run_baseline_banking_task,
        run_governed_banking_task,
    )

    __all__ += [
        "build_governed_pipeline",
        "build_result_artifact",
        "make_banking_hook_selector",
        "make_governed_runtime_class",
        "run_governed_banking_task",
        "build_baseline_pipeline",
        "build_baseline_result_artifact",
        "run_baseline_banking_task",
    ]
except ImportError:
    run_governed_banking_task = None  # type: ignore[assignment]
