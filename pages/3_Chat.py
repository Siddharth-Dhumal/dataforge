"""
Page 3 — Chat (pages/3_Chat.py)

Full conversational interface per the masterplan:
  - Message history in st.session_state
  - Three pre-wired "example question" buttons at top (demo fallback)
  - Each answer: plain English text + Plotly chart + "Show SQL" expander + AI Briefing card
  - "Query auto-corrected" badge if self-healing fired, with link to diff in admin console
  - Chat uses Genie API primarily, falls back to Agent 1 if Genie unavailable
"""
from datetime import datetime, timezone
import streamlit as st
import plotly.express as px
import pandas as pd

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
      /* Style the auto-corrected badge */
      .heal-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(234, 179, 8, 0.15);
        border: 1px solid rgba(234, 179, 8, 0.4);
        border-radius: 8px;
        padding: 4px 12px;
        font-size: 13px;
        color: #eab308;
        margin-top: 8px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Chat")
st.caption("Governed Q&A — Genie API + AI agents (SELECT-only • LIMIT • masked PII)")

# --- Suggested Queries (always work as demo fallback) ---
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

# --- Chat History ---
with st.container(border=True):
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant" and msg.get("preview_rows"):
                rows = msg["preview_rows"]
                df = pd.DataFrame(rows)

                # ── Plotly chart (masterplan: each answer has a Plotly chart) ──
                if not df.empty and len(df.columns) >= 2:
                    # Detect numeric columns for charting
                    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
                    str_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

                    if num_cols and str_cols:
                        # Bar chart: first string col as x, first numeric col as y
                        x_col = str_cols[0]
                        y_col = num_cols[0]
                        color_col = str_cols[1] if len(str_cols) > 1 else None

                        fig = px.bar(
                            df,
                            x=x_col,
                            y=y_col,
                            color=color_col,
                            title=f"{y_col} by {x_col}",
                            template="plotly_dark",
                            color_discrete_sequence=px.colors.qualitative.Set2,
                        )
                        fig.update_layout(
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font_color="#e2e8f0",
                            margin=dict(l=20, r=20, t=40, b=20),
                            height=350,
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"chart_{id(msg)}")
                    elif num_cols:
                        # Numeric-only: show a simple bar of values
                        fig = px.bar(
                            df,
                            y=num_cols[0],
                            title=f"{num_cols[0]} values",
                            template="plotly_dark",
                        )
                        fig.update_layout(
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font_color="#e2e8f0",
                            margin=dict(l=20, r=20, t=40, b=20),
                            height=300,
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"chart_{id(msg)}")

                # ── Data table ──
                st.dataframe(df, use_container_width=True, height=250)

                # ── "Query auto-corrected" badge (stretch goal per masterplan) ──
                if msg.get("healed"):
                    st.markdown(
                        '<div class="heal-badge">🩹 Query auto-corrected by self-healing agent — '
                        'see diff in IT Admin Console</div>',
                        unsafe_allow_html=True,
                    )

                # ── "Show SQL" expander (masterplan: per-message expander) ──
                if msg.get("sql"):
                    with st.expander("🔍 Show SQL"):
                        st.code(msg["sql"], language="sql")

                    # Show diff if self-healed
                    if msg.get("heal_diff"):
                        with st.expander("🩹 Self-Heal Diff"):
                            st.code(msg["heal_diff"], language="diff")

                # ── AI Briefing card (masterplan: Agent 3 insight) ──
                insight = msg.get("insight", "")
                if insight:
                    ai_briefing(f"🧠 {insight}")
                else:
                    row_count = len(rows)
                    first_row = rows[0] if rows else {}
                    cols = ", ".join(first_row.keys()) if first_row else "N/A"
                    ai_briefing(
                        f"📊 Returned {row_count} rows from governed views. "
                        f"Columns: {cols}. PII masked, SELECT-only enforced."
                    )

# --- Policy & Source Info ---
with st.container(border=True):
    left, right = st.columns([1.0, 1.0], gap="large")

    with left:
        st.slider("Days", 7, 90, key="chat_days")

    with right:
        if st.session_state.last_chat_policy_note:
            st.success(st.session_state.last_chat_policy_note)

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
        "insight": result.insight,
        "sql": result.sql,
        "healed": result.healed,
        "heal_diff": result.heal_diff,
    })

    # Log to session audit
    st.session_state.audit_events.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "chat_query",
            "source": result.source,
            "status": "success" if result.can_answer else ("healed" if result.healed else "failed"),
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
                "status": "success" if not result.healed else "healed",
            })
        except Exception:
            pass  # Don't crash if audit logging fails

    st.rerun()