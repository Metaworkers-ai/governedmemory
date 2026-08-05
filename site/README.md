# Governed Memory — landing page

A single self-contained static page (no build step, no dependencies) introducing the
project: the problem it solves, the four-stage governance pipeline, what's live vs.
in review vs. next, and a self-host quickstart. Separate in purpose from
[`web/`](../web) (the authenticated internal console) — this page is public and
requires no backend to load.

**Live:** https://governedmemory.metaworkers.ai/

**Hosted demo:** https://demo.metaworkers.ai/ (public, synthetic data only)

## Preview locally

It's one HTML file with everything inlined — just open it:

```bash
# Windows PowerShell, macOS, Linux
open site/index.html      # macOS
start site/index.html     # Windows
xdg-open site/index.html  # Linux
```

## Deploy

The canonical deployment is S3 + CloudFront (private bucket, CloudFront reads it
via Origin Access Control — no public S3 access). The production hostname above
currently serves that distribution. Pushes to `main` that touch `site/` are
deployed by `.github/workflows/site.yml` once the repository environment is
configured:

Required GitHub environment values for `production-site`:

- secret `SITE_AWS_ROLE_ARN`: an AWS IAM role trusted by GitHub Actions OIDC;
- variable `SITE_AWS_REGION` (defaults to `ap-south-1`);
- variable `SITE_S3_BUCKET`;
- variable `SITE_CLOUDFRONT_DISTRIBUTION_ID`.

The current production hostname is the public entry point. If the hostname
changes, add the replacement as a CloudFront alternate domain with an ACM
certificate in `us-east-1`, then update DNS and this document together.
