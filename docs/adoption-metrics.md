# Privacy-preserving adoption metrics

Adoption measurement is opt-in and event-only. Never send memory content,
queries, customer IDs, API keys, IP addresses, or full error payloads to an
analytics endpoint.

## Collector decision and configuration

As of 24 July 2026, the public hosted collector is **not enabled**. This
preserves the self-hosted product's no-outbound-network default and avoids
collecting usage data before retention, access, deletion, and privacy-notice
requirements are approved. The hosted demo therefore does not transmit
analytics.

The repository now includes a local, opt-in JSONL collector. It makes no
network requests, accepts only the event contract below, generates an
ephemeral anonymous identifier by default, and stores a newly-created file as
owner-readable (`0600`). Operators can use it when they have a private,
approved location for the report input:

```bash
python scripts/adoption_collector.py \
  --file "$HOME/.governedmemory/adoption/events.jsonl" \
  --event quickstart_completed \
  --surface quickstart \
  --version 0.1.0 \
  --duration-seconds 19 \
  --success

python scripts/adoption_metrics_report.py \
  "$HOME/.governedmemory/adoption/events.jsonl"
```

This is deliberately an operator-invoked configuration, not automatic
telemetry. Enabling a hosted endpoint later requires an explicit team decision
covering the endpoint owner, retention period, access controls, deletion path,
privacy notice, and an opt-in mechanism before any deployment configuration is
changed.

## Event contract

An event is a JSON object with these fields:

```json
{
  "event": "quickstart_completed",
  "occurred_at": "2026-07-22T12:00:00Z",
  "anonymous_id": "salted-install-or-session-hash",
  "surface": "quickstart",
  "version": "0.1.0",
  "duration_seconds": 184,
  "success": true,
  "error_code": null
}
```

Allowed event names:

| Event | Meaning |
| --- | --- |
| `quickstart_started` | Wrapper began a local startup attempt |
| `quickstart_completed` | API health, web readiness, and seed checks passed |
| `sandbox_started` | Hosted demo loaded without authentication |
| `sandbox_completed` | Guided write → governed search → audit flow completed |
| `sdk_install` | A package installation check completed |
| `first_governed_operation` | First successful governed write/retrieval observed |
| `cta_clicked` | A user selected a documented next step |

`anonymous_id` must be generated locally from a rotating salt or ephemeral
session identifier. It must not be reversible into a person, repository clone,
customer, or memory record.

## Local report

The repository includes a dependency-free report generator:

```bash
python scripts/adoption_metrics_report.py events.jsonl
```

It prints event totals and funnel conversion rates. The input file is expected
to contain only the fields above; malformed or unknown events are reported and
excluded rather than silently counted.

The current public demo does not enable a hosted analytics collector. The
local collector and report are the supported measurement path until the team
approves those hosted controls.
