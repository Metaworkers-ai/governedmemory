# GovernedMemory + AgentDojo (Banking suite)

Status: **Steps 1–10 of 11 complete.** Steps 1-9 tested and passing,
including confirmation on a real developer machine (Windows + Docker
Desktop) that all AgentDojo unit/contract tests and Step 3's Docker-backed
integration tests pass for real. Step 10 (manual validation) ships as a
tool (`scripts/validate_agentdojo_manual.py`) and checklist
(`docs/integrations/agentdojo-manual-validation.md`) — it needs a real LLM
API key to actually run, which hasn't happened yet. Step 11 (full
benchmark run) not started. The integration now uses the approved Option B
`banking-v2-content-scored-transactions` mapping: recent-transaction
results arrive through a trusted bank channel but remain subject to
injection scanning; `read_file` remains untrusted by source. This tracks
Workstream A (`docs/traction-roadmap.md`) Ticket 1/2. For the full
implementation history, design decisions, bug fixes, and test coverage,
see [`docs/integrations/agentdojo-progress.md`](./agentdojo-progress.md).
This page only covers the version pin and how to run the contract test
that validates it.

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
what's built (Steps 1–10) in full detail, including the section 5 decision
to content-score recent transactions while retaining fail-closed treatment
for file content. Remaining, per the low-level design's
"Recommended implementation order":

11. Full pinned Banking benchmark run + published methodology/results,
    after Step 10 has actually been run against a real model.
