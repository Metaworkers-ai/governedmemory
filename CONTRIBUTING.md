# Contributing to GovernedMemory

Thanks for helping make AI-agent memory safer and easier to inspect. Small,
reproducible contributions are welcome: tests, documentation, examples,
integration contracts, and focused fixes are all valuable.

## Before you start

- Read the [Code of Conduct](CODE_OF_CONDUCT.md) and [security policy](SECURITY.md).
- Search existing issues and Discord discussions before opening a duplicate.
- Never commit API keys, customer data, raw memory contents, or unsanitized logs.
- Use a short-lived branch from the latest `main`; do not work directly on `main`.

## Prerequisites

| Tool | Supported baseline |
| --- | --- |
| Python | 3.11+ |
| Node.js | 22 (for the Next.js console) |
| Docker | Docker Desktop or Docker Engine with Compose v2 |
| Git | 2.40+ recommended |

## First-time setup

```bash
git clone https://github.com/Metaworkers-ai/governedmemory.git
cd governedmemory
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\Activate.ps1    # Windows PowerShell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pip install -e sdk/python
```

For the fastest product check, use the [Docker Quickstart](docs/quickstart.md)
instead; it does not require a Python environment.

## Daily development loop

```bash
git switch main
git pull --ff-only origin main
git switch -c fix/short-description

# edit code and tests
python -m pytest tests/unit/ -q
python -m ruff check core/ api/ tests/ sdk/python/ integrations/ scripts/
python -m ruff format --check core/ api/ tests/ sdk/python/ integrations/ scripts/
git diff --check
```

Run integration tests when a change touches persistence, API behavior, or
Docker:

```bash
docker compose -f deploy/docker-compose.yml up -d
python -m pytest tests/integration/ -q
```

For web changes:

```bash
cd web
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

## Test matrix

| Area | Command | Needs Docker? |
| --- | --- | --- |
| Unit and SDK tests | `pytest tests/unit/ -q` | No |
| API/store integration | `pytest tests/integration/ -q` | Yes |
| Mem0 contract | `pip install -e 'sdk/python[mem0]'` then `pytest tests/unit/test_mem0_contract.py -q` | No, pinned package |
| Docs links | `python scripts/check_docs_links.py` | No |
| Quickstart endpoint smoke | `python scripts/smoke_quickstart.py` | Running Quickstart |
| Detection evaluation | `python scripts/eval_detection.py` | No |
| Web lint/typecheck/build | `npm run lint`, `npx tsc --noEmit`, `npm run build` in `web/` | No |

If a dependency or platform is unavailable, report the exact command and
reason rather than replacing the result with a guess.

## Where to make changes

Read the [contributor map](docs/contributor-map.md) before choosing a file.
Keep governance logic in `core/`; API and SDK layers should transport it, not
duplicate it. New integrations need a documented contract, mocked unit tests,
and an integration test when the external dependency is available.

## Pull requests

Use a clear Conventional Commit-style title, for example:

```text
fix(api): reject cross-tenant memory lookup
docs(quickstart): clarify occupied-port recovery
test(mem0): cover malformed result IDs
```

Every PR should include:

- the user/operator problem and the narrow change made;
- tests and validation commands with exact results;
- security, migration, or compatibility implications;
- documentation updates for changed public behavior;
- screenshots or a short recording for visible UI changes;
- confirmation that no secrets or private data are included.

Do not claim benchmark results, adoption, security guarantees, or production
readiness unless the PR includes a reproducible measurement and its scope.

## Good first contributions

See [good first issue guidance](docs/good-first-issue.md). Good starter work
includes a missing regression test, a focused docs correction, a runnable
example, or a sanitized cross-platform validation report.

## Release and deployment notes

The SDK is released independently from the pre-1.0 server package. The PyPI
workflow validates that a pushed tag exactly matches `sdk/python/pyproject.toml`
before publishing. Site deployment requires the repository's configured
`production-site` environment and AWS variables; contributors should not add
credentials to the repository.

## Maintainer expectations

Maintainers prioritize reproducibility, narrow diffs, honest claims, and
reviewable tests. A change may be declined when it broadens the threat model,
adds an unsupported integration, or makes a public claim that cannot be
verified. Security reports belong in [SECURITY.md](SECURITY.md), not in public
issues.
