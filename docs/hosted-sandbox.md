# Hosted sandbox runbook

The public sandbox is available at <https://demo.metaworkers.ai/>. It is a
short, anonymous demonstration of the same governed write, retrieval, and audit
surfaces exposed by the self-hosted stack.

## Two-minute verification flow

Use a fresh browser session and synthetic data only.

1. Open the demo and confirm that no login or API key is requested.
2. In **Write**, choose **Benign example**, submit it, and confirm the result is
   `trusted`.
3. Choose **Phishing via a "trusted" source** or **Fake system override** and
   submit it. Confirm the result is `untrusted` or `quarantined`, including the
   scanner reason when shown.
4. In **Search**, run a query matching the example with
   **Include untrusted/quarantined** disabled. The governed result set must not
   contain the flagged memory.
5. Open **Audit Log** and confirm the write decision is present with its
   tamper-evident hash-chain fields.

The flow is complete when the five steps take less than two minutes on desktop
and mobile widths.

## Safety boundaries

- The hosted deployment must be demo-only and use a dedicated demo tenant and
  demo API credential; it is not a production environment.
- The seeded records and the examples are synthetic. Never enter customer,
  personal, secret, or production data.
- The public UI does not expose a reset or delete-all control. This prevents an
  anonymous visitor from changing the shared baseline for everyone else.
- The deployment owner restores the disposable baseline by rerunning
  `python scripts/seed_demo.py --reset` against the demo database, or by
  recreating the hosted deployment. For a local clone, use:

  ```bash
  ./scripts/quickstart.sh reset
  ./scripts/quickstart.sh
  ```

- Any hosted deployment change should be made against the demo database only;
  production credentials and production databases must never be wired into the
  public web console.

## Usability checks

Verify the following after each hosted deployment:

- anonymous access works after a refresh and in a private browser window;
- the write examples, result banners, tables, and navigation fit at roughly
  390px and 1440px viewport widths;
- the complete verification flow above finishes in under two minutes;
- the README and project site link directly to the stable demo URL.
