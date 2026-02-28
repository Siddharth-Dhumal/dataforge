import os
from decimal import Decimal
from pathlib import Path

import streamlit as st
import plotly.express as px
import pandas as pd

from ui.theme import apply_theme
from ui.state import init_state

apply_theme()
init_state()

TEST_MODE = os.getenv("DATAFORGE_TEST_MODE") == "1"

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

st.title("Dashboard")
st.caption("Live governed data • role-scoped • Databricks")


# ── Databricks helper (same pattern as chat_engine.py) ──────────────
def _ensure_env():
    if not os.environ.get("DATABRICKS_HOST"):
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


def _clean(v):
    return float(v) if isinstance(v, Decimal) else v


def run_query(sql: str) -> pd.DataFrame:
    """Run SQL directly against Databricks, return a DataFrame."""
    _ensure_env()
    host = os.environ.get("DATABRICKS_HOST", "")
    http_path = os.environ.get("DATABRICKS_HTTP_PATH", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if not all([host, http_path, token]):
        return pd.DataFrame({"error": ["Missing Databricks credentials"]})
    try:
        from utils.query_validator import validate_query
        validated = validate_query(sql)
    except Exception as e:
        return pd.DataFrame({"error": [f"Validation: {e}"]})
    try:
        from databricks import sql as dbsql
        conn = dbsql.connect(server_hostname=host, http_path=http_path, access_token=token)
        cur = conn.cursor()
        cur.execute(validated)
        if not cur.description:
            cur.close(); conn.close()
            return pd.DataFrame()
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        cur.close(); conn.close()
        df = pd.DataFrame([{c: _clean(v) for c, v in zip(cols, row)} for row in rows], columns=cols)
        return df
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})


# ── Sidebar: Role Scoping ───────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div class="df-card" style="padding: 14px; margin-bottom: 20px; border-left: 4px solid #10b981; background: rgba(16, 185, 129, 0.05);">
          <div style="font-size: 11px; font-weight: bold; letter-spacing: 1.2px; color: #10b981; text-transform: uppercase; margin-bottom: 4px;">
            🛡️ Active Security Policy
          </div>
          <div class="df-title" style="font-size: 18px;">Data Scope</div>
        </div>
        """, unsafe_allow_html=True
    )
    simulated_role = st.radio(
        "Simulate User Identity:",
        ["All Regions (Admin)", "West Only (Regional Analyst)", "East Only (Regional Analyst)"],
        key="role_simulation",
    )
    st.markdown("---")
    st.caption("Enforced via Unity Catalog parameterized governed views.")

    if "West" in simulated_role:
        st.session_state.dash_region = "West"
    elif "East" in simulated_role:
        st.session_state.dash_region = "East"
    else:
        st.session_state.dash_region = "All"

region = st.session_state.dash_region
where = f"WHERE region = '{region}'" if region != "All" else ""


# ── Filter bar ──────────────────────────────────────────────────────
with st.container(border=True):
    c1, c2, c3 = st.columns([1.0, 1.6, 0.8], gap="medium")
    with c1:
        st.selectbox("Table focus", ["All Tables", "Orders", "Inventory", "Shipping"], key="dash_table_focus")
    with c2:
        st.slider("Row limit", 10, 500, value=50, step=10, key="dash_row_limit")
    with c3:
        st.write("")
        if st.button("Refresh", key="refresh_dashboard", width="stretch"):
            st.session_state.dashboard_refresh_count += 1
            st.rerun()

limit = st.session_state.dash_row_limit
focus = st.session_state.dash_table_focus


# ── KPIs from real data ─────────────────────────────────────────────
with st.spinner("Querying Databricks for KPIs..."):
    kpi_orders = run_query(f"SELECT COUNT(order_nbr) AS cnt, SUM(ord_qty) AS qty FROM workspace.governed.orders {where} LIMIT 1")
    kpi_inventory = run_query(f"SELECT COUNT(sku) AS sku_count, SUM(qoh) AS total_stock, SUM(qoh_cost) AS total_value FROM workspace.governed.inventory {where} LIMIT 1")
    kpi_shipping = run_query(f"SELECT COUNT(sku) AS shipments, SUM(intransit_value) AS transit_val FROM workspace.governed.shipping {where} LIMIT 1")

k1, k2, k3, k4, k5 = st.columns(5, gap="medium")

if "error" not in kpi_orders.columns and not kpi_orders.empty:
    k1.metric("Orders", f"{int(kpi_orders['cnt'].iloc[0]):,}")
    k2.metric("Total Qty", f"{int(kpi_orders['qty'].iloc[0]):,}")
else:
    k1.metric("Orders", "—")
    k2.metric("Total Qty", "—")

if "error" not in kpi_inventory.columns and not kpi_inventory.empty:
    k3.metric("SKUs", f"{int(kpi_inventory['sku_count'].iloc[0]):,}")
    val = kpi_inventory['total_value'].iloc[0]
    k4.metric("Inventory $", f"${val/1e6:,.1f}M" if val > 1e6 else f"${val:,.0f}")
else:
    k3.metric("SKUs", "—")
    k4.metric("Inventory $", "—")

if "error" not in kpi_shipping.columns and not kpi_shipping.empty:
    transit = kpi_shipping['transit_val'].iloc[0]
    k5.metric("In Transit $", f"${transit/1e6:,.1f}M" if transit > 1e6 else f"${transit:,.0f}")
else:
    k5.metric("In Transit $", "—")


# ── Shared Plotly theme ─────────────────────────────────────────────
layout_opts = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#f8fafc", family="sans-serif"),
    margin=dict(l=20, r=20, t=40, b=20),
    hoverlabel=dict(bgcolor="rgba(15, 23, 42, 0.9)", font_size=14, font_family="monospace"),
    xaxis=dict(showgrid=False, zeroline=False),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False),
)


# ── Charts from real data ───────────────────────────────────────────
if not TEST_MODE:
    with st.container(border=True):
        # Orders by region (bar chart)
        if focus in ["All Tables", "Orders"]:
            st.subheader("📊 Orders by Region & Type")
            orders_df = run_query(
                f"SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty "
                f"FROM workspace.governed.orders {where} "
                f"GROUP BY region, order_type ORDER BY total_qty DESC LIMIT {limit}"
            )
            if "error" not in orders_df.columns and not orders_df.empty:
                v1, v2 = st.columns(2, gap="large")
                with v1:
                    bar_df = orders_df.groupby("region", as_index=False)["total_qty"].sum()
                    fig_bar = px.bar(
                        bar_df, x="region", y="total_qty", color="region",
                        color_discrete_sequence=["#38bdf8", "#818cf8", "#c084fc", "#f472b6", "#10b981"],
                    )
                    fig_bar.update_layout(**layout_opts, title="Qty by Region", showlegend=False)
                    st.plotly_chart(fig_bar, use_container_width=True)
                with v2:
                    type_df = orders_df.groupby("order_type", as_index=False)["order_count"].sum()
                    fig_pie = px.pie(
                        type_df, values="order_count", names="order_type",
                        color_discrete_sequence=["#38bdf8", "#818cf8", "#c084fc", "#f472b6", "#10b981"],
                    )
                    fig_pie.update_layout(**layout_opts, title="Order Types Breakdown")
                    st.plotly_chart(fig_pie, use_container_width=True)
                with st.expander("View raw data"):
                    st.dataframe(orders_df, use_container_width=True)
            else:
                err = orders_df['error'].iloc[0] if 'error' in orders_df.columns else "Empty result"
                st.warning(f"Orders query: {err}")

    with st.container(border=True):
        # Inventory (bar + scatter)
        if focus in ["All Tables", "Inventory"]:
            st.subheader("📦 Inventory by SKU & Region")
            inv_df = run_query(
                f"SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost "
                f"FROM workspace.governed.inventory {where} "
                f"GROUP BY sku, sku_description, region ORDER BY total_cost DESC LIMIT {limit}"
            )
            if "error" not in inv_df.columns and not inv_df.empty:
                v1, v2 = st.columns(2, gap="large")
                with v1:
                    region_inv = inv_df.groupby("region", as_index=False)["total_cost"].sum()
                    fig_inv = px.bar(
                        region_inv, x="region", y="total_cost", color="region",
                        color_discrete_sequence=["#10b981", "#f59e0b", "#f43f5e", "#818cf8"],
                    )
                    fig_inv.update_layout(**layout_opts, title="Inventory Value by Region", showlegend=False)
                    st.plotly_chart(fig_inv, use_container_width=True)
                with v2:
                    fig_scatter = px.scatter(
                        inv_df.head(30), x="total_qty", y="total_cost", size="total_cost",
                        color="region", hover_data=["sku_description"],
                        color_discrete_sequence=["#10b981", "#f59e0b", "#f43f5e"],
                    )
                    fig_scatter.update_layout(**layout_opts, title="Qty vs Cost (top 30 SKUs)")
                    st.plotly_chart(fig_scatter, use_container_width=True)
                with st.expander("View raw data"):
                    st.dataframe(inv_df, use_container_width=True)
            else:
                err = inv_df['error'].iloc[0] if 'error' in inv_df.columns else "Empty result"
                st.warning(f"Inventory query: {err}")

    with st.container(border=True):
        # Shipping (bar + pie)
        if focus in ["All Tables", "Shipping"]:
            st.subheader("🚚 Shipping & Transit")
            ship_df = run_query(
                f"SELECT region, shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value "
                f"FROM workspace.governed.shipping {where} "
                f"GROUP BY region, shipping_org, wms_shipment_status ORDER BY total_value DESC LIMIT {limit}"
            )
            if "error" not in ship_df.columns and not ship_df.empty:
                v1, v2 = st.columns(2, gap="large")
                with v1:
                    status_df = ship_df.groupby("wms_shipment_status", as_index=False)["shipment_count"].sum()
                    fig_status = px.pie(
                        status_df, values="shipment_count", names="wms_shipment_status",
                        color_discrete_sequence=["#38bdf8", "#f59e0b", "#f43f5e", "#10b981"],
                    )
                    fig_status.update_layout(**layout_opts, title="Shipments by Status")
                    st.plotly_chart(fig_status, use_container_width=True)
                with v2:
                    carrier_df = ship_df.groupby("shipping_org", as_index=False)["total_value"].sum().sort_values("total_value", ascending=False).head(10)
                    fig_carrier = px.bar(
                        carrier_df, x="shipping_org", y="total_value", color="shipping_org",
                        color_discrete_sequence=["#818cf8", "#c084fc", "#f472b6", "#38bdf8", "#10b981"],
                    )
                    fig_carrier.update_layout(**layout_opts, title="Transit Value by Carrier (Top 10)", showlegend=False)
                    st.plotly_chart(fig_carrier, use_container_width=True)
                with st.expander("View raw data"):
                    st.dataframe(ship_df, use_container_width=True)
            else:
                err = ship_df['error'].iloc[0] if 'error' in ship_df.columns else "Empty result"
                st.warning(f"Shipping query: {err}")


# ── Bottom: code preview ────────────────────────────────────────────
with st.container(border=True):
    if st.session_state.show_code:
        code_text = st.session_state.last_generated_code or "# Generate a dashboard in the Factory page first"
        st.code(code_text, language="python")
    else:
        st.caption("Enable **Show Generated Code** in the sidebar.")