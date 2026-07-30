# GovernedMemory + AgentDojo (Banking suite)

Status: **The v4 file-policy change passed repeated targeted validation and
a complete Gemini 2.5 Flash Banking sweep.** Across the full 16-user-task,
9-injection-task matrix, GovernedMemory reduced targeted ASR from `0.4375`
to `0.0`, produced no benign policy denials, and had no infrastructure
errors. In matched native-defense runs, Repeat User Prompt reached `0.5208`
ASR and Spotlighting reached `0.4236`. These are one-repetition Banking
results, not an official AgentDojo leaderboard rank. The integration uses the Option B
`banking-v4-content-scored-files` mapping:
recent-transaction results arrive through a trusted bank channel but each
list item is written and injection-scored independently, preventing benign
records from diluting an injected record. Files delivered by AgentDojo's
virtual filesystem are also content-scored: clean files may support the
requested action, while scanner-flagged files become untrusted. Historical
artifacts under earlier mapping versions must not be used to validate v4.
This tracks
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

## Run with Gemini 2.5 Flash

The pinned `agentdojo==0.1.35` release predates the stable
`gemini-2.5-flash` model ID and routes its bundled Google models through
Vertex AI. The GovernedMemory benchmark runner provides a narrow compatibility
path for the stable model through Google AI Studio instead:

```bash
export GEMINI_API_KEY="your-google-ai-studio-key"

python scripts/run_agentdojo_benchmark.py \
  --model gemini-2.5-flash \
  --max-user-tasks 2 \
  --max-injection-tasks 1 \
  --out-dir results/smoke-gemini25-flash
```

If the machine resolves Google to IPv6 but has no working IPv6 route, set
`GEMINI_FORCE_IPV4=1`. This binds only the Gemini HTTP client to IPv4.

After the smoke run completes without infrastructure errors, run the full
three-repetition sweep:

```bash
python scripts/run_agentdojo_benchmark.py \
  --model gemini-2.5-flash \
  --repetitions 3 \
  --out-dir results/full-gemini25-flash-r3
```

The Banking suite and AgentDojo version remain pinned at `v1.2.2` and
`0.1.35`; only model client construction is overridden. Existing AgentDojo
model IDs retain their upstream provider routing. For attack generation,
the stable Gemini ID is assigned AgentDojo's existing Google-model family
label; API inference still uses `gemini-2.5-flash`.

Published repository artifacts:

- `results/full-gemini25-flash-r1/analysis-report.md`
- `results/full-gemini25-flash-r1/raw.jsonl`
- `results/gemini-native-defenses-r1/comparison-report.md`
- `results/gemini-native-defenses-r1/raw.jsonl`

AgentDojo's official results page explicitly describes itself as a results
catalog rather than a leaderboard. It also requires submissions to include
the implementation and benchmark results in a PR to the AgentDojo repository.
Do not describe this Banking-only result as an official Top-5 placement.

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
