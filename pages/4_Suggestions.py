"""
Page 4 — Suggestions (pages/4_Suggestions.py)

Per masterplan line 319:
  - "Analyze My Data" button
  - Calls get_schema_metadata(), passes to Agent 4 (Schema Analyzer)
  - Returns 5 suggestion cards with title, description, tables, KPIs
  - "Build This" button on each card writes factory_prompt to session state
    and navigates to Page 1

Per masterplan line 636 (demo script):
  - Click "Analyze My Data," show 5 suggestions appear from schema analysis,
    click "Build This" — factory pre-fills with the suggestion prompt
"""
from datetime import datetime, timezone
import streamlit as st

from ui.theme import apply_theme
from ui.state import init_state

apply_theme()
init_state()

# Full-width layout
st.markdown(
    """
    <style>
      .block-container{
        max-width: 100% !important;
        padding-left: clamp(18px, 4vw, 72px) !important;
        padding-right: clamp(18px, 4vw, 72px) !important;
      }
      /* Suggestion card styling */
      .suggestion-card {
        background: linear-gradient(135deg, rgba(30,41,59,0.8), rgba(15,23,42,0.9));
        border: 1px solid rgba(148,163,184,0.15);
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 12px;
        transition: transform 0.2s, border-color 0.3s;
      }
      .suggestion-card:hover {
        border-color: rgba(99,102,241,0.5);
        transform: translateY(-2px);
      }
      .suggestion-title {
        font-size: 18px;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 8px;
      }
      .suggestion-desc {
        color: #94a3b8;
        font-size: 14px;
        line-height: 1.5;
        margin-bottom: 12px;
      }
      .kpi-badge {
        display: inline-block;
        background: rgba(99,102,241,0.15);
        border: 1px solid rgba(99,102,241,0.3);
        border-radius: 6px;
        padding: 3px 10px;
        font-size: 12px;
        color: #818cf8;
        margin: 2px 4px 2px 0;
      }
      .table-badge {
        display: inline-block;
        background: rgba(16,185,129,0.12);
        border: 1px solid rgba(16,185,129,0.3);
        border-radius: 6px;
        padding: 3px 10px;
        font-size: 12px;
        color: #34d399;
        margin: 2px 4px 2px 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Suggestions")
st.caption("AI-powered schema analysis — discover what dashboards your data can power")


# ── Session state for suggestions ─────────────────────────────────────
if "schema_suggestions" not in st.session_state:
    st.session_state.schema_suggestions = []
if "suggestions_loading" not in st.session_state:
    st.session_state.suggestions_loading = False
if "suggestions_error" not in st.session_state:
    st.session_state.suggestions_error = None


# ── "Analyze My Data" button ──────────────────────────────────────────
with st.container(border=True):
    st.markdown(
        "### 🔬 Schema Analysis\n"
        "Click below to analyze your governed data tables and get AI-powered "
        "suggestions for dashboards you can build instantly."
    )

    col_btn, col_status = st.columns([1, 2])
    with col_btn:
        analyze_clicked = st.button(
            "🔍 Analyze My Data",
            key="analyze_schema_btn",
            type="primary",
            use_container_width=True,
        )

    if analyze_clicked:
        with st.spinner("🧠 Agent 4 analyzing your schema..."):
            try:
                from agents.schema_analyzer import analyze_schema, FALLBACK_SUGGESTIONS
                result = analyze_schema()

                if result["success"] and result["suggestions"]:
                    st.session_state.schema_suggestions = result["suggestions"]
                    st.session_state.suggestions_error = None
                else:
                    # Use fallback suggestions if LLM fails
                    st.session_state.schema_suggestions = FALLBACK_SUGGESTIONS
                    st.session_state.suggestions_error = (
                        f"⚠️ Live analysis unavailable ({result.get('error', 'unknown')}). "
                        "Showing curated suggestions."
                    )
            except Exception as e:
                # Absolute last resort — hardcoded suggestions
                from agents.schema_analyzer import FALLBACK_SUGGESTIONS
                st.session_state.schema_suggestions = FALLBACK_SUGGESTIONS
                st.session_state.suggestions_error = (
                    f"⚠️ Agent 4 error ({e}). Showing curated suggestions."
                )

            # Log the event
            st.session_state.audit_events.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "schema_analysis",
                "source": "agent4",
                "status": "success" if not st.session_state.suggestions_error else "fallback",
                "note": f"{len(st.session_state.schema_suggestions)} suggestions generated",
            })

            st.rerun()

    # Show status
    with col_status:
        if st.session_state.suggestions_error:
            st.warning(st.session_state.suggestions_error)
        elif st.session_state.schema_suggestions:
            st.success(f"✅ {len(st.session_state.schema_suggestions)} suggestions ready")


# ── Suggestion Cards ──────────────────────────────────────────────────
if st.session_state.schema_suggestions:
    st.markdown("---")
    st.markdown("### 💡 Recommended Dashboards")
    st.caption("Each suggestion is tailored to your governed data. Click **Build This** to create it instantly.")

    for idx, suggestion in enumerate(st.session_state.schema_suggestions):
        with st.container(border=True):
            # Title
            st.markdown(
                f"<div class='suggestion-title'>📊 {suggestion['title']}</div>",
                unsafe_allow_html=True,
            )

            # Description
            st.markdown(
                f"<div class='suggestion-desc'>{suggestion['description']}</div>",
                unsafe_allow_html=True,
            )

            # Tables badges
            tables_html = "".join(
                f"<span class='table-badge'>📁 {t}</span>" for t in suggestion.get("tables", [])
            )
            if tables_html:
                st.markdown(f"**Tables:** {tables_html}", unsafe_allow_html=True)

            # KPI badges
            kpis_html = "".join(
                f"<span class='kpi-badge'>📈 {k}</span>" for k in suggestion.get("kpis", [])
            )
            if kpis_html:
                st.markdown(f"**KPIs:** {kpis_html}", unsafe_allow_html=True)

            # Factory prompt preview
            with st.expander("🔍 View Factory Prompt"):
                st.code(suggestion.get("factory_prompt", ""), language="text")

            # "Build This" button — writes factory_prompt to session state and navigates to Page 1
            if st.button(
                "🏭 Build This",
                key=f"build_suggestion_{idx}",
                type="primary",
                use_container_width=True,
            ):
                # Write the factory_prompt to session state
                st.session_state.business_request = suggestion["factory_prompt"]
                # Log the event
                st.session_state.audit_events.append({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event": "suggestion_selected",
                    "source": "agent4",
                    "status": "success",
                    "note": f"Selected: {suggestion['title']}",
                })
                # Navigate to Factory (Page 1)
                st.switch_page("pages/1_Factory.py")

else:
    # Show empty state with instructions
    st.markdown("---")
    st.info(
        "👆 Click **Analyze My Data** above to get AI-powered suggestions "
        "based on your governed data schema."
    )

# ── Policy footer ─────────────────────────────────────────────────────
with st.container(border=True):
    st.success(
        "🛡️ All suggestions respect governance: SELECT-only • masked PII • governed views only"
    )