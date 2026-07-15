# Governed Memory — Use Cases

Every use case below maps to the same underlying problem: **once an AI agent can remember things and take actions, "what it remembers" becomes an attack surface and a compliance liability.** Governed Memory is the layer that sits between what an agent stores and what it's allowed to read or act on — so you can give agents real memory and real permissions (refunds, emails, escalations) without betting the company on every piece of text an agent ever ingests being trustworthy.

Ordered below by how urgent and buyer-visible the problem is — start at the top.

## 1. [Stop Agents From Acting on Poisoned Memory](01-privileged-action-fraud-prevention.md) ⭐ start here

The flagship use case. An agent that can issue refunds, send emails, or escalate accounts is one injected instruction away from doing it for an attacker instead of a customer. This is the scenario that blocks most enterprises from giving agents real write/action access at all — and the one Governed Memory was built around first. **Read this one in full**, the rest build on it.

## 2. [Prompt Injection Defense for Agent Memory](02-prompt-injection-defense.md)

Untrusted content (inbound email, scraped web pages, tool output) routinely contains "ignore previous instructions"-style payloads. Most RAG/memory pipelines store this text as if it were as trustworthy as a verified CRM record. Governed Memory scores and taints it on write, before it ever reaches a prompt.

## 3. [Multi-Tenant Isolation for Agent Platforms](03-multi-tenant-isolation.md)

If you're building an agent product that serves more than one customer, a single cross-tenant data leak is a company-ending incident, not a bug ticket. Tenant isolation is enforced at the storage layer here, not left to application-code discipline.

## 4. [Purpose-Limited Retrieval (Need-to-Know AI)](04-purpose-limited-memory-compliance.md)

GDPR/CCPA-style purpose limitation, applied to agent memory: a memory collected for support shouldn't silently become the basis for a sales or marketing decision. Governed Memory enforces this at query time, with an explanation of what got excluded and why.

## 5. [Tamper-Evident Audit Trail for Agent Decisions](05-tamper-evident-audit-trail.md)

"What did the agent know when it did that?" is the first question in every AI incident review and every enterprise security questionnaire. A hash-chained, append-only log answers it without trusting application logs that could have been edited after the fact.

## 6. [Memory Hygiene: Dedup and Supersede](06-memory-deduplication-hygiene.md)

A smaller but real cost center: agents re-writing the same fact every session bloats storage, slows retrieval, and — worse — lets a stale fact keep answering queries after it's been corrected. Automatic dedup and versioning fix this without any caller-side bookkeeping.

## 7. [AI Claims & Underwriting Agents for Insurance](07-insurance-claims-and-underwriting.md)

Industry deep-dive: how the mechanisms above apply specifically to claims and underwriting agents — blocking payout approval on fabricated or injected claim documents, keeping underwriting signals out of claims decisions, isolating books of business across carriers/MGAs, and producing an audit trail a market conduct exam can actually use.

## 8. [AI Payments, Lending & Advisory Agents for Financial Services](08-financial-services-payments-and-lending.md)

Industry deep-dive: the same mechanisms applied to banking and fintech — blocking a payments agent from wiring funds based on a fraudulent "updated remittance details" email (classic BEC), keeping KYC/AML monitoring data out of cross-sell and advisory decisions, isolating accounts across a multi-tenant platform, and producing an audit trail for regulatory exams.

## 9. [AI Recruiting & Talent Acquisition Agents](09-recruiting-and-talent-acquisition.md)

Industry deep-dive grounded in a documented real-world incident: hidden prompt-injection text in a scraped LinkedIn profile hijacking an AI recruiting workflow. Covers blocking hiring-decision actions on unverified/scraped candidate data, keeping one req's candidate data from silently screening another (relevant under NYC Local Law 144-style AEDT rules), staffing-platform tenant isolation, and adverse-action audit trails.

## 10. [AI Legal Research & Contract Review Agents](10-legal-and-contract-review.md)

Industry deep-dive grounded in *Mata v. Avianca* — the landmark case where attorneys were sanctioned for filing ChatGPT-fabricated citations. Covers preventing an agent's own unverified inference (or a planted instruction in opposing counsel's filing) from reaching a document as if it were verified authority, structural matter/client separation (the ethical-wall problem), and a defensible audit trail for challenged citations.

---

## Who this is for

- **Eng/AI leads** shipping a customer-facing or internal agent that reads memory and can take actions with real consequences (refunds, emails, account changes).
- **Security and compliance reviewers** who are the actual blocker on an agent rollout — these docs give you concrete answers to "what stops the agent from doing something dangerous with bad data?"
- **Platform teams** building a multi-tenant agent product, where isolation and auditability aren't optional.

## Try it yourself

Every code sample in these docs runs against the real, open-source engine. Fastest path to seeing it work:

```bash
git clone https://github.com/Metaworkers-ai/governedmemory.git
cd governedmemory
# ... see the Quickstart in the main README ...
python scripts/seed_demo.py --reset
streamlit run frontend/app.py
```

See [Quickstart](../../README.md#quickstart-populate-the-db--run-the-demo-frontend) in the main README for the full copy-paste setup.

The core engine (write governor, retrieval engine, policy engine, audit log) is MIT-licensed and self-hostable. If you need SSO/RBAC, a managed policy console, or help integrating this into an existing agent stack, see [Enterprise](../../README.md#enterprise).
