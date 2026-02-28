from datetime import datetime, timezone
import streamlit as st

from ui.theme import apply_theme
from ui.state import init_state
from ui.chat_engine import answer_chat
from ui.components import ai_briefing

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

st.title("Chat")
st.caption("Governed Q&A (SELECT-only • LIMIT • masked)")

# --- Suggested Queries (match real tables) ---
with st.container(border=False):
    st.markdown("<div class='df-subtitle' style='margin-bottom: 8px;'>Suggested Queries</div>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    
    if "force_chat_prompt" not in st.session_state:
        st.session_state.force_chat_prompt = None

    if b1.button("🌍 Orders by region", use_container_width=True):
        st.session_state.force_chat_prompt = "Orders by region"
    if b2.button("📦 Inventory levels", use_container_width=True):
        st.session_state.force_chat_prompt = "Show inventory stock levels by SKU"
    if b3.button("🚚 Shipping status", use_container_width=True):
        st.session_state.force_chat_prompt = "Shipping status by region"

# --- Output area ---
with st.container(border=True):
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("preview_rows"):
                st.dataframe(msg["preview_rows"], use_container_width=True)
                row_count = len(msg["preview_rows"])
                # Dynamic insight based on actual data
                first_row = msg["preview_rows"][0] if msg["preview_rows"] else {}
                cols = ", ".join(first_row.keys()) if first_row else "N/A"
                ai_briefing(f"📊 Returned {row_count} rows from governed views. Columns: {cols}. PII masked, SELECT-only enforced.")

# --- Details ---
with st.container(border=True):
    left, right = st.columns([1.0, 1.0], gap="large")

    with left:
        st.slider("Days", 7, 90, key="chat_days")
        st.toggle("Show SQL", key="chat_show_sql")

    with right:
        if st.session_state.last_chat_policy_note:
            st.success(st.session_state.last_chat_policy_note)

        if st.session_state.chat_show_sql and st.session_state.last_chat_sql:
            st.code(st.session_state.last_chat_sql, language="sql")

        if st.session_state.audit_events:
            st.caption("Audit (latest)")
            st.table(st.session_state.audit_events[-3:])

# --- Composer ---
user_typed = st.chat_input(
    "Ask about orders, inventory, shipping, regions…",
    key="chat_input",
)

prompt = user_typed or st.session_state.force_chat_prompt

if prompt:
    st.session_state.force_chat_prompt = None 
    
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    seed = 200 + st.session_state.dashboard_refresh_count
    result = answer_chat(
        prompt,
        days=st.session_state.chat_days,
        safe_mode=st.session_state.safe_mode,
        demo_mode=st.session_state.demo_mode,
        seed=seed,
    )

    st.session_state.last_chat_sql = result.sql
    st.session_state.last_chat_policy_note = result.policy_note
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": result.assistant_text,
        "preview_rows": result.preview_rows,
    })

    # Log to audit
    st.session_state.audit_events.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "chat_query",
            "status": "allowed" if result.can_answer else "blocked",
            "note": result.policy_note,
        }
    )

    # Also write to Databricks audit log if not demo mode
    if not st.session_state.demo_mode and result.can_answer:
        try:
            from core.databricks_connect import log_query
            log_query({
                "user_role": "analyst",
                "generated_sql": result.sql,
                "status": "allowed",
            })
        except Exception:
            pass  # Don't crash if audit logging fails

    st.rerun()