# Governance Gap Closure — Engineering Spec

**Source:** gap analysis against ["Governed Shared Memory for Multi-Agent LLM Systems"](https://arxiv.org/html/2606.24535v1), which formalizes fleet-memory systems as a five-tuple **F = (A, M, G, P, T)** — agents, memory substrate, governance layer, provenance, temporal ordering — and validates a reference implementation against four named failure modes: unauthorized leakage, stale propagation, contradiction persistence, provenance collapse.

**Where we already hold up:** provenance graph + cascade purge (E6) covers their derivation-chain metadata; our hash-chained audit log is strictly stronger than what they describe (they claim reconstructability, not tamper-evidence); tenant isolation (E1) is enforced on every `MemoryStore` method via `_require_tenant()`, which is the exact class of bug they had to patch mid-study (see Workstream B).

**Three real gaps, in priority order:**

| # | Gap | Failure mode it closes | Size |
|---|---|---|---|
| A | No contradiction detection — only exact-string dedup | Contradiction Persistence | Small, ~1 week |
| B | No agent/fleet-scoped memory visibility — `agent_id` is descriptive only | Unauthorized Leakage (in their multi-agent sense) | Large, ~2-3 weeks |
| C | No reproducible, quantified governance benchmark | (credibility/validation, not a named failure mode) | Small-medium, ~1 week, parallelizable with A |

Do **A** first — it's self-contained and extends an existing module without touching the schema or any API surface. Do **C** in parallel — it doesn't depend on A or B for its first three experiments. Do **B** last and separately — it's a schema change touching every read path, and the paper's own postmortem is a direct warning about how easy this is to get half-right.

---

## Workstream A — Contradiction Detection (extends E2 / Write Governor)

### Current state

[`core/write_governor/dedup.py`](../core/write_governor/dedup.py) does normalized-string equality only (`normalize()` + exact match) — its own docstring already flags this as incomplete: *"semantic dedup would need an embedding-similarity pass, a reasonable future enhancement."* Two records that say opposite things about the same fact (`"account status: active"` vs. `"account status: closed for cust-4471"`) currently coexist forever with no signal that either is stale or in conflict — neither dedup (text differs) nor `Temporal.superseded_by` (nothing sets it) catches this.

### Scope decision (resolve in the spec step, don't guess mid-implementation)

The paper's approach — RDF triple extraction + structural compatibility checking — is a real NLP problem, not a rule extension. For a v1 that's actually buildable in a week, **do not** attempt automatic true/false resolution. Instead: **detect and flag candidate contradictions for review, async, without blocking the write** — mirrors the paper's own architecture choice (their contradiction detector is also async/post-commit, separate from the synchronous dedup gate). Resolution (which record wins) stays a human or policy decision, not something the detector decides unilaterally.

### Design

1. **New module** `core/write_governor/contradiction.py`, same shape as `dedup.py` — pure logic, no SQL (store.py owns queries, matching the existing separation of concerns).
2. **Candidate selection**: after embedding is computed (this runs *after* dedup's pre-embedding stage, since it needs the vector), search existing non-superseded records for the same `tenant_id` + `customer_id` in a similarity band — high topical overlap but *not* near-identical text (e.g. cosine similarity between 0.80 and 0.97; below 0.80 is "different topic," above 0.97 is dedup's job). Tune the band empirically against the seeded demo data rather than guessing exact numbers.
3. **Contradiction cue heuristic**: within that similarity band, apply a small rule-based polarity check — negation cues (`"not"`, `"no longer"`, `"cancelled"`, `"revoked"`) and paired antonym terms (`active`/`inactive`, `approved`/`denied`, `true`/`false`) — same style as `injection_scanner.py`'s pattern-based scoring, not a trained classifier. This is intentionally a heuristic stopgap (consistent with how E2's injection scanner started, later got an optional trained classifier in E5) — don't over-invest in NLP sophistication for v1.
4. **What happens on a flagged pair**: do **not** block or auto-supersede. Emit a new `AuditOp.CONTRADICTION_FLAGGED` event referencing both memory IDs, and expose a new read method `MemoryStore.list_conflicts(tenant_id, customer_id=None) -> list[dict]` returning flagged pairs. This is additive — no existing behavior changes for callers who don't use it.
5. **REST + SDK surface**: `GET /v1/memory/conflicts?customer_id=` (mirrors the existing `/v1/memories` list-route pattern) and a corresponding `list_conflicts()` method on the `metaworkers` client — same shape as the recently-added `list_customers()`/`list_memories()`.

### Tickets

1. **Spec (0.5 day):** Confirm the similarity-band thresholds and cue-word list against 5-10 real examples from the seeded demo data (`scripts/seed_demo.py`). Write down the exact band and cue list before coding — this is the "resolve ambiguity before writing code" step the existing traction-roadmap.md uses for every open-ended ticket. **DoD:** short spec note (PR description is fine) listing the band, the cue list, and 3 worked examples (2 real contradictions, 1 deliberate near-miss that should *not* flag).
2. **Implement `contradiction.py` (2 days):** Pure function(s) taking existing candidate rows + new content, returning flagged pairs + reason strings. Unit tests co-located at `tests/unit/test_contradiction.py`, following `test_dedup.py`'s structure. **DoD:** unit tests green, no DB/embedding dependency in this module's own tests (mock the embedding vector).
3. **Wire into the write path + audit + `list_conflicts()` (2 days):** Call the new module from `MemoryStore.write()` after embedding, add `AuditOp.CONTRADICTION_FLAGGED`, implement `list_conflicts()`. Integration test in `tests/integration/test_memory_store.py` (new `TestContradictionDetection` class) against real Postgres+pgvector. **DoD:** integration tests green; a deliberately-contradictory write pair produces exactly one flagged-pair record and one audit event; an unrelated write produces neither.
4. **REST + SDK (1 day):** `GET /v1/memory/conflicts`, `metaworkers.list_conflicts()`. Follow the existing pattern in `api/main.py` / `sdk/python/metaworkers/client.py` for the list-route additions from the last SDK round. **DoD:** route covered by `tests/integration/test_api.py`, SDK method covered by `tests/unit/test_sdk_client.py` (mocked transport).
5. **Docs (0.5 day):** Update `docs/use-cases/06-memory-deduplication-hygiene.md` — it currently oversells dedup as covering "stale fact" resolution; correct it and cross-link to the new conflict-flagging behavior. **DoD:** doc accurately distinguishes "duplicate" (auto-superseded) from "contradiction" (flagged, human-resolved).

---

## Workstream B — Agent/Fleet-Scoped Memory Visibility (new engine slice, E8)

### Current state

Confirmed by direct inspection — zero hits for `scope`, `fleet`, or any trust-ladder concept anywhere in `core/`. Every read method scopes by `tenant_id` only:

```
core/memory_store/store.py:355   def get(self, memory_id: str, tenant_id: str) -> MemoryRecord | None:
core/memory_store/store.py:393   def vector_search(self, query: str, tenant_id: str, k: int = 10) -> list[MemoryRecord]:
core/memory_store/store.py:420   def lexical_search(self, query: str, tenant_id: str, k: int = 10) -> list[MemoryRecord]:
core/memory_store/store.py:444   def retrieve(self, query: str, tenant_id: str, ...)
```

`agent_id` is captured on every `MemoryRecord` (via `Provenance`/write metadata) but never used as an access-control input anywhere. Today, every agent inside one tenant can read every other agent's memory — there is no "this agent's private working memory" vs. "shared across a team of agents" vs. "tenant-wide" distinction. This is the repo's closest analog to the paper's core five-tuple dimension (their "A"), and it's the one dimension not yet governed at all.

### Explicit warning from their own postmortem

Their disclosed production bug: *"Sub-tenant scope enforcement was bimodal: tenant-level enforced everywhere, but fleet/agent scope not enforced on direct GET-by-id"* — i.e., they got it right on the main retrieval path and missed it on the by-ID lookup path, and it shipped that way until the study caught it. **This is the single most important testing requirement for this workstream**: any new scope check must be enforced identically across `get()`, `retrieve()`, `vector_search()`, and `lexical_search()` — not just the retrieval path most people think to test first.

### Scope decision (resolve in the spec step)

The paper's model is a 3-tier hierarchy (`agent ⊑ fleet ⊑ tenant`) with a 4-level trust ladder for cross-fleet operations. That's more than this repo needs for a first cut. Recommended v1 scope, to validate before coding:

- **Two tiers, not three**: `agent`-private and `tenant`-shared (the existing default — fully backward compatible, nothing breaks for current callers). Skip the middle "team/fleet" tier for v1; add it later only if a real customer need shows up. This cuts schema and query complexity roughly in half versus the paper's model while still closing the actual gap (an agent's private scratch memory staying private).
- **No trust ladder for v1** — a requesting agent either owns an `agent`-scoped record or doesn't; there's no graduated cross-agent read/write permission level. `PrivilegeRules`/purpose-binding already exist for action-level gating; don't duplicate that machinery here.

Flag this as an open decision for the spec ticket below rather than committing to it blind — confirm against whatever the first real multi-agent design partner actually needs.

### Design

1. **Schema**: add `visibility: str` (`"agent"` | `"tenant"`, default `"tenant"`) to `MemoryRecord`/`WriteRequest` (`core/models/memory_record.py`). Default preserves all existing behavior — this is additive, not breaking. Migration: new nullable-with-default column, same pattern as prior schema additions (check `core/memory_store/store.py`'s migration handling for the established pattern).
2. **Write path**: `WriteRequest.visibility` defaults to `"tenant"`. `agent`-scoped writes store the writing `agent_id` as the owner.
3. **Read paths — all four, uniformly**: every method takes an explicit `requesting_agent_id: str | None`. Filter logic: `visibility == "tenant" OR (visibility == "agent" AND owner_agent_id == requesting_agent_id)`. If `requesting_agent_id` is omitted, default to tenant-only visibility (fail closed — an omitted agent identity should never accidentally grant access to agent-private records, it should just exclude them).
4. **This is the part their bug warns about**: write the test suite *before* or alongside each method, not after all four are done — a `TestAgentScopeIsolation` class in `tests/integration/test_memory_store.py` parametrized across all four read methods, so a gap in one path fails the same way a gap in any other would. This directly mirrors the [`TestTenantIsolation`](../tests/integration/test_memory_store.py) class structure already in the suite — same pattern, one dimension over.
5. **REST + SDK**: `requesting_agent_id` becomes a query/body param on `/v1/retrieve` and any by-ID GET route; `visibility` becomes a write-request field. Update `metaworkers` client signatures to match — this is the same kind of additive, backward-compatible parameter addition as `include_untrusted`/`purpose` were for E3/E4.

### Tickets

1. **Spec (1 day):** Confirm the two-tier-vs-three-tier decision above, confirm the fail-closed default behavior, and write the exact filter predicate for each of the four read methods as pseudocode before touching real code. **DoD:** spec reviewed, no ambiguity left for the four read-path implementations.
2. **Schema + migration (1 day):** Add `visibility` column + migration, update `MemoryRecord`/`WriteRequest` models. **DoD:** existing test suite still green with zero test changes required (proves backward compatibility) — new field only exercised by new tests.
3. **Write path (1 day):** `store.write()` accepts and persists `visibility`. Unit test for the default-omitted case explicitly. **DoD:** written record round-trips `visibility` correctly; omitting it produces `"tenant"` (unchanged behavior).
4. **Read paths, one PR per method or one combined PR with the parametrized cross-method test from step 5 below — do not skip the cross-method test in favor of testing only `retrieve()` (4-6 days across `get`/`vector_search`/`lexical_search`/`retrieve`):** implement the filter predicate in each. **DoD:** each method individually covered.
5. **Cross-method isolation test suite (2 days, can start alongside step 4):** `TestAgentScopeIsolation`, parametrized across all four methods — write an agent-private record as agent A, assert agent B gets nothing back from *every* method, assert agent A gets it back from every method, assert an omitted `requesting_agent_id` gets nothing from any method for agent-scoped records. **DoD:** this test suite is the actual proof the paper's bug class doesn't exist here — treat it as the workstream's real deliverable, not a formality.
6. **REST + SDK (2 days):** Wire `requesting_agent_id`/`visibility` through `api/main.py` and `sdk/python/metaworkers/client.py`. **DoD:** `tests/integration/test_api.py` and `tests/unit/test_sdk_client.py` cover the new params; SDK README usage example updated.
7. **Docs (1 day):** New or extended use-case doc — multi-agent platforms (a support tenant running a triage agent and a billing agent that shouldn't read each other's scratch reasoning) is the natural flagship scenario, same style as the existing `docs/use-cases/*.md`. **DoD:** doc follows the established structure (scenario → code walkthrough → try-it-in-demo → related use cases).

---

## Workstream C — Governance Benchmark Harness

### Why

The paper's strongest credibility move isn't the architecture, it's ArgusFleet — a small, purpose-built eval harness producing hard, rerunnable numbers (0/80 cross-fleet leaks, 90/90 contradiction detection, p50 291ms provenance-hop latency, JSONL traces + CSV summaries). We currently prove these properties one-off inside `pytest` but don't publish a standalone, rerunnable, quantified report — which is exactly the kind of artifact [traction-roadmap.md](traction-roadmap.md)'s Workstream A already identified as valuable for AgentDojo's attack-success-rate number. This is the same idea applied to our own governance properties instead of a third-party benchmark.

This does **not** block on Workstream B — three of four experiments below work against what's already shipped.

### Design

New `scripts/benchmark_governance.py`, run against a live instance (reuse `deploy/docker-compose.yml`), producing a JSONL trace file + a markdown/CSV summary table. Four experiments, matching the paper's structure:

1. **Leakage** — write N records across M tenants, attempt cross-tenant reads via all four read methods, assert 0 successes. (Extend with cross-agent leakage once Workstream B ships.)
2. **Provenance** — build N derivation chains of varying depth, verify `get_provenance()` reconstructs each completely, measure p50/p99 latency per hop.
3. **Injection defense** — write N untrusted/injected records, verify `check_privilege()` denies 100% of privileged actions against them, 0% false-positive rate against a control set of trusted records.
4. **Contradiction detection** (once Workstream A ships) — write deliberately contradictory pairs and unrelated pairs, measure detection rate and false-positive rate.

### Tickets

1. **Spec (0.5 day):** Confirm N/M sample sizes and pass/fail thresholds for each experiment (e.g. "leakage must be exactly 0/N, no tolerance"; injection defense might tolerate a documented false-positive rate rather than demanding 0%). **DoD:** thresholds written down before the harness is built, so the harness isn't tuned after the fact to whatever numbers it happens to produce.
2. **Harness (3 days):** Implement the four experiments against a running `docker compose` instance, using the REST API (not direct `MemoryStore` calls) so the numbers reflect what an external integrator actually gets. **DoD:** `python scripts/benchmark_governance.py --reset` produces a JSONL trace + summary table from a clean environment, reproducibly.
3. **Publish (1 day):** Results table into a short doc (`docs/benchmarks.md` or similar), linked from the main README alongside wherever the AgentDojo numbers land per traction-roadmap.md Workstream A. **DoD:** a third party can find both sets of numbers without asking for a screenshot — same bar traction-roadmap.md already set for the AgentDojo work.

---

## Sequencing summary

| Week | Workstream A (contradiction) | Workstream C (benchmark) | Workstream B (agent scoping) |
|---|---|---|---|
| 1 | Spec + implement + wire in | Spec + harness build | Spec (can start anytime, no dependency) |
| 2 | REST/SDK + docs | Publish | Schema + write path |
| 3 | — | Extend with contradiction experiment (after A ships) | Read paths + isolation test suite (the critical part) |
| 4 | — | — | REST/SDK + docs |

A and C can run fully in parallel on separate developers. B should not be rushed to fit this timeline — the isolation test suite (B.5) is the actual point of the workstream, and the paper's own postmortem is a direct demonstration of what happens when that gets shortcut.
