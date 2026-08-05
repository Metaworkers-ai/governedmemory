# Developer traction scorecard

This scorecard separates facts we can verify in the repository from outcomes
that require real-world usage. It is deliberately not embedded in the README,
where manually maintained numbers would become stale.

## Current verified state

| Indicator | Current value | Evidence / command |
| --- | --- | --- |
| Quickstart path | Implemented for macOS/Linux and PowerShell | `scripts/quickstart.sh`, `scripts/quickstart.ps1`, `docs/quickstart.md` |
| Hosted sandbox | Public link documented | `https://demo.metaworkers.ai/` |
| SDK package | Stable `metaworkers==0.1.0` documented | `sdk/python/pyproject.toml`, PyPI workflow |
| REST + SDK examples | Available | README and `examples/` |
| Opt-in collector | Local JSONL only; no hosted telemetry | `docs/adoption-metrics.md`, `scripts/adoption_collector.py` |
| Automated CI | Unit, integration, web, package, and Mem0 contract jobs configured | `.github/workflows/ci.yml` |

## Unavailable until measured

The repository does not currently verify GitHub stars/forks, PyPI download
counts, unique external contributors, issue response time, PR merge time,
Discord participation, hosted-demo completions, or first governed operations.
Do not present those as adoption numbers.

## Recommended measurement path

Use the local collector only when an operator has approval and a private report
location. Events must remain content-free and should be aggregated locally:

```bash
python scripts/adoption_collector.py \
  --file "$HOME/.governedmemory/adoption/events.jsonl" \
  --event quickstart_completed --surface quickstart --version 0.1.0 \
  --duration-seconds 120 --success
python scripts/adoption_metrics_report.py \
  "$HOME/.governedmemory/adoption/events.jsonl"
```

The hosted demo currently does not transmit events. Enabling a hosted collector
requires a separate privacy review covering consent, retention, deletion,
access, and ownership.

## 30 / 60 / 90-day targets

| Horizon | Target | How to verify honestly |
| --- | --- | --- |
| 30 days | 10 external Quickstart attempts and 3 reproducible issue reports | Private, approved collector report plus linked issues |
| 60 days | 25 successful Quickstarts, 10 SDK installs, 3 external contributors | Collector/report, PyPI stats, GitHub contributor history |
| 90 days | 50 successful demo/Quickstart completions, 5 external contributors, median issue first response under 3 days | Monthly report with timestamps and source links |

Targets are goals, not current results. Review this file monthly and record the
measurement date before sharing it publicly.
