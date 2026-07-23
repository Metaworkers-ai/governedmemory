# Distribution checklist

This page separates repository changes from account-level launch operations.

## Done in the repository

- [Quickstart guide](quickstart.md) is a standalone entry point.
- The README and project site link to the hosted sandbox.
- The SDK has PyPI metadata and a clean-install CI job.
- Version tags build a wheel and source distribution through
  `.github/workflows/publish-python.yml`.
- The project site has an OIDC-based S3/CloudFront deployment workflow.
- Bug-report and feature-request issue forms protect against accidental secret
  or memory-content disclosure.
- A short attack/block [GIF](assets/governedmemory-demo.gif) and launch drafts
  are committed.
- Privacy-preserving adoption events and a local report generator are documented
  in [adoption-metrics.md](adoption-metrics.md).

## Account-level follow-ups

These require repository, PyPI, AWS, or DNS administration and are not implied
by a code commit:

1. Bump `sdk/python/pyproject.toml` to the release version, configure the PyPI
   `pypi` environment and trusted publisher for
   `publish-python.yml`, then publish the adapter-enabled `metaworkers` extra
   from a matching version tag. The workflow verifies the package can be
   installed from PyPI after publication.
2. Configure the `production-site` GitHub environment values listed in
   [site/README.md](../site/README.md), then run the site workflow once with
   `workflow_dispatch`.
3. Choose the final custom domain, provision an ACM certificate in `us-east-1`,
   add the CloudFront alternate domain, and update `og:url` plus the README
   website badge after DNS is live.
4. Publish the launch draft through the agreed channels after a maintainer has
   reviewed claims and links.
5. Decide whether to enable an adoption collector. If enabled, accept only the
   event contract in [adoption-metrics.md](adoption-metrics.md), with retention
   and deletion controls documented before collection starts.

No step above requires collecting memory contents or granting public write
access to production infrastructure.
