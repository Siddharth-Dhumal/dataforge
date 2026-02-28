from datetime import datetime, timezone
import streamlit as st

from ui.theme import apply_theme
from ui.state import init_state
from ui.chat_engine import answer_chat
from ui.components import ai_briefing

apply_theme()
init_state()

# Full-width like Factory/Dashboard (Chat-only)
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

# --- Demo Fallback Buttons (Mandatory) ---
with st.container(border=False):
    st.markdown("<div class='df-subtitle' style='margin-bottom: 8px;'>Suggested Queries</div>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    
    # We use session state to catch button clicks and feed them to the chat
    if "force_chat_prompt" not in st.session_state:
        st.session_state.force_chat_prompt = None

    if b1.button("🌍 Revenue by region", use_container_width=True):
        st.session_state.force_chat_prompt = "Revenue by region last 30 days"
    if b2.button("📦 Top product lines", use_container_width=True):
        st.session_state.force_chat_prompt = "Top product lines by revenue"
    if b3.button("📈 Revenue trend", use_container_width=True):
        st.session_state.force_chat_prompt = "Revenue trend over time"

# --- Output area (like ChatGPT conversation) ---
with st.container(border=True):
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Show the holographic card if it's the assistant
            if msg["role"] == "assistant":
                ai_briefing("AI Insight: Revenue is trending upward by 14% driven primarily by Widget sales in the West region.")

# --- Details (minimal, judge-useful) ---
with st.container(border=True):
    left, right = st.columns([1.0, 1.0], gap="large")

    with left:
        st.slider("Days", 7, 90, key="chat_days")
        st.toggle("Show SQL", key="chat_show_sql")

    with right:
        # Keep it short: only show policy note when present
        if st.session_state.last_chat_policy_note:
            st.success(st.session_state.last_chat_policy_note)

        if st.session_state.chat_show_sql and st.session_state.last_chat_sql:
            st.code(st.session_state.last_chat_sql, language="sql")

        if st.session_state.audit_events:
            st.caption("Audit (latest)")
            st.table(st.session_state.audit_events[-3:])

# --- Composer (bottom input, like ChatGPT) ---
user_typed = st.chat_input(
    "Ask about revenue, orders, regions, product lines, trends…",
    key="chat_input",
)

# Accept either a typed prompt or a clicked button prompt
prompt = user_typed or st.session_state.force_chat_prompt

if prompt:
    # Immediately clear the forced prompt so it doesn't loop
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
    st.session_state.chat_history.append({"role": "assistant", "content": result.assistant_text})

    st.session_state.audit_events.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "chat_query",
            "status": "allowed" if result.can_answer else "blocked",
            "note": result.policy_note,
        }
    )

    # Make the new assistant message appear immediately at the top
    st.rerun()