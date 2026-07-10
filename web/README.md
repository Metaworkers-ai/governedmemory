# Governed Memory — Web UI

A Next.js console for the governed memory REST API ([`../api`](../api)), replacing the
[Streamlit demo](../frontend/app.py) as the primary way to use this project from a
browser. Talks to the API over plain HTTP — no direct dependency on `core`, Postgres,
or Python at all.

Pages: Write, Browse (customers → memories), Search (governed `retrieve()`),
Governance (quarantine/delete), Audit Log.

## Architecture

- **Server Components fetch directly** from the REST API (`lib/backend.ts`) for reads
  (Browse, Audit Log).
- **Server Actions** (`app/actions.ts`) handle mutations (write, quarantine, delete)
  and one client-triggered read (search), following Next.js's App Router conventions
  rather than a hand-rolled `/api/*` proxy layer.
- **The API key never reaches the browser.** `lib/backend.ts` is marked with the
  [`server-only`](https://www.npmjs.com/package/server-only) import, which turns an
  accidental import from a Client Component into a build error rather than a runtime
  leak.
- **Single-tenant-per-deployment.** The REST API resolves `tenant_id` entirely from
  the API key you configure (see [`../api/auth.py`](../api/auth.py)) — there's no
  tenant switcher in the UI. Run one deployment per tenant, same as any other
  self-hosted client of the API.
- Customer/agent/session IDs are shared UI-only state (a `ContextBar`, backed by
  `localStorage`) across the Write/Search/Governance pages, similar to the Streamlit
  demo's sidebar. This is convenience state for the browser tab, not sent as an
  identity/auth claim to the API.

## Known gaps vs. the Streamlit demo

The REST API (E7) covers write/retrieve/quarantine/delete/audit/customers/memories.
Two things from the Streamlit demo have no REST equivalent yet and are **not**
reproduced here:

- **Policy tab** (view/add purpose bindings, check a privileged action) — no
  `/v1/policy` or `/v1/check-privilege` routes exist.
- **Raw-vs-gated search comparison** ("what got excluded and why") — Streamlit builds
  this by calling `core`'s internal fusion/gate functions directly; `/v1/retrieve`
  only returns the final governed result set.
- **Tenant Isolation demo** — an engineering proof (write as tenant A, prove tenant B
  can't read it), not a product feature; doesn't fit a single-tenant-per-deployment
  frontend built on top of per-tenant API keys.

## Setup

```bash
cp .env.example .env.local   # fill in GOVERNEDMEMORY_API_URL / GOVERNEDMEMORY_API_KEY
npm install
npm run dev
```

Requires the REST API running somewhere reachable (`make api` from the repo root, or
`docker compose -f ../deploy/docker-compose.yml up -d`) with a key configured in its
`GOVERNEDMEMORY_API_KEYS`.

Opens at `http://localhost:3000`.

## Commands

```bash
npm run dev     # dev server, Turbopack
npm run build   # production build
npm run lint    # eslint
npx tsc --noEmit  # type-check
```
