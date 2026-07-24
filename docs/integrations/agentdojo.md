# GovernedMemory + AgentDojo (Banking suite)

Status: **Steps 1–6 of 11 complete** (contract test; run identity, context,
and registry; Banking privileged-action policy; `GovernedRunInitializer`;
`GovernedFunctionFactory`; source/read-tool wrapper). No privileged-tool
gate, benchmark runner, or full benchmark run yet. This tracks Workstream A
(`docs/traction-roadmap.md`) Ticket 1/2. For the full implementation
history, design decisions, bug fixes, and test coverage, see
[`docs/integrations/agentdojo-progress.md`](./agentdojo-progress.md). This
page only covers the version pin and how to run the contract test that
validates it.

Supported contract version: **`agentdojo==0.1.35`** (benchmark version
`v1.2.2`). Do not claim compatibility with other AgentDojo releases until
the contract test suite below passes against them.

## Install

```bash
pip install -r requirements-agentdojo.txt
```

or

```bash
make install-agentdojo
```

## Contract test

Before any adapter code is written against AgentDojo's `Function` /
`FunctionsRuntime` / `ToolsExecutor` / Banking suite APIs, run:

```bash
pytest tests/contract/ -v
```

or

```bash
make test-agentdojo-contract
```

This suite does not touch GovernedMemory code — it only asserts that the
installed `agentdojo` package still behaves the way the integration design
assumes: `Function`/`Depends`/`FunctionsRuntime` field and method shapes,
the exact Banking suite tool set, `AbortAgentError`'s constructor shape, and
— most importantly — that `ToolsExecutor` executes every tool call in one
assistant message inside a single `query()` call, with no pipeline element
able to run between two tool calls in the same batch. That last fact is why
the integration wraps individual Banking tool functions rather than relying
on a single post-`ToolsExecutor` defense element for both evidence-writing
and privileged-action gating.

If `agentdojo` is not installed, the whole suite is skipped (same pattern as
`tests/integration/` skipping when Docker is unavailable) rather than
failing the rest of the test run.

### Known upstream quirk (0.1.35)

Importing `agentdojo.default_suites.v1.banking.task_suite` directly (e.g.
`from agentdojo.default_suites.v1.banking.task_suite import TOOLS`) as the
first AgentDojo import in a process triggers a circular-import error inside
`agentdojo`'s own `default_suites` package init order. Use the public
`agentdojo.task_suite.load_suites.get_suite("v1.2.2", "banking")` entrypoint
instead — it does not hit this path. The contract test's Banking-suite
assertions use this entrypoint; keep doing so in adapter code too.

## Next steps

See [`docs/integrations/agentdojo-progress.md`](./agentdojo-progress.md) for
what's built (Steps 1–6) in full detail. Remaining, per the low-level
design's "Recommended implementation order":

7. Privileged-tool wrapper — all-evidence `check_privilege()` gate for
   `send_money` and the other four privileged actions.
8. Docker-backed integration tests for the full write -> gate path.
9. Custom benchmark runner + JSON result collector.
10. Manual validation: one benign task, one injection task.
11. Full pinned Banking benchmark run + published methodology/results.
