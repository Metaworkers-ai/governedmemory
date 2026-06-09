"""
Load realistic sample CX data to demo the governed memory layer.
Run: python seed_data.py
"""
import httpx
import json

BASE = "http://localhost:8000"

SEED = [
    # Customer: cust_jane_001
    {
        "customer_id": "cust_jane_001",
        "content": "Customer Jane Doe is on Enterprise plan, SLA 4 hours, region US, renewal due Q4 2026.",
        "source_ref": "Salesforce CRM",
        "source_type": "crm",
        "sensitivity": "internal",
        "pii_fields": ["name"],
        "retention_days": 730,
        "allowed_roles": ["support", "billing", "manager"],
        "confidence": 0.98,
        "tags": ["plan", "sla", "renewal"],
    },
    {
        "customer_id": "cust_jane_001",
        "content": "Ticket #1842: Jane reported billing discrepancy after plan change on Jan 10. Refund of $320 approved pending manager review. Support Lead Sam promised credit by Jan 20.",
        "source_ref": "Zendesk #1842",
        "source_type": "ticket",
        "sensitivity": "confidential",
        "pii_fields": [],
        "retention_days": 365,
        "allowed_roles": ["support", "billing", "manager"],
        "confidence": 1.0,
        "tags": ["billing", "refund", "promise"],
    },
    {
        "customer_id": "cust_jane_001",
        "content": "Policy note: Refunds under $5K allowed with manager approval. Do not discuss internal ticket routing in customer-facing chat.",
        "source_ref": "Internal Policy KB v3.2",
        "source_type": "kb",
        "sensitivity": "confidential",
        "pii_fields": [],
        "retention_days": 180,
        "allowed_roles": ["support", "manager"],
        "confidence": 0.95,
        "tags": ["policy", "refund", "billing"],
    },
    {
        "customer_id": "cust_jane_001",
        "content": "Old preference: annual billing cycle. NOTE: superseded — latest contract changed to quarterly billing effective Mar 1 2026.",
        "source_ref": "Salesforce CRM",
        "source_type": "crm",
        "sensitivity": "internal",
        "pii_fields": [],
        "retention_days": 365,
        "allowed_roles": ["support", "billing"],
        "confidence": 0.6,
        "tags": ["billing", "preference"],
        # will be marked stale by newer billing preference entry below
    },
    {
        "customer_id": "cust_jane_001",
        "content": "Current billing: quarterly cycle starting Mar 1 2026. First invoice $2,400.",
        "source_ref": "Salesforce CRM",
        "source_type": "crm",
        "sensitivity": "internal",
        "pii_fields": [],
        "retention_days": 365,
        "allowed_roles": ["support", "billing"],
        "confidence": 1.0,
        "tags": ["billing", "preference"],
    },
    {
        "customer_id": "cust_jane_001",
        "content": "Call transcript May 5: Jane asked about escalation path for unresolved refund. Escalation owner: Sarah M. (Tier 2). Ticket re-opened.",
        "source_ref": "Voice transcript 2026-05-05",
        "source_type": "voice",
        "sensitivity": "confidential",
        "pii_fields": [],
        "retention_days": 365,
        "allowed_roles": ["support", "manager"],
        "confidence": 0.92,
        "tags": ["escalation", "refund"],
    },
    # Customer with PII for masking demo
    {
        "customer_id": "cust_bob_002",
        "content": "Customer Bob Smith, email bob.smith@example.com, phone 415-555-0192. Basic plan, monthly billing.",
        "source_ref": "Salesforce CRM",
        "source_type": "crm",
        "sensitivity": "pii",
        "pii_fields": ["email", "phone", "name"],
        "retention_days": 365,
        "allowed_roles": ["billing", "manager", "admin"],
        "confidence": 1.0,
        "tags": ["plan", "contact"],
    },
    {
        "customer_id": "cust_bob_002",
        "content": "Ticket #2201: Requested plan upgrade from Basic to Pro. Waiting on procurement approval.",
        "source_ref": "Zendesk #2201",
        "source_type": "ticket",
        "sensitivity": "internal",
        "pii_fields": [],
        "retention_days": 365,
        "allowed_roles": ["support", "billing", "manager"],
        "confidence": 0.95,
        "tags": ["upgrade", "plan"],
    },
]


def seed():
    print("Seeding Metaworkers demo data...\n")
    for item in SEED:
        r = httpx.post(f"{BASE}/ingest", json=item)
        r.raise_for_status()
        resp = r.json()
        print(f"  [OK] [{item['customer_id']}] {item['source_ref']} -> {resp['memory_id'][:8]}...")

    print(f"\n[DONE] Seeded {len(SEED)} memories across 2 customers.")
    print("\nTry:")
    print(f"  GET {BASE}/memory-card/cust_jane_001?agent_role=support")
    print(f"  GET {BASE}/memory-card/cust_jane_001?agent_role=billing")
    print(f"  POST {BASE}/query  body: {{\"customer_id\":\"cust_jane_001\",\"query_text\":\"refund billing\",\"agent_role\":\"support\"}}")
    print(f"\n  Swagger UI: {BASE}/docs")


if __name__ == "__main__":
    seed()
