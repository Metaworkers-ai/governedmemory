# Distribution checklist

This page separates repository changes from account-level launch operations.

## Done in the repository

- [Quickstart guide](quickstart.md) is a standalone entry point.
- The README and project site link to the hosted sandbox.
- The SDK is published to PyPI as stable `metaworkers==0.1.0`; the release
  workflow also verifies a clean installation from PyPI.
- Version tags build a wheel and source distribution through
  `.github/workflows/publish-python.yml`.
- The project site has an OIDC-based S3/CloudFront deployment workflow, with
  `governedmemory.metaworkers.ai` as the intended canonical URL and
  `govmem.metaworkers.ai` as its short alias.
- Bug-report and feature-request issue forms protect against accidental secret
  or memory-content disclosure.
- A short attack/block [GIF](assets/governedmemory-demo.gif) and launch drafts
  are committed.
- Privacy-preserving adoption events and a local report generator are documented
  in [adoption-metrics.md](adoption-metrics.md).
- The hosted-demo flow was verified with synthetic data; the timing and mobile
  layout verification are recorded in [hosted-sandbox.md](hosted-sandbox.md).

## Account-level follow-ups

These require repository, PyPI, AWS, or DNS administration and are not implied
by a code commit:

1. Configure the `production-site` GitHub environment values listed in
   [site/README.md](../site/README.md), then run the site workflow once with
   `workflow_dispatch`. The DNS aliases are already serving the CloudFront
   distribution; verify the ACM certificate and CloudFront alternate-domain
   entries in AWS before calling this complete.
2. After deployment, verify `og:url`, the README link, both aliases, and HTTPS
   redirects from the CloudFront infrastructure URL.
3. Publish the launch draft through the agreed channels after a maintainer has
   reviewed claims and links.
4. Decide whether to enable an adoption collector. If enabled, accept only the
   event contract in [adoption-metrics.md](adoption-metrics.md), with retention
   and deletion controls documented before collection starts.

No step above requires collecting memory contents or granting public write
access to production infrastructure.
