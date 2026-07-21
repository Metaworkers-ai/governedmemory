# Security Policy

Governed Memory handles multi-tenant customer data and is explicitly designed
to defend against prompt-injection and data-poisoning attacks. We take
security reports seriously and appreciate responsible disclosure.

> Looking for how the system handles data — the deployment model, what does and
> doesn't leave your environment, tenant isolation, and the audit trail? See the
> [Security & Data Handling Overview](docs/security-overview.md). This file is
> specifically about **reporting a vulnerability**.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, email **jagadish@metaworkers.ai** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce (a minimal repro is very helpful)
- Any relevant logs, screenshots, or PoC code

We aim to acknowledge reports within 3 business days and to provide a fix or
mitigation plan within 30 days for confirmed issues, depending on severity.

## Scope

In scope:
- Tenant isolation bypasses (a tenant reading/writing another tenant's data)
- Prompt-injection or taint-labeling bypasses (untrusted content not being
  flagged as untrusted)
- Audit log tampering that evades hash-chain detection
- SQL injection or other injection vulnerabilities in `core/`
- Authentication/authorization issues once E7 (the API layer) ships

Out of scope (for now):
- The `frontend/` Streamlit demo UI, which is a local development tool, not a
  hardened multi-user deployment
- Denial-of-service reports that require unrealistic resource assumptions
- Issues in third-party dependencies (report those upstream, but let us know
  too if it affects this project)

## Supported Versions

This project is pre-1.0 and under active development. Security fixes are
applied to `main` only — there are no maintained release branches yet.
