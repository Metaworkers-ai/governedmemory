# Privacy-preserving adoption metrics

Adoption measurement is opt-in and event-only. Never send memory content,
queries, customer IDs, API keys, IP addresses, or full error payloads to an
analytics endpoint.

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

The current public demo does not enable a hosted analytics collector. Configure
one only after reviewing retention, access, and deletion policy with the team.
