# Traction Roadmap — 2-3 Week Sprint

**Goal:** get an independently-citable proof point and real distribution for what already exists (E1–E4 engine, E7 REST API/SDK) — not new engine capabilities. This is deliberately narrow. If it's not proof or distribution, it's out of scope for this sprint.

**Team shape assumed:** 3-5 developers, AI-assisted ("vibe coding") development. Every ticket below has a machine-checkable definition of done — a benchmark number, a published package, a live URL — not "make it good." Vibe-coded work is fast and reliable on narrowly-specified, testable tickets; it drifts on open-ended ones. Where a ticket would otherwise be open-ended, it's preceded by a same-day spec step.

**Explicitly out of scope for this sprint** (revisit after, don't pull forward pre-emptively):
- E5 (injection classifier) — already attempted and closed this cycle ([PR #11](https://github.com/Metaworkers-ai/governedmemory/pull/11)), don't re-open without a new reason to believe the outcome changes
- E6 (provenance graph / cascade purge)
- A hosted/managed SaaS offering
- More than one new benchmark integration in this sprint

---

## Workstream A — Benchmark validation (1-2 devs)

**Why this one, and why AgentDojo specifically:** [AgentDojo](https://github.com/ethz-spylab/agentdojo) (ETH Zurich, NeurIPS 2024) is a dynamic benchmark that measures both attack success rate *and* task utility for tool-calling agents under prompt injection, across four domains — including **Banking**, where the attack is literally "an injected instruction triggers an unauthorized transaction." That's the same threat model as [the flagship use case](use-cases/01-privileged-action-fraud-prevention.md) already documented, so results here reinforce a story that's already being told, rather than starting a new one. Results are also listed at [agentdojo.spylab.ai/results](https://agentdojo.spylab.ai/results/) and the [Invariant Labs benchmark registry](https://explorer.invariantlabs.ai/benchmarks/) — independently checkable, not self-reported.

Two other real benchmarks exist and are worth knowing about, but are explicitly **not** this sprint's target — pick one number to defend well rather than three partial ones:
- [InjecAgent](https://github.com/uiuc-kang-lab/InjecAgent) (ACL 2024) — broader indirect-injection coverage, no utility metric
- [Benchmarking Poisoning Attacks against RAG](https://arxiv.org/abs/2505.18543) (2025, successor to PoisonedRAG) — closer to pure retrieval poisoning, no live agent-action angle

### Tickets

1. **Spec (day 1, 0.5 day):** Read AgentDojo's defense interface (`agentdojo/defenses.py` region — confirm exact API by reading source, not docs, since public docs were thin as of this writing) and the Banking task suite. Write a one-page spec: what a "Governed Memory defense" plugin does — likely: every tool output gets written to `MemoryStore` with `source_type` reflecting its actual origin (tool output vs. injected content can't be distinguished at ingest, that's the point), and the Banking domain's money-moving tools (`send_money`/similar) get gated through `check_privilege()` before execution. **Definition of done:** spec doc reviewed, ambiguities resolved before any code is written.
2. **Adapter (days 2-4):** Implement the defense per spec, wired against the existing `MemoryStore`/`check_privilege()` API (no changes to `core/` — this is an integration, not an engine change). **Definition of done:** `agentdojo` CLI runs end-to-end with the defense flag against at least one model, produces a result file.
3. **Benchmark sweep (days 6-8):** Run AgentDojo's standard Banking (and optionally Slack/Workspace) suites with and without the defense, across 2-3 models. Capture attack success rate and utility for each. **Definition of done:** a results table with numbers, not vibes — e.g. "attack success rate X% → Y%, utility retained Z%."
4. **Publish (days 8-10):** Write up the methodology + results as a short doc/blog post (reuse the flagship use-case doc's narrative). Investigate submitting to the Invariant Labs registry / AgentDojo's own results page — the submission process needs to be confirmed by actually looking, don't assume. **Definition of done:** results are live somewhere a third party (investor, prospect) can find without asking you for a screenshot.

---

## Workstream B — LangChain integration (1 dev)

**Why:** LangChain's current integration model (confirmed against their docs) is a standalone PyPI package (`langchain-{name}`) implementing their `BaseRetriever` interface, published independently of their monorepo — not a PR that needs their team's review cycle. Since [E7](../README.md#rest-api-e7--self-hosted) already shipped a REST API and a `metaworkers` Python SDK, this is a thin adapter over existing code, not new engineering. LangChain's developer audience is large and its integrations directory is a real discovery channel.

### Tickets

1. **Scaffold (day 1):** `pip install langchain-cli`, generate a partner-package skeleton per [LangChain's template](https://python.langchain.com/docs/contributing/how_to/integrations/from_template/). Confirm `langchain-metaworkers` is unclaimed on PyPI before committing to the name. **Definition of done:** skeleton package imports cleanly.
2. **Implement (days 2-4):** A `BaseRetriever` subclass wrapping `metaworkers.GovernedMemory.retrieve()` — `purpose`/`agent_id`/`session_id` as constructor or call-time args, taint/policy filtering happens for free since it's the same `retrieve()` call the SDK already makes. Add the LangChain-standard integration test suite (they provide a base test class for retrievers). **Definition of done:** LangChain's own standard retriever tests pass against a local Governed Memory instance.
3. **Docs + publish (days 6-8):** Write the integration doc page using LangChain's doc-generation CLI, publish `langchain-metaworkers` to PyPI, submit the docs PR to LangChain's integrations directory per their contribution process. Add a short "Use with LangChain" section to the main README. **Definition of done:** `pip install langchain-metaworkers` works from a clean environment; docs PR is opened against `langchain-ai/langchain` (merge timing is out of your control — opening it is the deliverable).
4. **LangSmith public eval + case-study pitch (days 8-10):** LangSmith is not a benchmark — it's not a public leaderboard, and a shared eval is self-reported the same as any vendor claim (unlike Workstream A's AgentDojo number, which sits on a third-party registry). Its value here is reach, not proof: LangSmith's actual customer base (Klarna, C.H. Robinson, Dun & Bradstreet, Vizient are named case studies) is a far larger and more commercially relevant audience than the academic security-benchmark crowd. Using the now-published `langchain-metaworkers` retriever, build a small LangSmith dataset/experiment reproducing the flagship phishing-email-to-refund scenario, pytest-integrated (LangSmith supports failing a PR when an eval score drops), and share it publicly via `share_dataset`. Then pitch the retriever package + eval to [LangChain's case-studies team](https://www.langchain.com/case-studies) for a blog feature. **Definition of done:** a public, shareable LangSmith eval link exists; the case-study pitch has been sent (a placement isn't guaranteed or required for this ticket to be done — sending it is).

**Not this sprint, flagged for the week-3 buffer:** contributing a prompt-injection-resistance evaluator to [`openevals`](https://github.com/langchain-ai/openevals), LangChain's own open-source evaluator library — at ~1.1k GitHub stars it's more visible than either AgentDojo or ASB, but it's a distinct piece of work (a reusable evaluator, not a retriever adapter) and shouldn't be pulled into week 1-2 alongside everything else above.

---

## Workstream C — Frictionless proof + GTM assets (1 dev)

**Why:** the fastest way to lose a prospect or investor's attention is making them run Docker locally before they see the value. This workstream removes that friction and produces the assets that actually get shared (a deck slide, a GIF, a one-pager) rather than a link to a repo they won't clone.

### Tickets

1. **One-click demo (days 1-3):** A Render/Railway "Deploy" button or a `.devcontainer/devcontainer.json` for GitHub Codespaces — either gets someone from "click" to the seeded Streamlit demo with zero local setup. Pick whichever is less work given current `deploy/docker-compose.yml`; don't build both. **Definition of done:** a stranger with no local setup can click a link and be looking at the Policy tab within 2 minutes.
2. **Demo capture (days 3-4):** A short (30-60s) screen-recorded GIF/video of the exact flagship scenario — the phishing email, the denied refund, the audit log entry — embedded at the top of the main README, right under the existing "New here?" pointer. **Definition of done:** GIF is in the repo and renders in the GitHub README preview.
3. **One-pager (days 6-8):** A single page (reuse the flagship use-case doc's narrative + Workstream A's benchmark number once available) formatted for a pitch deck appendix or a cold email attachment. **Definition of done:** exists as a standalone doc or exportable slide, not buried in README prose.
4. **Cheap discovery (days 8-10):** GitHub topic tags (`prompt-injection`, `llm-security`, `rag-security`, `ai-agents`), a PR to 1-2 relevant "awesome-llm-security"/"awesome-ai-agents" lists. **Definition of done:** tags are set, PRs are opened (again, merge timing isn't the deliverable — opening them is).

---

## Suggested week-by-week

| | Workstream A (benchmark) | Workstream B (LangChain) | Workstream C (GTM assets) |
|---|---|---|---|
| **Week 1** | Spec + adapter build | Scaffold + implement | One-click demo + GIF |
| **Week 2** | Run sweep + publish results | Publish package + submit docs PR + LangSmith eval + case-study pitch | One-pager + discovery |
| **Week 3 (buffer, optional)** | Only if capacity: a second benchmark data point (InjecAgent) — pick at most one | Only if capacity: an `openevals` contribution, or a second framework adapter (e.g. LlamaIndex) — pick at most one | Design-partner outreach using what's now live |

Week 3 is a checkpoint, not a pre-committed backlog — decide what's worth pulling forward based on what actually landed in weeks 1-2, rather than locking it in now.

## What "done" looks like for the funding narrative

By the end of week 2, you should be able to say, with a link for each claim:
- "Independently benchmarked on [AgentDojo](https://agentdojo.spylab.ai/results/) (NeurIPS 2024): attack success rate cut from X% to Y%, Z% task utility retained" — a number, not an adjective
- "`pip install langchain-metaworkers` — one of N LangChain retriever integrations, live in their directory"
- "Here's a public LangSmith eval showing it block the same attack" — a link a LangChain-ecosystem buyer can run themselves, plus a pitch in front of their case-studies team
- "Try it yourself in under 2 minutes, no setup" — a link, not an invitation to clone a repo
