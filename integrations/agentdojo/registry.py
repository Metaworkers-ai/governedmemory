"""Thread-safe registry mapping an AgentDojo TaskEnvironment instance to its
RunGovernanceContext.

Wrapped tool functions (built in a later implementation step) need the
current attempt's governance context, but it must not become an
LLM-visible tool argument. AgentDojo's hidden-dependency mechanism
(`Depends`) resolves a value from the environment object at call time, so
the eventual tool wrapper looks the context up here by the environment's
identity rather than threading it through the tool's public schema.

See the reviewed low-level design, section 8 ("Context lookup"):

- The hidden dependency must not appear in the tool's parameter schema.
- Missing or duplicate context registration is an infrastructure error.
- Registry lookup and cleanup must be thread-safe.
- No evidence may be selected by querying "the latest row" from the
  database -- this registry only ever returns the ordered, explicit history
  a context itself accumulated (see context.py).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from integrations.agentdojo.context import RunGovernanceContext


class RegistryCollisionError(Exception):
    """Raised when a context is already registered for this environment.

    A collision means either a runner bug (registering the same
    environment twice without cleaning up the first registration) or an
    `id()` reuse race after a prior environment was garbage-collected
    without being unregistered first. Either way this is an infrastructure
    error for the attempt (see the LLD's failure-semantics table: "Context
    registry collision/miss -> Stop attempt") -- never silently overwritten.
    """


class RegistryMissError(Exception):
    """Raised when no context is registered for this environment.

    A wrapped tool hitting this means the environment was never registered
    (a runner bug) or was already cleaned up (a lifecycle bug). In both
    cases the correct response is to fail the tool call closed, not to
    silently proceed ungoverned.
    """


class RunContextRegistry:
    """Maps `id(environment)` -> RunGovernanceContext, guarded by a lock.

    Deliberately keyed by object identity with an explicit register/
    unregister lifecycle, rather than a weak-reference cache: the design
    wants a missing or duplicate registration to be a loud, immediate error,
    not something whose behavior depends on garbage-collection timing.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._contexts: dict[int, RunGovernanceContext] = {}
        # Holds a strong reference to each registered environment for the
        # lifetime of its entry, purely so id() cannot be reused by an
        # unrelated object while the entry is still considered live.
        self._environments: dict[int, object] = {}

    def register(self, environment: object, context: RunGovernanceContext) -> None:
        """Register `context` for `environment`.

        Raises:
            RegistryCollisionError: if `environment` already has a
                registered context -- call unregister() (or use the `run()`
                context manager) before registering a new attempt against
                the same environment object.
        """
        key = id(environment)
        with self._lock:
            if key in self._contexts:
                existing = self._contexts[key]
                raise RegistryCollisionError(
                    f"a RunGovernanceContext is already registered for this "
                    f"environment (existing tenant={existing.tenant_id!r}); "
                    f"unregister the previous attempt before registering a new one"
                )
            self._contexts[key] = context
            self._environments[key] = environment

    def get(self, environment: object) -> RunGovernanceContext:
        """Look up the context registered for `environment`.

        Raises:
            RegistryMissError: if nothing is registered -- callers (wrapped
                tools) must treat this as fail-closed, per the LLD's
                failure-semantics table, and must not fall back to
                proceeding ungoverned.
        """
        key = id(environment)
        with self._lock:
            try:
                return self._contexts[key]
            except KeyError as exc:
                raise RegistryMissError(
                    "no RunGovernanceContext registered for this environment "
                    "-- the runner must register() before the pipeline runs "
                    "and must not unregister() before it finishes"
                ) from exc

    def unregister(self, environment: object) -> None:
        """Remove the registration for `environment`, if any. Idempotent:
        calling this on an already-unregistered (or never-registered)
        environment is a no-op, so cleanup code can call it unconditionally
        in a `finally` block without an extra existence check."""
        key = id(environment)
        with self._lock:
            self._contexts.pop(key, None)
            self._environments.pop(key, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._contexts)

    @contextmanager
    def run(
        self, environment: object, context: RunGovernanceContext
    ) -> Iterator[RunGovernanceContext]:
        """Register `context` for `environment` for the duration of the
        `with` block, guaranteeing cleanup on both normal exit and any
        exception.

        This is the intended entrypoint for a benchmark runner: LLD section
        7 requires that "the in-memory run-context registry" is cleaned up
        "after the attempt, including exceptional exits," and this is
        exactly that guarantee expressed as a context manager.
        """
        self.register(environment, context)
        try:
            yield context
        finally:
            self.unregister(environment)


# A process-wide default instance. A custom benchmark runner may run many
# task attempts concurrently (LLD section 7: "Concurrent task runs do not
# cross-contaminate evidence" is a required test), and a single shared,
# lock-guarded registry -- keyed per environment instance -- is what makes
# that safe without every caller having to construct and thread through its
# own registry.
default_registry = RunContextRegistry()
