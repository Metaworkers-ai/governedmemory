# Adoption Execution Plan

This plan turns GovernedMemory from a working core into something a new developer
can try, integrate, and share.

The four workstreams are deliberately ordered by leverage:

1. Quickstart — remove setup friction.
2. Mem0 adapter — meet developers inside an existing memory stack.
3. Hosted sandbox — let people experience governance without installing anything.
4. Distribution — make the first three discoverable and measurable.

## Current baseline

- The repository already has a Docker-based Quickstart for Postgres, the API, the
  web console, and seeded demo data.
- The core REST API and Python SDK are available for self-hosted use.
- A Mem0 adapter is not yet present.
- `adoption-dashboard/` is a hosting scaffold, not yet the governed-memory
  interactive sandbox.
- The README, project site, use-case documentation, SDK, and Discord community
  link provide the initial distribution surface.

## Definition of done

By the end of this effort, a stranger should be able to:

1. Clone the repository and reach a governed write in under 10 minutes.
2. Wrap a Mem0 memory operation with governance in approximately five lines.
3. Try the poisoning/blocking flow in a browser with zero local setup.
4. Find the project through the README, site, package documentation, and launch
   content, then measure whether they install, try, or contribute.

## Workstream 1 — Quickstart

### Outcome

`git clone` to “poisoned memory blocked and audit event visible” should work with
Docker only, without Python, conda, or third-party API keys.

### Plan

1. Define the happy path and keep it to one primary command:

   ```bash
   ./scripts/quickstart.sh
   ```

   On Windows PowerShell, use `./scripts/quickstart.ps1`.

2. Make environment configuration optional for local use. Keep `.env.example`
   for production/custom deployments, but ensure the default Compose values are
   sufficient for a clean clone.
3. Make readiness deterministic:
   - add or verify API and web health checks;
   - make Postgres readiness explicit;
   - ensure the seed job completes before the user is told to test the UI;
   - document the expected `docker compose ps` state.
4. Add a repeatable smoke test that verifies:
   - API `/healthz` responds;
   - the seeded tenant is available;
   - the web console loads;
   - an injection-like write is marked `untrusted`;
   - the audit event can be found.
5. Document normal restart, demo reseed, and destructive reset separately.
6. Test the path on macOS, Linux, and Windows PowerShell, including a cold clone,
   a warm rebuild, missing `.env`, and occupied ports.

### Acceptance criteria

- A new contributor completes the flow in under 10 minutes.
- No Python installation is needed for the primary path.
- Re-running the seed flow is safe and produces a predictable demo state.
- Every failure mode has a short, actionable troubleshooting note.

## Workstream 2 — Mem0 adapter

### Outcome

An existing Mem0 user can add GovernedMemory governance without replacing their
memory system.

### Plan

1. Confirm the Mem0 integration points and supported versions.
2. Choose a thin adapter boundary around the existing `metaworkers` client/API;
   do not duplicate governance logic in the adapter.
3. Provide a small wrapper for the common operations:
   - governed add/write;
   - governed search/retrieve;
   - quarantine or deny handling;
   - propagation of tenant, agent, session, and purpose context.
4. Preserve Mem0-compatible return shapes where practical and expose governance
   metadata (trust, taint, policy decision, and audit identifiers) explicitly.
5. Add unit tests with mocked Mem0 calls and an end-to-end test against the local
   Docker stack.
6. Publish a five-minute integration guide with a before/after example.

### Acceptance criteria

- A clean environment can install the adapter and import it successfully.
- The documented example wraps a Mem0 flow in roughly five lines.
- Untrusted or quarantined memories do not pass governed retrieval by default.
- The adapter guide links directly to the Quickstart and troubleshooting steps.

## Workstream 3 — Hosted sandbox

### Outcome

Someone who will not install Docker can still see an attack, governance decision,
and provenance result in under two minutes.

### Plan

1. Convert the hosted dashboard scaffold into a focused public demo rather than a
   general admin dashboard.
2. Build one guided flow:
   - paste or select a normal memory;
   - paste an injection/poisoning attempt;
   - show taint classification and the blocked action;
   - show the associated audit event and provenance path.
3. Use safe, deterministic demo data first. Do not expose the repository's live
   database or require user-provided secrets.
4. Keep the first interaction anonymous and frictionless. Add sign-in only for
   optional saved sessions or follow-up actions.
5. Add clear calls to action:
   - Run locally with the Quickstart.
   - Integrate with Mem0.
   - Join Discord.
   - Star or contribute on GitHub.
6. Deploy a preview, run browser verification, and publish the stable URL in the
   README and project site.

### Acceptance criteria

- The landing page loads without authentication or configuration.
- The core demo path completes in under two minutes.
- The result explains *why* the memory was blocked, not just that it was blocked.
- The sandbox never mutates production or shared user data.
- The UI works on a current desktop and mobile browser.

## Workstream 4 — Distribution

### Outcome

The project is easy to discover, easy to evaluate, and measurable after launch.

### Plan

1. Make the README the canonical entry point:
   - Quickstart above the fold;
   - hosted sandbox link;
   - Mem0 integration link;
   - short threat-model explanation;
   - contribution and Discord links.
2. Publish standalone integration pages for Quickstart and Mem0, then link them
   from the project site and use-case pages.
3. Package the adapter for its intended distribution channel and verify clean
   installation from a fresh environment.
4. Add discovery metadata:
   - GitHub topics such as `prompt-injection`, `llm-security`, `rag-security`,
     and `ai-agents`;
   - package keywords and repository descriptions;
   - social preview metadata and a short demo GIF/video.
5. Prepare launch assets:
   - a 60–90 second attack-block demo;
   - a short “why governed memory” post;
   - a contributor issue template;
   - a support path through Discord.
6. Track opt-in adoption signals without collecting memory contents:
   - Quickstart completion;
   - first governed write;
   - adapter installs;
   - sandbox starts/completions;
   - GitHub stars, clones, issues, and external pull requests.

### Acceptance criteria

- A visitor can reach the sandbox or Quickstart from the README in one click.
- The Mem0 guide is independently usable from a clean environment.
- The launch post links to working artifacts rather than screenshots alone.
- Metrics are privacy-preserving, documented, and actionable.

## Sequence and checkpoints

### Phase 1 — Make the path reliable

- Harden Quickstart readiness and reset behavior.
- Add the smoke test and cross-platform verification.

**Checkpoint:** an outside contributor completes the demo from a clean clone.

### Phase 2 — Make the path integratable

- Implement the Mem0 adapter.
- Publish the minimal integration guide and end-to-end test.

**Checkpoint:** a Mem0 user can run a governed write and retrieve example locally.

### Phase 3 — Make the path instant

- Replace the hosted dashboard scaffold with the guided sandbox.
- Deploy and verify the public flow.

**Checkpoint:** a first-time visitor sees a blocked attack and its audit evidence.

### Phase 4 — Make the path discoverable

- Update README/site/package metadata.
- Publish the demo assets and launch content.
- Turn on privacy-preserving adoption measurement.

**Checkpoint:** every public entry point leads to a working evaluation path.

## Metrics

- Install-to-first-value time: target under 10 minutes.
- Sandbox time-to-first-result: target under 2 minutes.
- Quickstart completion rate.
- Adapter installs and successful first governed operations.
- Sandbox completion rate and calls to action.
- GitHub stars, unique clones, issues, and external pull requests.

## Guardrails

- Do not duplicate governance logic in adapters or the sandbox.
- Do not collect or transmit user memory contents for analytics.
- Keep hosted demo data isolated from development and production data.
- Keep self-hosted operation functional without a managed account.
- Prefer one polished, reproducible flow over many partial integrations.
