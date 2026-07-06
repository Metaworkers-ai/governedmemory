"""
Streamlit UI for trying the E1 governed memory layer end-to-end.

This talks directly to MemoryStore — there is no REST API yet (that's E7).
Run:
    streamlit run frontend/app.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from core.memory_store import MemoryStore, NullEmbeddingProvider, init_db
from core.models import Provenance, Purpose, SourceType, Taint, WriteRequest

load_dotenv()

st.set_page_config(page_title="Governed Memory — E1 Demo", layout="wide")


@st.cache_resource
def get_store(dsn: str) -> MemoryStore:
    init_db(dsn)
    try:
        from core.memory_store import SentenceTransformerProvider
        embedder = SentenceTransformerProvider()
    except ImportError:
        embedder = NullEmbeddingProvider()
    return embedder, MemoryStore(dsn, embedder)


DSN = os.environ.get("DATABASE_URL", "postgresql://mw:mw_dev_password@localhost:5432/governedmemory")

try:
    embedder, store = get_store(DSN)
except Exception as e:
    st.error(f"Could not connect to Postgres at `{DSN}`.\n\nStart it with:\n"
             f"`docker compose -f deploy/docker-compose.yml up -d`\n\nError: {e}")
    st.stop()

if isinstance(embedder, NullEmbeddingProvider):
    st.info(
        "Using **NullEmbeddingProvider** (zero vectors) — vector search results will be "
        "arbitrary. Run `pip install -r requirements-embed-local.txt` and reload for real "
        "semantic search.",
        icon="ℹ️",
    )

st.title("Governed Memory — E1 Demo")
st.caption("Every write is tenant-scoped, provenance-tracked, and audit-logged. Try to break tenant isolation.")

NEW_CUSTOMER_SENTINEL = "+ New customer…"

with st.sidebar:
    st.header("Context")
    tenant_id = st.text_input("Tenant ID", value="solstice-cloud")

    customers = store.list_customers(tenant_id) if tenant_id else []
    if customers:
        counts = {c["customer_id"]: c["memory_count"] for c in customers}
        options = [NEW_CUSTOMER_SENTINEL] + [c["customer_id"] for c in customers]
        default_index = options.index("cust-maria-chen") if "cust-maria-chen" in options else 1
        chosen = st.selectbox(
            "Customer ID  (type to search)",
            options,
            index=default_index,
            format_func=lambda cid: cid if cid == NEW_CUSTOMER_SENTINEL else f"{cid}  ({counts[cid]})",
        )
        customer_id = st.text_input("New customer ID", value="cust-new-001") if chosen == NEW_CUSTOMER_SENTINEL else chosen
    else:
        customer_id = st.text_input("Customer ID", value="cust-maria-chen")
        if tenant_id:
            st.caption("No customers yet for this tenant — type a new customer ID to write the first memory.")

    agent_id = st.text_input("Agent ID", value="cx-agent-1")
    session_id = st.text_input("Session ID", value="demo-session")
    st.divider()
    if tenant_id:
        stats = store.get_stats(tenant_id)
        st.metric("Memories (this tenant)", stats["total_memories"])
        st.metric("Customers (this tenant)", stats["total_customers"])
        if stats["total_memories"] == 0:
            st.caption("No data yet — run `python scripts/seed_demo.py` to populate the demo.")

tab_write, tab_browse, tab_search, tab_governance, tab_isolation, tab_audit = st.tabs(
    ["Write", "Browse", "Search", "Governance", "Tenant Isolation", "Audit Log"]
)

# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
with tab_write:
    st.subheader("Write a memory")
    with st.form("write_form"):
        content = st.text_area("Content", placeholder="Customer prefers email contact...")
        col1, col2 = st.columns(2)
        with col1:
            source_type = st.selectbox("Source type", [s.value for s in SourceType])
            source_ref = st.text_input("Source ref", value="zendesk-ticket-4821")
        with col2:
            confidence = st.slider("Confidence", 0.0, 1.0, 0.95)
            allowed_purposes = st.text_input("Allowed purposes (comma-separated)", value="cx_support")
        submitted = st.form_submit_button("Write memory", type="primary")

    if submitted:
        if not content or not tenant_id or not customer_id:
            st.error("Tenant ID, Customer ID, and Content are required.")
        else:
            req = WriteRequest(
                tenant_id=tenant_id,
                customer_id=customer_id,
                agent_id=agent_id,
                session_id=session_id,
                content=content,
                provenance=Provenance(
                    source_type=SourceType(source_type),
                    source_ref=source_ref,
                    confidence=confidence,
                ),
                purpose=Purpose(allowed_purposes=[p.strip() for p in allowed_purposes.split(",") if p.strip()]),
            )
            record = store.write(req)
            taint_icon = {"trusted": "✅", "untrusted": "⚠️", "quarantined": "🚫"}[record.trust.taint.value]
            st.success(f"Written — id `{record.id}`  {taint_icon} taint: **{record.trust.taint.value}**")
            if record.trust.taint_reason:
                st.caption(f"Reason: {record.trust.taint_reason}")

# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------
with tab_browse:
    st.subheader(f"Customers in tenant `{tenant_id}`")
    if tenant_id and customers:
        filter_text = st.text_input("Filter by customer ID", placeholder="type to search", key="customer_filter")
        filtered = [c for c in customers if filter_text.lower() in c["customer_id"].lower()] if filter_text else customers
        st.dataframe(
            [{"Customer ID": c["customer_id"], "Memories": c["memory_count"], "Last activity": str(c["last_activity"])}
             for c in filtered],
            use_container_width=True, hide_index=True,
        )
    elif tenant_id:
        st.write("No customers yet — write a memory in the **Write** tab.")

    st.divider()
    st.subheader(f"Memories for `{customer_id}` in tenant `{tenant_id}`")
    if st.button("Refresh", key="refresh_browse"):
        st.cache_data.clear()
    if tenant_id and customer_id:
        memories = store.list_for_customer(tenant_id, customer_id)
        if not memories:
            st.write("No memories yet — write one in the **Write** tab.")
        for m in memories:
            taint_icon = {"trusted": "✅", "untrusted": "⚠️", "quarantined": "🚫"}[m.trust.taint.value]
            with st.expander(f"{taint_icon} {m.content[:80]}  —  `{m.id}`"):
                st.json({
                    "id": m.id,
                    "content": m.content,
                    "taint": m.trust.taint.value,
                    "taint_reason": m.trust.taint_reason,
                    "source_type": m.provenance.source_type.value,
                    "source_ref": m.provenance.source_ref,
                    "confidence": m.provenance.confidence,
                    "allowed_purposes": m.purpose.allowed_purposes,
                    "created_at": str(m.created_at),
                })

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
with tab_search:
    st.subheader("Search (tenant-scoped)")
    query = st.text_input("Query", placeholder="refund policy")
    purpose_filter = st.text_input("Purpose (optional)", placeholder="e.g. billing, cx_support, sales",
                                     help="If set, only records with this purpose in allowed_purposes "
                                          "(or an empty allowed_purposes — open to any) are returned.")
    include_untrusted = st.checkbox("Include untrusted/quarantined (bypass the privilege gate)")

    if query and tenant_id:
        st.markdown("### `retrieve()` — governed hybrid search (E3)")
        st.caption("Reciprocal rank fusion over vector + lexical, then the privilege gate "
                   "(taint + purpose). This is what agents should actually call.")
        gated_results = store.retrieve(query, tenant_id, agent_id, session_id,
                                        purpose=purpose_filter or None, k=5,
                                        include_untrusted=include_untrusted)
        if not gated_results:
            st.write("No results — try a broader query, a different purpose, or check the untrusted box.")
        for r in gated_results:
            taint_icon = {"trusted": "✅", "untrusted": "⚠️", "quarantined": "🚫"}[r.trust.taint.value]
            st.write(f"- {taint_icon} {r.content[:100]}  `purposes={r.purpose.allowed_purposes or ['any']}`")

        st.divider()
        st.markdown("### Raw primitives (ungated — for comparison only)")
        st.caption("vector_search()/lexical_search() apply no taint or purpose filtering. "
                   "This is what agents got before E3 — notice untrusted/quarantined records can appear here.")
        search_col1, search_col2 = st.columns(2)
        with search_col1:
            st.markdown("**Vector search** (semantic)")
            for r in store.vector_search(query, tenant_id, k=5):
                taint_icon = {"trusted": "✅", "untrusted": "⚠️", "quarantined": "🚫"}[r.trust.taint.value]
                st.write(f"- {taint_icon} {r.content[:100]}")
        with search_col2:
            st.markdown("**Lexical search** (full-text)")
            for r in store.lexical_search(query, tenant_id, k=5):
                taint_icon = {"trusted": "✅", "untrusted": "⚠️", "quarantined": "🚫"}[r.trust.taint.value]
                st.write(f"- {taint_icon} {r.content[:100]}")

# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------
with tab_governance:
    st.subheader("Quarantine / Delete")
    memories = store.list_for_customer(tenant_id, customer_id) if tenant_id and customer_id else []
    if not memories:
        st.write("No memories for this customer yet.")
    else:
        options = {f"{m.content[:60]} ({m.trust.taint.value})": m.id for m in memories}
        choice = st.selectbox("Select a memory", list(options.keys()))
        memory_id = options[choice]

        col1, col2 = st.columns(2)
        with col1:
            reason = st.text_input("Quarantine reason", value="potential prompt injection")
            if st.button("Quarantine", type="secondary"):
                ok = store.quarantine(memory_id, tenant_id, reason=reason)
                st.success("Quarantined." if ok else "Failed.")
                st.rerun()
        with col2:
            st.write("")
            st.write("")
            if st.button("Delete permanently", type="secondary"):
                ok = store.delete(memory_id, tenant_id)
                st.success("Deleted." if ok else "Failed.")
                st.rerun()

# ---------------------------------------------------------------------------
# Tenant isolation demo
# ---------------------------------------------------------------------------
with tab_isolation:
    st.subheader("Prove tenant isolation")
    st.write(
        "Write a memory as **tenant A**, then try to read it as **tenant B**. "
        "A correct implementation always returns `None` for the cross-tenant read."
    )
    col1, col2 = st.columns(2)
    with col1:
        tenant_a = st.text_input("Tenant A", value="tenant-a")
    with col2:
        tenant_b = st.text_input("Tenant B", value="tenant-b")

    if st.button("Run isolation test", type="primary"):
        rec = store.write(WriteRequest(
            tenant_id=tenant_a,
            customer_id="cust-001",
            agent_id="agent-1",
            session_id="sess-1",
            content="Confidential info for tenant A",
            provenance=Provenance(source_type=SourceType.TRUSTED_SYSTEM, source_ref="crm"),
        ))
        same_tenant = store.get(rec.id, tenant_a)
        cross_tenant = store.get(rec.id, tenant_b)

        st.write(f"Written to `{tenant_a}` — id `{rec.id}`")
        st.success(f"Read as `{tenant_a}` (same tenant): **{same_tenant.content}**")
        if cross_tenant is None:
            st.success(f"Read as `{tenant_b}` (different tenant): **None** — isolation holds ✅")
        else:
            st.error(f"Read as `{tenant_b}` (different tenant): **{cross_tenant.content}** — DATA LEAK ❌")

# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
with tab_audit:
    st.subheader(f"Audit trail for `{tenant_id}`")
    st.caption("Each event's hash is SHA-256(prev_hash + payload) — a tamper-evident chain.")
    if tenant_id:
        events = store.list_audit(tenant_id, limit=50)
        if not events:
            st.write("No audit events yet.")
        for e in events:
            outcome_icon = {"allow": "✅", "deny": "🚫", "gated": "🟡"}.get(e["outcome"], "•")
            st.text(
                f"{outcome_icon} {e['ts']}  op={e['op']:<10}  outcome={e['outcome']:<6}  "
                f"hash={e['hash'][:12]}…  prev={e['prev_hash'][:12]}…"
            )
