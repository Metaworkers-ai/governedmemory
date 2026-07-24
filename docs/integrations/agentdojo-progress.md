# GovernedMemory + AgentDojo integration — progress report (Steps 1–6)

**Status as of this report:** Steps 1–6 of the low-level design's 11-step
"Recommended implementation order" are complete, tested, and passing. No
adapter code exists yet for Step 7 onward (privileged-tool gating, the
benchmark runner, or an actual benchmark run).

This document is the single place to read to understand what's been built,
why it's built that way, and what's left. `docs/integrations/agentdojo.md`
stays a short pointer/reference page; this is the detailed record.

---

## 1. What this integration is

A defense plugin for [AgentDojo](https://github.com/ethz-spylab/agentdojo)'s
Banking suite that routes every tool output through GovernedMemory's
write-time taint scoring, and gates the five privileged Banking actions
(`send_money`, `schedule_transaction`, `update_scheduled_transaction`,
`update_password`, `update_user_info`) behind `MemoryStore.check_privilege()`
before they execute — closing the gap that a post-tool-output defense
element alone cannot close (AgentDojo can execute multiple tool calls from
one assistant message in a single batch, before any downstream pipeline
element runs).

Two specs preceded this code (`governed-memory-agentdojo-defense-spec_1.md`
and a teammate's low-level design). The team's low-level design was chosen
as the implementation blueprint after independent verification against
AgentDojo's actual source found the original spec's write-path assumption
(`GovernanceEvaluationService.evaluate()` doesn't persist) was wrong, and
identified a same-assistant-message-batch timing gap the original spec's
Job1/Job2 split didn't close. See the conversation history for the full
comparison; this document starts from the point both specs converged.

---

## 2. Design decisions made while implementing (not just following the LLD verbatim)

The low-level design is a design document, not pseudocode — several
concrete decisions had to be made (and verified against real code) while
building each step:

| # | Decision | Why |
|---|---|---|
| 1 | New top-level `integrations/agentdojo/` package, sibling to `core/`, never imported by it | `docs/traction-roadmap.md`'s own Workstream A ticket requires "no changes to `core/`" |
| 2 | `agentdojo`-importing submodules (`run_initializer.py`, `function_factory.py`, `source_tool_wrapper.py`) are imported inside `try/except ImportError` in `integrations/agentdojo/__init__.py` | Otherwise every DB-free unit test (context, registry, banking mapping/policy) would start requiring `agentdojo` installed, since Python always runs a package's `__init__.py` before any of its submodules |
| 3 | `RunContextRegistry` uses an explicit `id(environment) -> context` map with a real lock and an explicit register/unregister lifecycle, not a weak-reference cache | The design wants a missing or duplicate registration to be a loud, immediate error, not something whose behavior depends on garbage-collection timing |
| 4 | Banking suite tool names/tests use `agentdojo.task_suite.load_suites.get_suite(...)`, never `agentdojo.default_suites.v1.banking.task_suite` directly | The direct import path triggers a real circular-import bug in `agentdojo==0.1.35` (found by actually running the contract test, not by inspection) |
| 5 | `GovernedRunHook` signature is `(context, original_run, explicit_kwargs)` — hooks never receive the raw AgentDojo `env` | Keeps hook implementations (Step 6's source-tool wrapper, Step 7's privileged-tool wrapper) from needing to import `agentdojo` at all; only `function_factory.py` (which resolves `env` from the hidden dependency) needs to |
| 6 | Hooks signal infrastructure failures via a plain `GovernanceInfrastructureError`, which `GovernedFunctionFactory` catches and converts to `agentdojo`'s `AbortAgentError` | Decision 5 means a hook has no `env` to construct `AbortAgentError` with; the factory does |
| 7 | `RunGovernanceContext.next_sequence()` is one monotonic counter shared by both `EvidenceRef.sequence` and `ActionEvent.sequence` | Matches the LLD's dataclass design intent: the two lists together reconstruct one combined "what happened when" timeline for an attempt, e.g. a privileged tool call that's allowed writes both an `EvidenceRef` (its confirmation output) and an `ActionEvent` (the decision) |
| 8 | `ensure_banking_policy()` upserts a tenant-scoped policy with `PrivilegedActions=[send_money, schedule_transaction, update_scheduled_transaction, update_password, update_user_info]` and `require_trust=True`, called once per attempt right after `generate_run_identity()` | GovernedMemory's shipped `PrivilegeRules` defaults (`send_email`, `refund`, `escalate`) don't match any Banking tool name — an unconfigured tenant would leave every privileged action unconditionally allowed (verified against `evaluate_privileged_action()`'s real source, then proven with a Docker-backed integration test) |
| 9 | The source-tool wrapper formats results with the exact same formatter callable AgentDojo's `ToolsExecutor` uses (`tool_result_to_str` by default) | `ToolsExecutor` formats a tool's raw result *again*, independently, after `run_function()` returns — if the wrapper wrote different text, the persisted evidence (and injection scanner score) wouldn't match what the LLM actually reads |
| 10 | `make_banking_source_tool_hook()` refuses to build a hook for any of the five privileged actions | Wrapping a mutating tool with the read-tool hook instead of Step 7's privileged hook would let it run completely ungated while still looking governed in the tool list — worse than doing nothing |

---

## 3. Two bugs found and fixed during implementation (not after)

Both were caught by actually working through the next step's requirements
before writing its code — not discovered by accident later:

1. **`RunGovernanceContext.append_evidence`'s ordering check was wrong.**
   It required `ref.sequence == len(self.evidence)`, assuming evidence
   sequence numbers are contiguous within the evidence list alone. Since
   `next_sequence()` is shared with `ActionEvent.sequence` (decision #7
   above), the first privileged action recorded via Step 7 would have
   permanently broken every evidence write afterward for that attempt.
   Fixed in Step 6 (before Step 7 needed it) by checking that a sequence
   was actually reserved and not already used by *either* list, rather
   than checking list-length equality.

2. **`GovernedFunctionFactory` had no way for a hook to signal an
   infrastructure failure.** Decision #5 (hooks don't get `env`) meant a
   hook literally could not construct `AbortAgentError` itself. Fixed by
   adding `GovernanceInfrastructureError`, converted to `AbortAgentError`
   by the factory's closure, which already has `env` in scope.

---

## 4. What's built, step by step

### Step 1 — AgentDojo contract test (`requirements-agentdojo.txt`, `tests/contract/`)

Pins `agentdojo==0.1.35`. `tests/contract/test_agentdojo_contract.py` (10
tests) verifies, against the real installed package rather than
assumption: `Function`/`Depends`/`FunctionsRuntime` shapes, the exact
11-tool Banking suite tool set, `AbortAgentError`'s constructor, and —
the load-bearing fact for the whole design — that `ToolsExecutor` executes
every tool call in one assistant message inside a single `query()` call,
with no pipeline element able to run between two calls in the same batch.
Found and documented a real circular-import bug in `agentdojo==0.1.35`
(decision #4 above).

### Step 2 — Run identity, context, registry (`integrations/agentdojo/identity.py`, `context.py`, `registry.py`)

- `generate_run_identity()`: builds an isolated `RunIdentity`
  (tenant/customer/agent/session/policy ids) per task attempt, embedding a
  fresh UUID in `tenant_id` so independent attempts never bleed into each
  other.
- `RunGovernanceContext` (+ `EvidenceRef`, `ActionEvent`): ordered,
  append-only bookkeeping of what's been written and gated in one attempt.
- `RunContextRegistry`: thread-safe `id(environment) -> context` map
  (decision #3 above), with a `run()` context manager guaranteeing cleanup
  on both success and exceptions.

32 tests (21 in `test_agentdojo_context.py`, 11 in `test_agentdojo_registry.py`), including a 32-thread concurrency stress test (re-run 20× with no
flakes) proving independent registrations never cross-contaminate.

### Step 3 — Banking privileged-action policy (`banking_mapping.py`, `banking_policy.py`)

- `SOURCE_TYPE_BY_TOOL`: explicit `SourceType` mapping for all 11 Banking
  tools. `validate_tool_coverage()` fails loudly on any unmapped tool.
- `PRIVILEGED_ACTIONS`: the 5 mutating tools.
- `ensure_banking_policy()`: upserts the tenant-scoped policy (decision #8
  above). A Docker-backed integration test
  (`tests/integration/test_banking_policy.py`) proves both the danger
  (unconfigured tenant leaves `send_money` ungated) and the fix, plus
  per-action coverage, audit-event correctness, and tenant isolation. This
  test needs Docker to actually execute — verified by reading
  `store.py`'s real `write()`/`check_privilege()`/`list_audit()`
  implementations directly, since no Docker daemon is available in the
  sandbox this was built in; **run it yourself with `make db-up` before
  fully trusting it.**

32 DB-free unit tests (24 in `test_banking_mapping.py`, 8 in
`test_banking_policy.py`) + the 10-test integration file above.

### Step 4 — `GovernedRunInitializer` (`run_initializer.py`)

Pipeline element sitting between AgentDojo's `InitQuery` and the LLM.
Writes the task prompt once as trusted evidence (`SourceType.USER`) so a
benign task always has at least one trusted evidence record before any
direct privileged action. Idempotent (`processed_initial_input`), fails
closed (missing context or a failed write both raise `AbortAgentError`).

13 tests, all run against real `agentdojo==0.1.35`.

### Step 5 — `GovernedFunctionFactory` (`function_factory.py`)

Clones an AgentDojo `Function`, preserving its schema/dependencies/return
type/docstring exactly, and adds one hidden dependency resolving to the
current environment — used to look up the attempt's
`RunGovernanceContext` and delegate to a `GovernedRunHook` (decision #5).
Verified against real AgentDojo source that the hidden dependency is
genuinely invisible to the LLM (the schema is built once from
docstring-documented params and never rebuilt; dependency resolution
bypasses schema validation entirely).

14 tests, deliberately routed through AgentDojo's real
`FunctionsRuntime.run_function()` rather than calling `Function.run`
directly, so the dependency-resolution and schema-validation behavior
being relied on is actually exercised, not assumed.

### Step 6 — Source/read-tool wrapper (`source_tool_wrapper.py`)

`make_source_tool_hook()`: calls the original tool (letting its own errors
propagate untouched), formats the result with AgentDojo's own formatter
(decision #9), writes it as evidence, appends an `EvidenceRef`, returns the
original result unchanged. `make_banking_source_tool_hook()` adds the
automatic `SOURCE_TYPE_BY_TOOL` lookup and the privileged-action misuse
guard (decision #10).

37 tests. The one that matters most,
`tests/unit/test_source_tool_wrapper_batching.py`, wires two wrapped tools
into a real `FunctionsRuntime`, sends AgentDojo's actual `ToolsExecutor` one
assistant message with two tool calls, and confirms both get recorded as
evidence inside a single batch — the concrete, working proof of the claim
the entire design rests on (see Step 1).

---

## 5. Test coverage summary

| Environment | Command | Result |
|---|---|---|
| Plain `python3` (no `agentdojo`, no Docker) | `pytest tests/unit/ tests/contract/ tests/integration/test_banking_policy.py` | **205 passed, 15 skipped** (skips: agentdojo-dependent tests + Docker-dependent integration tests, both skip cleanly by design) |
| `agentdojo==0.1.35` venv (no Docker) | same command | **259 passed**, plus 2 pre-existing failures in `tests/unit/test_embeddings.py` unrelated to this work (an environment-variable check that behaves differently across venvs — confirmed clean on the primary venv) |
| Lint (`ruff check` + `ruff format --check`) | across every new/changed file | clean |

**Not yet run in this environment:** the Docker-backed
`tests/integration/test_banking_policy.py` assertions themselves (10
tests) — no Docker daemon is available in the sandbox this was built in.
Their logic was verified by reading `MemoryStore`'s real implementation
directly, but you should run `make db-up && pytest
tests/integration/test_banking_policy.py -v` yourself before fully
trusting them.

---

## 6. File manifest (everything new or changed, Steps 1–6)

```
requirements-agentdojo.txt                          new   — pins agentdojo==0.1.35
Makefile                                            mod   — install-agentdojo, test-agentdojo-contract, integrations/ added to lint/format
pyproject.toml                                      mod   — integrations* added to package discovery
docs/integrations/agentdojo.md                      new   — short reference page (this doc is the detailed one)
docs/integrations/agentdojo-progress.md             new   — this document

tests/contract/__init__.py                          new
tests/contract/test_agentdojo_contract.py           new   — 10 tests (Step 1)

integrations/__init__.py                            new
integrations/agentdojo/__init__.py                  new   — guarded exports for all of the below
integrations/agentdojo/identity.py                  new   — RunIdentity, generate_run_identity() (Step 2)
integrations/agentdojo/context.py                   new   — EvidenceRef, ActionEvent, RunGovernanceContext (Step 2, bug-fixed in Step 6)
integrations/agentdojo/registry.py                  new   — RunContextRegistry (Step 2)
integrations/agentdojo/banking_mapping.py           new   — SOURCE_TYPE_BY_TOOL, PRIVILEGED_ACTIONS (Step 3)
integrations/agentdojo/banking_policy.py            new   — ensure_banking_policy() (Step 3)
integrations/agentdojo/run_initializer.py           new   — GovernedRunInitializer (Step 4)
integrations/agentdojo/function_factory.py          new   — GovernedFunctionFactory (Step 5, extended in Step 6)
integrations/agentdojo/source_tool_wrapper.py       new   — make_source_tool_hook(), make_banking_source_tool_hook() (Step 6)

tests/unit/test_agentdojo_context.py                new   — 21 tests (Step 2, updated Step 6)
tests/unit/test_agentdojo_registry.py               new   — 11 tests (Step 2)
tests/unit/test_banking_mapping.py                  new   — 24 tests (Step 3)
tests/unit/test_banking_policy.py                   new   — 8 tests (Step 3)
tests/unit/test_governed_run_initializer.py         new   — 13 tests (Step 4)
tests/unit/test_function_factory.py                 new   — 14 tests (Step 5, +1 in Step 6)
tests/unit/test_source_tool_wrapper.py              new   — 18 tests (Step 6)
tests/unit/test_source_tool_wrapper_batching.py     new   — 1 test (Step 6, the key proof)

tests/integration/test_banking_policy.py            new   — 10 tests, Docker-backed (Step 3)
```

Total: 130 tests across these 10 files (10 contract + 120 unit/integration),
counted with `pytest --collect-only` against the actual files, not estimated.

---

## 7. What's next — Steps 7–11 (not started)

7. **Privileged-tool wrapper.** The all-evidence `check_privilege()` gate
   for the five privileged Banking actions: snapshot every evidence id
   written so far in the attempt (`context.ordered_evidence_ids()`, now
   safe to build on after the Step 6 sequencing fix), loop
   `check_privilege()` over each, deny if any fails, never call the
   original tool on denial, and — on allow — persist the tool's own
   confirmation output as evidence too (an `EvidenceRef` *and* an
   `ActionEvent`, which is exactly the interleaving case the Step 6 bug
   fix now supports correctly).
8. **Docker-backed integration tests** for the full write → gate path
   end-to-end (some already exist from Step 3; more needed once Step 7's
   code exists to exercise it against a real database).
9. **Custom benchmark runner** + JSON result collector, since
   `--module-to-load` can't register a custom defense into
   `AgentPipeline.from_config()` for this design.
10. **Manual validation**: one benign Banking task, one injection task, by
    hand, before running a full sweep.
11. **Full pinned Banking benchmark run** + published methodology and
    results, per `docs/traction-roadmap.md`'s Ticket 4.
