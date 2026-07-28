# GovernedMemory + AgentDojo (Banking suite)

Status: **Step 11 targeted validation passed; full sweep remains pending.**
Three live repetitions against `gpt-4o-2024-05-13` produced governed-benign
utility `1.0`, false-block rate `0.0`, governed-attacked ASR `0.0`, and
infrastructure-error rate `0.0`. The integration uses the Option B
`banking-v3-per-record-scored-outputs` mapping:
recent-transaction results arrive through a trusted bank channel but each
list item is written and injection-scored independently, preventing benign
records from diluting an injected record. `read_file` remains untrusted by
source. Historical smoke artifacts produced under earlier mapping versions
must not be used to validate v3. Current targeted artifacts are under
`results/option-b-v3-targeted-r3/`. This tracks
Workstream A (`docs/traction-roadmap.md`) Ticket 1/2. For the full
implementation history, design decisions, bug fixes, and test coverage,
see [`docs/integrations/agentdojo-progress.md`](./agentdojo-progress.md).
This page only covers the version pin and how to run the contract test
that validates it.

The default AgentDojo gate checks attacker-reachable tool outputs while
still persisting, scanning, and auditing the benchmark-authored initial
task. Use `--include-user-input-in-gate` in the Step 11 runner to reproduce
the older strict all-evidence comparison policy.

The AgentDojo validation and benchmark CLIs default to
`--detection-backend ensemble`. The heuristic backend alone does not detect
AgentDojo's indirect “important message” attack style.

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
