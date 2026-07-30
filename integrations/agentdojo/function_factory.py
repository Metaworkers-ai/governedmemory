"""GovernedFunctionFactory: clones an AgentDojo `Function`, preserving its
public tool schema exactly, and routes every call through a governance
hook via a hidden environment dependency.

See the reviewed low-level design, section 8 ("Context lookup") and
section 9 ("Function wrapping contract"):

- Every cloned `Function` preserves name, description, the LLM-visible
  parameter schema, return type, and the original's own dependencies.
- The factory adds only one thing: a hidden dependency that resolves to
  the current AgentDojo environment object, so the wrapped `run` can look
  up this attempt's `RunGovernanceContext` from the registry (Step 2)
  without that dependency ever appearing in the tool's parameter schema or
  being visible to the LLM.

Why this is safe, confirmed against `agentdojo==0.1.35`'s real source
(`agentdojo/functions_runtime.py`):

- `Function.parameters` (the LLM-visible schema) is built once, by
  `make_function`, from the *original* function's docstring-documented
  `:param:` entries -- it is copied here as-is and never touched again.
- `FunctionsRuntime.run_function` validates only against `f.parameters`
  (`f.parameters.model_validate(resolved_kwargs)`), so an extra
  dependency-resolved kwarg that isn't part of that schema is never
  validated and never rejected.
- Every entry in `f.dependencies` -- both the tool's original ones and the
  one added here -- gets resolved from `env` and merged into the kwargs
  actually passed to `f.run(**kwargs_with_deps)`. That merge is exactly
  what lets the wrapped `run` receive the hidden environment value
  alongside the tool's normal arguments, with zero AgentDojo-side changes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from agentdojo.agent_pipeline.errors import AbortAgentError
from agentdojo.functions_runtime import Depends, Function

from integrations.agentdojo.context import RunGovernanceContext
from integrations.agentdojo.registry import RegistryMissError, RunContextRegistry, default_registry

# Deliberately unlikely to collide with a real Banking tool parameter name.
# wrap() defensively refuses to clone a function that already defines a
# dependency under this exact name (see the collision guard below) rather
# than silently overwriting it.
HIDDEN_ENV_DEPENDENCY_NAME = "__governed_memory_env__"

# hook(context, original_run, explicit_kwargs) -> whatever original_run
# would have returned (or raises). `explicit_kwargs` is every kwarg
# `run_function` resolved for the *original* function -- its own explicit
# LLM-supplied arguments plus its own (non-hidden) dependency-resolved
# ones -- with the hidden environment kwarg already removed. Step 6/7
# wrappers (source-tool / privileged-tool) are exactly one hook each; this
# factory has no opinion on what a hook does with `original_run` or on how
# it handles errors -- see the module docstring's "original return value
# and error behavior... except for an explicit governance denial" rule,
# which is the hook's responsibility, not this factory's.
GovernedRunHook = Callable[[RunGovernanceContext, Callable[..., Any], dict[str, Any]], Any]


class HiddenDependencyCollisionError(Exception):
    """The original function already defines a dependency under
    `HIDDEN_ENV_DEPENDENCY_NAME`. Cloning it would silently overwrite that
    dependency with the environment-lookup one instead of adding a new,
    separate hidden dependency -- refuse instead of guessing which one the
    caller meant."""


class GovernanceInfrastructureError(Exception):
    """A `GovernedRunHook` raises this to signal an infrastructure failure
    that must abort the current attempt (e.g. a GovernedMemory write or
    check_privilege() call failed for reasons unrelated to governance
    policy -- a database outage, not a taint decision).

    Hooks raise this rather than `agentdojo`'s own `AbortAgentError`
    directly, for two reasons: hooks don't need to import `agentdojo` at
    all this way (source-tool and privileged-tool wrapper modules stay
    decoupled from AgentDojo's exception types), and a hook never has
    direct access to the AgentDojo environment object that
    `AbortAgentError` requires -- only the factory's `governed_run`
    closure does, since it's the one that resolved `env` from the hidden
    dependency. `wrap()` catches this and re-raises as `AbortAgentError`
    with that `env` filled in.
    """


class GovernedFunctionFactory:
    """Clones AgentDojo `Function` objects for exactly one purpose: routing
    every call through a `GovernedRunHook`, via a hidden environment
    dependency resolved from the registry supplied at construction time.
    """

    def __init__(self, registry: RunContextRegistry = default_registry) -> None:
        self.registry = registry

    def wrap(self, original: Function, hook: GovernedRunHook) -> Function:
        """Return a new `Function` with the same public schema as
        `original`, whose `run` resolves this attempt's
        `RunGovernanceContext` and delegates to `hook(context,
        original.run, explicit_kwargs)`.

        Raises:
            HiddenDependencyCollisionError: if `original` already declares
                a dependency named `HIDDEN_ENV_DEPENDENCY_NAME`.
        """
        if HIDDEN_ENV_DEPENDENCY_NAME in original.dependencies:
            raise HiddenDependencyCollisionError(
                f"function {original.name!r} already declares a dependency "
                f"named {HIDDEN_ENV_DEPENDENCY_NAME!r}; cannot add the "
                f"hidden environment dependency without overwriting it"
            )

        # Copy, not alias: mutating the clone's dependencies must never
        # affect the original Function object (e.g. if the same original
        # is wrapped twice with different hooks for some reason).
        dependencies = dict(original.dependencies)
        dependencies[HIDDEN_ENV_DEPENDENCY_NAME] = Depends(lambda env: env)

        registry = self.registry
        original_name = original.name
        original_run = original.run

        def governed_run(**kwargs: Any) -> Any:
            env = kwargs.pop(HIDDEN_ENV_DEPENDENCY_NAME)
            try:
                context = registry.get(env)
            except RegistryMissError as exc:
                # No prior message history is available at this layer, and
                # none is needed: AbortAgentError's own __init__ appends a
                # synthesized assistant message to whatever list it's
                # given, so an empty list still produces a well-formed
                # message history for the pipeline to surface.
                raise AbortAgentError(
                    f"{original_name}: {exc}",
                    [],
                    env,
                ) from exc
            try:
                return hook(context, original_run, kwargs)
            except GovernanceInfrastructureError as exc:
                raise AbortAgentError(
                    f"{original_name}: {exc}",
                    [],
                    env,
                ) from exc

        return Function(
            name=original.name,
            description=original.description,
            parameters=original.parameters,
            dependencies=dependencies,
            run=governed_run,
            full_docstring=original.full_docstring,
            return_type=original.return_type,
        )

    def wrap_all(
        self, functions: Mapping[str, Function], hook_for: Callable[[Function], GovernedRunHook]
    ) -> dict[str, Function]:
        """Convenience for wrapping every function in a mapping (e.g. an
        already-built `FunctionsRuntime.functions` dict), choosing each
        one's hook via `hook_for(original)` -- e.g. a source-tool hook for
        read tools and a privileged-tool hook for mutating ones (Steps 6
        and 7). Returns a new `{name: Function}` mapping; does not mutate
        `functions`."""
        return {name: self.wrap(fn, hook_for(fn)) for name, fn in functions.items()}
