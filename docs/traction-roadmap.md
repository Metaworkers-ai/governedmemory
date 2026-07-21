# Traction Roadmap

**Revision note:** this roadmap was first written on 2026-07-10, before most of what it called "future work" actually shipped. This revision (2026-07-21) reflects what's real now — PRs merged since, the current public site, and one large PR still in review — rather than re-planning from a stale snapshot. Keep revising this doc in place as things ship; don't let it drift again.

**Goal (unchanged):** get independently-citable proof points and real distribution for what already exists — not new engine capability. If it's not proof or distribution, it's out of scope.

**Team shape assumed:** 3-5 developers, AI-assisted ("vibe coding") development. Every ticket has a machine-checkable definition of done — a benchmark number, a merged PR, a live URL — not "make it good."

---

## Shipped since the first draft — don't re-plan this

A lot of what this doc originally scoped as 2-3 weeks of work is now done, via PRs merged directly or the "increase_traction" push:

| Done | PR(s) | Note |
|---|---|---|
| REST API + Python SDK (E7) | [#12](https://github.com/Metaworkers-ai/governedmemory/pull/12), [#13](https://github.com/Metaworkers-ai/governedmemory/pull/13) | `pip install metaworkers` |
| Detection (E5) + Audit Graph (E6) | [#18](https://github.com/Metaworkers-ai/governedmemory/pull/18) | Trained injection classifier w/ tracked precision/recall; provenance lineage, cascade purge, formal hash-chain verifier |
| Next.js web console, containerized into the self-host stack | [#16](https://github.com/Metaworkers-ai/governedmemory/pull/16), [#17](https://github.com/Metaworkers-ai/governedmemory/pull/17) | Replaces the old Streamlit demo |
| One-command Quickstart, Docker-only, cross-platform | [#21](https://github.com/Metaworkers-ai/governedmemory/pull/21), [#25](https://github.com/Metaworkers-ai/governedmemory/pull/25) | `./scripts/quickstart.sh` — no Python/conda needed |
| Live hosted demo + redesigned landing page | [#20](https://github.com/Metaworkers-ai/governedmemory/pull/20) | demo.metaworkers.ai, "live inspection demo + motion" |
| MIT relicense (was Apache 2.0) | [#19](https://github.com/Metaworkers-ai/governedmemory/pull/19) | Removes a real adoption blocker for companies that avoid Apache 2.0's patent clause |
| Discord community | [#24](https://github.com/Metaworkers-ai/governedmemory/pull/24) | Linked from README; **not yet linked from metaworkers.ai** (see gap list below) |
| 4 industry-vertical use-case docs (insurance, financial services, recruiting, legal) | [#22](https://github.com/Metaworkers-ai/governedmemory/pull/22) | Each grounded in a real, sourced incident or case, not a hypothetical |
| SDK correctness fixes + expanded test coverage (auth, embeddings, API routes) | [#22](https://github.com/Metaworkers-ai/governedmemory/pull/22) | Closed gaps the SDK's own docstrings had flagged as unimplemented |
| Security & data-handling overview for enterprise reviewers | [#27](https://github.com/Metaworkers-ai/governedmemory/pull/27) | `docs/security-overview.md`, linked from a new README `## Security` section |
| GitHub topic tags | — | Already set: `agent-memory`, `agentic-ai`, `ai-governance`, `llm-security`, `memory-poisoning`, `prompt-injection`, `rag-security`, `mcp`, `model-context-protocol`, etc. — the old "cheap discovery" ticket is done |

**In review, not yet merged — the single highest-leverage thing to act on right now:**

[**PR #29 — Mem0 adapter**](https://github.com/Metaworkers-ai/governedmemory/pull/29): a governance layer that bolts onto an *existing* Mem0 OSS deployment without replacing it as the memory store — Mem0 stays the system of record for storage/embeddings/retrieval, Governed Memory adds trust evaluation, policy enforcement, provenance, audit, and quarantine on top. ~4,700 lines, 310 tests claimed passing (contract tests, concurrency/idempotency tests, Docker-backed adapter tests), full docs (`docs/integrations/mem0.md`), and packaged as an **optional extra of the existing `metaworkers` SDK** (`pip install metaworkers[mem0]`) — not a new package to register or a new PyPI name to defend.

This changes the earlier plan more than anything else in this list: the original Workstream B was "build a LangChain retriever from scratch." A comparable ecosystem integration — arguably a *better first one*, since Mem0 is a memory framework specifically, so "add governance to the memory system you already run" is a tighter pitch than "another LangChain retriever" — is sitting 90% done waiting on review.

---

## What's still genuinely open

Checked the live site myself (metaworkers.ai) rather than assume. It has a hero section, product explainer, a financial-services scenario, a live demo link, and links to GitHub/the product site/use cases/contact — but confirmed **missing**: any benchmark or performance data, any traction metrics (stars, installs, users), a Discord link, and a specific (named or verifiably anonymized) customer case study — it currently has a generic/hypothetical scenario, not a real one. The README also still has no demo GIF/screenshot.

So the actual gaps, unchanged in kind from the first draft, are narrower in scope than originally planned:

1. **An independently-verifiable security benchmark result.** Nothing has shipped here. Still the top gap.
2. **Getting PR #29 merged, published, and announced.** Not a "build" task anymore — a review, ship, and distribute task.
3. **Turning what's now live into visible proof on the actual public site and README** — the specific, now-confirmed-missing pieces (Discord link, benchmark section, traction-metrics strip, real case study, README demo GIF) rather than "build a frictionless demo," which is done.

**Explicitly out of scope for this pass** (unchanged reasoning, still applies):
- More new engine capability (E8+)
- A hosted/managed SaaS offering
- More than one new benchmark integration
- Building a LangChain retriever from scratch *before* Mem0 ships — don't duplicate an ecosystem-integration effort that's already 90% done elsewhere; revisit LangChain only if there's a specific signal (a prospect asking for it) once Mem0 is live

---

## Workstream A — Benchmark validation (1-2 devs)

Unchanged from the first draft — this is the one place nothing has moved.

**Why AgentDojo:** [AgentDojo](https://github.com/ethz-spylab/agentdojo) (ETH Zurich, NeurIPS 2024, 669 stars, actively maintained through late 2025) measures both attack success rate *and* task utility for tool-calling agents under prompt injection, across four domains including **Banking** — an injected instruction triggering an unauthorized transaction, the same threat model as [the flagship use case](use-cases/01-privileged-action-fraud-prevention.md). Results sit on a public registry ([results page](https://agentdojo.spylab.ai/results/), [Invariant Labs registry](https://explorer.invariantlabs.ai/benchmarks/)) — independently checkable, not self-reported.

Real alternatives exist and are worth knowing about but are explicitly not this pass's target (pick one number to defend well, not three partial ones): [ASB — Agent Security Bench](https://github.com/agiresearch/ASB) (ICLR 2025, explicit "Memory Poisoning Attack" category — the closest name-match to this product, but only 271 stars and no public leaderboard) and [InjecAgent](https://github.com/uiuc-kang-lab/InjecAgent) (ACL 2024, broader coverage, no utility metric).

### Tickets
1. **Spec (day 1, 0.5 day):** Read AgentDojo's defense interface directly from source (public docs were thin) and the Banking task suite. Write a one-page spec for what a "Governed Memory defense" plugin does. **Definition of done:** spec reviewed before any code.
2. **Adapter (days 2-4):** Implement per spec against the existing `MemoryStore`/`check_privilege()` API — this is an integration, not a `core/` change. **Definition of done:** `agentdojo` CLI runs end-to-end with the defense flag against at least one model.
3. **Benchmark sweep (days 5-7):** Run the Banking suite (and optionally Slack/Workspace) with and without the defense, across 2-3 models. **Definition of done:** a results table — attack success rate X% → Y%, utility retained Z%.
4. **Publish (days 7-9):** Write up methodology + results, reusing the flagship use-case doc's narrative. Confirm the actual submission process for the Invariant Labs registry / AgentDojo's results page by looking, not assuming. **Definition of done:** results are live somewhere a third party can find without asking for a screenshot.

---

## Workstream B — Ship Mem0, then decide on what's next

Re-scoped entirely from "build a LangChain retriever" to "land the ecosystem integration that's already built, then extend it."

### Tickets
1. **Review + merge PR #29 (days 1-2):** The PR claims full test coverage and extensive manual verification — a focused review pass (architecture fit, whether the claimed 310 tests actually run clean, whether the concurrency/idempotency claims hold up) converts ~4,700 lines of already-built work into something shippable. This is the single highest-leverage action available right now — higher than anything net-new in this doc.
2. **Publish + announce (days 2-4):** No new PyPI package needed — it's `pip install metaworkers[mem0]`, an extra on the existing SDK. Cut a release, write a short announcement (README, Discord, a post), and post it where Mem0's own community would see it (their Discord/GitHub — same distribution logic the original plan applied to LangChain's directory, aimed at Mem0's instead). **Definition of done:** `pip install metaworkers[mem0]` works from a clean environment against a released version; announcement is posted.
3. **Public eval on the live integration (days 4-6):** Reproduce the flagship phishing-email-to-refund scenario running through the Mem0 adapter and publish it as a public, shareable eval (LangSmith-style if there's a natural hook, otherwise a simple reproducible script + results doc — don't force a LangSmith dependency that doesn't fit the Mem0 path). **Definition of done:** a link a prospect can open and see the attack get blocked, using the real shipped adapter, not a hypothetical.
4. **LangChain retriever — explicit backlog, not this pass:** Only revisit if a specific prospect asks for it. Building it now, before Mem0's even merged, would be duplicating unproven "ecosystem integration" effort rather than following up on integration #1 with evidence from real usage.

---

## Workstream C — Close the specific gaps on the live site (1 dev)

Re-scoped from "build a frictionless demo" (done — live hosted demo + one-command local install both exist) to the concrete, confirmed-missing pieces.

### Tickets
1. **Add the Discord link to metaworkers.ai (day 1):** Confirmed missing on the live site despite existing in the README since PR #24. Quick site fix, no excuse for this gap to persist.
2. **Add a benchmarks/results section to the site (days 1-3, blocked on Workstream A output):** The site currently has zero performance data. Wire it to Workstream A's number as soon as it exists rather than waiting for a separate later pass.
3. **Add a traction-metrics strip (days 3-4):** GitHub stars, PyPI/SDK installs, "Mem0 adapter live" — placeholder structure now, filled in as real numbers exist. Confirmed absent from the current site.
4. **Replace the generic financial-services scenario with a real one, or clearly label it as illustrative (days 4-6):** The site's only use-case content right now is a hypothetical. Either land a real design partner/pilot to reference (an outreach task, not a dev one — flag to whoever owns customer conversations) or make the existing scenario's illustrative nature explicit rather than implying it's a customer story.
5. **Add a demo GIF to the README (days 1-2, parallelizable with the above):** Confirmed still missing — the hosted demo covers the website, but the GitHub README is a separate, high-traffic surface with nothing visual on it. 30-60s capture of the flagship scenario (write the phishing email → watch it get tainted → denied refund → audit log entry), embedded under the existing "New here?" pointer.

---

## Suggested week-by-week

| | Workstream A (benchmark) | Workstream B (Mem0) | Workstream C (site gaps) |
|---|---|---|---|
| **Week 1** | Spec + adapter build | Review/merge PR #29 + publish/announce | Discord link + README GIF (both quick, do first) |
| **Week 2** | Run sweep + publish results | Public eval on the live Mem0 integration | Benchmarks section (once A lands) + traction-metrics strip |
| **Buffer / ongoing** | Second benchmark data point (ASB) only if capacity | LangChain retriever, only if a prospect asks | Real case study — outreach-dependent, may run longer than the dev-scoped items |

---

## What "done" looks like

By the end of this pass, you should be able to say, each with a link:
- "Independently benchmarked on [AgentDojo](https://agentdojo.spylab.ai/results/) (NeurIPS 2024): attack success rate cut from X% to Y%, Z% task utility retained" — a number, not an adjective
- "`pip install metaworkers[mem0]` — governance on top of the Mem0 deployment you already run" — a shipped integration, not a proposal
- "Here's a public eval showing it block the same attack, running through Mem0" — a link, not a claim
- "Try the live demo, no install" (already true — demo.metaworkers.ai) plus "here's the benchmark number and traction stats on the same page" (not yet true — closes with Workstream C)
