import streamlit as st
from datetime import datetime, timezone

from ui.theme import apply_theme
from ui.state import init_state
from ui.chat_engine import answer_chat

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

st.title("Suggestions")
st.caption("One-click demo starters.")

TEMPLATES = [
    {
        "id": "orders",
        "title": "Order Analytics by Region",
        "dataset": "Orders (governed.orders)",
        "factory_request": (
            "Build an order analytics dashboard by region and order type. "
            "Mask regional_manager. Include filters for region and order_type. "
            "Show charts: orders by region, order types breakdown, quantity distribution."
        ),
        "chat_prompt": "Orders by region",
        "dash_region": "All",
        "dash_days": 30,
        "dash_product_lines": [],
    },
    {
        "id": "inventory",
        "title": "Inventory Risk Watch",
        "dataset": "Inventory (governed.inventory)",
        "factory_request": (
            "Create an inventory dashboard showing stock levels by SKU and region. "
            "Mask regional_manager. Include drill-down filters by region and SKU. "
            "Show charts: stock value by region, top SKUs by quantity, cost distribution."
        ),
        "chat_prompt": "Show inventory stock levels by SKU",
        "dash_region": "All",
        "dash_days": 30,
        "dash_product_lines": [],
    },
    {
        "id": "shipping",
        "title": "Shipping & Logistics Overview",
        "dataset": "Shipping (governed.shipping)",
        "factory_request": (
            "Build a shipping dashboard showing transit status by region and carrier. "
            "Mask regional_manager. Include filters for region, shipping_org, and status. "
            "Show charts: shipment count by status, in-transit value by carrier, regional breakdown."
        ),
        "chat_prompt": "Shipping status by region",
        "dash_region": "All",
        "dash_days": 30,
        "dash_product_lines": [],
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
    st.session_state.dash_product_lines = tpl.get("dash_product_lines", [])


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
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": result.assistant_text,
        "preview_rows": result.preview_rows,
    })

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
        "app_name": "Order Analytics",
        "governance": {"mask_columns": ["regional_manager"], "notes": "PII masked via Unity Catalog"},
        "dashboard": {
            "tables": ["governed.orders"],
            "charts": ["Orders by Region", "Order Types Breakdown", "Quantity Distribution"],
            "filters": ["region", "order_type"],
        },
    }
    st.session_state.last_generated_code = (
        "# Generated dashboard code for Order Analytics\n"
        "import streamlit as st\n"
        "from core.databricks_connect import execute_query\n"
        "\n"
        "st.title('Order Analytics')\n"
        "df = execute_query('SELECT region, order_type, SUM(ord_qty) as total FROM workspace.governed.orders GROUP BY region, order_type LIMIT 500')\n"
        "st.dataframe(df)\n"
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


# --- Top: never-fail button ---
with st.container(border=True):
    st.subheader("Backup demo")
    if st.button("Load Full Demo Bundle ✅", key="load_full_demo", width="stretch"):
        load_backup_full_demo()
        st.success("Full demo bundle loaded.")
        st.rerun()

# --- Templates ---
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