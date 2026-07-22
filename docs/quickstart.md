# Quickstart integration guide

This is the shortest path from a clean checkout to a governed memory decision.
It is intentionally Docker-only: Python, conda, and third-party API keys are
not required for the demo.

## Hosted path (zero install)

Open the [hosted sandbox](https://demo.metaworkers.ai/) and follow the guided
Write → Search → Audit Log flow. Use synthetic data only; the hosted deployment
is disposable and may be reseeded.

## Local path

```bash
git clone https://github.com/Metaworkers-ai/governedmemory.git
cd governedmemory
./scripts/quickstart.sh
```

On Windows PowerShell:

```powershell
git clone https://github.com/Metaworkers-ai/governedmemory.git
Set-Location governedmemory
.\scripts\quickstart.ps1
```

The wrapper starts Docker Desktop when possible, chooses free host ports, waits
for Postgres/API/web readiness, and prints clickable URLs. Open the web URL and:

1. Select **Benign example** in **Write** and submit it. Expect `trusted`.
2. Select **Fake system override** and submit it. Expect `untrusted` or
   `quarantined`, with a scanner reason.
3. In **Search**, leave **Include untrusted/quarantined** off and query the
   example. The flagged record must be excluded.
4. Open **Audit Log** and confirm the write decision and hash-chain fields.

## Lifecycle commands

```bash
./scripts/quickstart.sh down    # stop containers; preserve volumes
./scripts/quickstart.sh reset   # remove clone-specific volumes; erase demo data
./scripts/quickstart.sh         # start and reseed the demo
```

PowerShell uses the equivalent `./scripts/quickstart.ps1 down` and `reset`
commands. Use `reset` only for a disposable demo database.

## Troubleshooting

- **Docker is not installed:** install Docker Desktop, then rerun the wrapper.
- **A port is occupied:** the wrapper scans Postgres `5432–5442`, API
  `8000–8010`, and web `3000–3010`. Override with
  `POSTGRES_HOST_PORT`, `API_HOST_PORT`, or `WEB_HOST_PORT`.
- **The API is not ready:** rerun the wrapper and inspect its printed Compose
  status and service logs; failures include the selected project and ports.
- **The browser shows no demo records:** run `reset`, then start again and wait
  for the seed service to complete.

For the underlying API and Python client, see the [REST API and SDK section in
the README](../README.md#rest-api-e7--self-hosted). For the next integration
step, see the [Mem0 adapter guide](https://github.com/Metaworkers-ai/governedmemory/blob/main/docs/integrations/mem0.md).
