import streamlit as st
from datetime import datetime, timezone

from ui.theme import apply_theme
from ui.state import init_state
from ui.chat_engine import answer_chat

apply_theme()
init_state()

# Full-width like other pages
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

st.title("Suggestions")
st.caption("One-click demo starters.")

TEMPLATES = [
    {
        "id": "sales",
        "title": "Retail Sales Performance",
        "dataset": "Retail Sales (Demo)",
        "factory_request": (
            "Build a sales performance dashboard by region and product line for the last 30 days. "
            "Mask customer_email. Let managers filter by region and product_line. "
            "Show 3–5 visuals: revenue trend, revenue by region, revenue by product line."
        ),
        "chat_prompt": "Revenue by region last 30 days",
        "dash_region": "All",
        "dash_days": 30,
        "dash_product_lines": ["Widgets", "Gadgets", "Services"],
    },
    {
        "id": "inventory",
        "title": "Inventory Risk Watch",
        "dataset": "Retail Sales (Demo)",
        "factory_request": (
            "Create an inventory risk dashboard for the last 30 days. "
            "Highlight regions and product lines with unusual changes in orders and revenue. "
            "Mask customer_email. Include drill-down filters by region and product_line."
        ),
        "chat_prompt": "Top product lines by revenue last 30 days",
        "dash_region": "All",
        "dash_days": 30,
        "dash_product_lines": ["Widgets", "Gadgets", "Services"],
    },
    {
        "id": "support",
        "title": "Support Tickets Overview",
        "dataset": "Support Tickets (Demo)",
        "factory_request": (
            "Build a support overview dashboard for the last 30 days. "
            "Show trends and breakdowns by category and region. "
            "Do not display PII; keep results aggregated."
        ),
        "chat_prompt": "Revenue trend over time last 30 days",
        "dash_region": "All",
        "dash_days": 30,
        "dash_product_lines": ["Widgets", "Gadgets", "Services"],
    },
]


def load_template_into_factory(tpl: dict) -> None:
    st.session_state.business_request = tpl["factory_request"]
    st.session_state.selected_dataset = tpl["dataset"]
    st.session_state.last_generated_spec = None
    st.session_state.last_generated_code = None


def apply_template_to_dashboard_filters(tpl: dict) -> None:
    st.session_state.dash_region = tpl["dash_region"]
    st.session_state.dash_days = tpl["dash_days"]
    st.session_state.dash_product_lines = tpl["dash_product_lines"]


def run_chat_demo(tpl: dict) -> None:
    prompt = tpl["chat_prompt"]
    st.session_state.suggested_chat_prompt = prompt

    st.session_state.chat_history.append({"role": "user", "content": prompt})

    seed = 300 + st.session_state.dashboard_refresh_count
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


def load_backup_full_demo() -> None:
    tpl = TEMPLATES[0]

    load_template_into_factory(tpl)
    apply_template_to_dashboard_filters(tpl)

    st.session_state.last_generated_spec = {
        "app_name": "Sales Performance",
        "governance": {"mask_columns": ["customer_email"], "notes": "demo masking"},
        "dashboard": {
            "charts": ["Revenue trend", "Revenue by region", "Revenue by product line"],
            "filters": ["region", "product_line"],
        },
    }
    st.session_state.last_generated_code = (
        "# (demo) generated dashboard code\n"
        "def build_dashboard():\n"
        "    # governed views only, select-only, limit enforced\n"
        "    pass\n"
    )

    st.session_state.chat_history = []
    run_chat_demo(tpl)

    st.session_state.audit_events.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "factory_generate",
            "status": "allowed",
            "note": "Generated spec + code (demo bundle).",
        }
    )

    st.session_state.demo_bundle_loaded = True


# --- Top: never-fail button (single, prominent) ---
with st.container(border=True):
    st.subheader("Backup demo")
    if st.button("Load Full Demo Bundle ✅", key="load_full_demo", width="stretch"):
        load_backup_full_demo()
        st.success("Full demo bundle loaded.")
        st.rerun()

# --- Templates (stacked, minimal) ---
for tpl in TEMPLATES:
    with st.container(border=True):
        st.subheader(tpl["title"])
        st.caption(tpl["dataset"])
        st.write(tpl["factory_request"])

        b1, b2, b3 = st.columns([1.0, 1.0, 1.2], gap="small")
        with b1:
            if st.button("Load Factory", key=f"tpl_factory_{tpl['id']}", width="stretch"):
                load_template_into_factory(tpl)
                st.success("Loaded.")
                st.rerun()
        with b2:
            if st.button("Set Dashboard", key=f"tpl_dash_{tpl['id']}", width="stretch"):
                apply_template_to_dashboard_filters(tpl)
                st.success("Set.")
                st.rerun()
        with b3:
            if st.button("Run Chat", key=f"tpl_chat_{tpl['id']}", width="stretch"):
                run_chat_demo(tpl)
                st.success("Generated.")
                st.rerun()