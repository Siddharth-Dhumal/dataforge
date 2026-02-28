import streamlit as st
from datetime import datetime, timezone

from ui.theme import apply_theme
from ui.state import init_state

apply_theme()
init_state()

# Full-width
st.markdown(
    """
    <style>
      .block-container{
        max-width: 100% !important;
        padding-left: clamp(18px, 4vw, 72px) !important;
        padding-right: clamp(18px, 4vw, 72px) !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("IT Admin Console")
st.caption("Audit • masking • registry")


def get_masked_columns() -> list[str]:
    spec = st.session_state.get("last_generated_spec") or {}
    gov = spec.get("governance") or {}
    cols = gov.get("mask_columns") or []
    return cols if isinstance(cols, list) else []


def get_current_app_name() -> str:
    spec = st.session_state.get("last_generated_spec") or {}
    return spec.get("app_name") or "Unnamed App"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_real_audit():
    """Try to pull real audit data from Databricks."""
    try:
        from core.databricks_connect import get_audit_feed
        df = get_audit_feed(limit=50)
        if "error" not in df.columns and not df.empty:
            return df.to_dict("records")
    except Exception:
        pass
    return None


masked_cols = get_masked_columns()

# --- Actions (top) ---
with st.container(border=True):
    b1, b2, b3, b4 = st.columns([1.0, 1.0, 1.0, 1.0], gap="medium")

    with b1:
        if st.button("Seed audit", key="seed_audit", use_container_width=True):
            st.session_state.audit_events.extend(
                [
                    {"ts": now_utc(), "event": "factory_generate", "status": "allowed", "note": "Generated spec (demo seed)."},
                    {"ts": now_utc(), "event": "dashboard_query", "status": "allowed", "note": "Governed query (demo seed)."},
                    {"ts": now_utc(), "event": "chat_query", "status": "blocked", "note": "Blocked sensitive request (demo seed)."},
                ]
            )
            st.success("Seeded.")
            st.rerun()

    with b2:
        if st.button("Register app", key="register_app", use_container_width=True):
            st.session_state.app_registry.append(
                {
                    "ts": now_utc(),
                    "app_name": get_current_app_name(),
                    "dataset": st.session_state.get("selected_dataset"),
                    "status": "registered",
                    "notes": "Demo registry entry.",
                }
            )
            # Also register in Databricks if possible
            try:
                from factory.registry import register_app
                spec = st.session_state.get("last_generated_spec") or {}
                code = st.session_state.get("last_generated_code") or ""
                register_app(
                    creator_role="analyst",
                    spec=spec,
                    generated_code=code,
                    status="registered",
                    app_id=f"app_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                )
            except Exception:
                pass
            st.success("Registered.")
            st.rerun()

    with b3:
        if st.button("🔄 Fetch Live Audit", key="fetch_live_audit", use_container_width=True):
            real_audit = fetch_real_audit()
            if real_audit:
                st.session_state.databricks_audit = real_audit
                st.success(f"Fetched {len(real_audit)} audit records from Databricks.")
            else:
                st.warning("Could not fetch live audit data. Using local events.")
            st.rerun()
    
    with b4:
        if st.button("Clear", key="clear_console", use_container_width=True):
            st.session_state.audit_events = []
            st.session_state.app_registry = []
            if "databricks_audit" in st.session_state:
                del st.session_state.databricks_audit
            st.success("Cleared.")
            st.rerun()

# --- Databricks Live Audit (if fetched) ---
if st.session_state.get("databricks_audit"):
    with st.container(border=True):
        st.subheader("🔴 Live Databricks Audit Log")
        st.caption("Real-time data from `workspace.audit.query_log`")
        st.dataframe(st.session_state.databricks_audit, use_container_width=True)

# --- Local Audit ---
with st.container(border=True):
    st.subheader("Audit (Session)")

    f1, f2, f3 = st.columns([1.0, 1.0, 1.2], gap="medium")
    with f1:
        st.selectbox("Status", ["All", "allowed", "blocked"], key="admin_filter_status")
    with f2:
        st.selectbox("Event", ["All", "factory_generate", "dashboard_query", "chat_query"], key="admin_filter_event")
    with f3:
        st.text_input("Search", key="admin_search", placeholder="masked, LIMIT, blocked...")

    status_filter = st.session_state.admin_filter_status
    event_filter = st.session_state.admin_filter_event
    search = (st.session_state.admin_search or "").strip().lower()

    filtered = []
    for ev in st.session_state.audit_events:
        if status_filter != "All" and ev.get("status") != status_filter:
            continue
        if event_filter != "All" and ev.get("event") != event_filter:
            continue
        if search and search not in str(ev.get("note", "")).lower():
            continue
        filtered.append(ev)

    if filtered:
        st.dataframe(filtered, use_container_width=True)
    else:
        st.dataframe([{"ts": "", "event": "", "status": "", "note": ""}], use_container_width=True)

# --- Governance ---
with st.container(border=True):
    st.subheader("Governance")
    st.caption(f"Masked columns: {', '.join(masked_cols) if masked_cols else '—'}")
    st.caption(f"Safe mode: {'ON' if st.session_state.safe_mode else 'OFF'}")
    st.caption("Query mode: SELECT-only • LIMIT enforced • governed views only")
    st.caption("PII column: `regional_manager` (masked via Unity Catalog)")

# --- Registry ---
with st.container(border=True):
    st.subheader("Registry")
    if st.session_state.app_registry:
        st.dataframe(st.session_state.app_registry, use_container_width=True)
    else:
        st.caption("No registered apps yet.")