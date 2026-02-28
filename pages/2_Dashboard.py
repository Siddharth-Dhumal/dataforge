import os
import streamlit as st
import plotly.express as px
from ui.theme import apply_theme
from ui.state import init_state
from ui.demo_data import PRODUCT_LINES, REGIONS, build_sales_rows, try_pandas_frame

apply_theme()
init_state()

TEST_MODE = os.getenv("DATAFORGE_TEST_MODE") == "1"

# Full-width like Factory (Dashboard-only)
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
st.caption("Filters • refresh • 3–5 visuals")

# --- Sidebar: Governance & Role Scoping ---
with st.sidebar:
    # Custom Security Badge CSS
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
    
    # The required role selector for the demo
    simulated_role = st.radio(
        "Simulate User Identity:",
        ["All Regions (Admin)", "West Only (Regional Analyst)", "East Only (Regional Analyst)"],
        key="role_simulation"
    )
    
    st.markdown("---")
    st.caption("Enforced via Unity Catalog parameterized governed views.")
    
    # Map the selected role to the session state region to mock the database filtering
    if "West" in simulated_role:
        st.session_state.dash_region = "West"
    elif "East" in simulated_role:
        st.session_state.dash_region = "East"
    else:
        st.session_state.dash_region = "All"

# --- Filter bar (single row) ---
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([1.0, 1.6, 1.1, 0.8], gap="medium")

    with c2:
        st.multiselect("Product Lines", PRODUCT_LINES, key="dash_product_lines")

    with c3:
        st.slider("Days", 7, 90, step=1, key="dash_days")

    with c4:
        st.write("")
        if st.button("Refresh", key="refresh_dashboard", width="stretch"):
            st.session_state.dashboard_refresh_count += 1
            st.rerun()

# --- Data generation (deterministic; seed changes after refresh) ---
seed = 100 + st.session_state.dashboard_refresh_count
rows = build_sales_rows(days=st.session_state.dash_days, seed=seed)

region = st.session_state.dash_region
pls = st.session_state.dash_product_lines

filtered = []
for r in rows:
    if region != "All" and r["region"] != region:
        continue
    if pls and r["product_line"] not in pls:
        continue
    filtered.append(r)

max_rows = 250 if st.session_state.safe_mode else 2000
filtered_view = filtered[:max_rows]

# --- KPIs (top summary) ---
total_revenue = round(sum(x["revenue"] for x in filtered), 2)
total_orders = int(sum(x["orders"] for x in filtered))
total_customers = int(sum(x["customers"] for x in filtered))

k1, k2, k3 = st.columns(3, gap="large")
k1.metric("Revenue", f"{total_revenue:,.2f}")
k2.metric("Orders", f"{total_orders:,}")
k3.metric("Customers", f"{total_customers:,}")

# --- Visualizations (minimal section) ---
with st.container(border=True):
    if TEST_MODE:
        st.caption("Charts skipped in test mode.")
    else:
        # 1. Define the DataFrame first!
        df = try_pandas_frame(filtered)
        
        # 2. Add the safety check back
        if df is None:
            st.warning("Pandas not available; showing table only.", icon="⚠️")
        else:
            # --- Shared Plotly Theme Settings ---
            # This makes the charts transparent so your animated CSS background shows through
            layout_opts = dict(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f8fafc", family="sans-serif"),
                margin=dict(l=20, r=20, t=40, b=20),
                hoverlabel=dict(bgcolor="rgba(15, 23, 42, 0.9)", font_size=14, font_family="monospace"),
                xaxis=dict(showgrid=False, zeroline=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False),
            )

            st.subheader("Revenue trend")
            ts = df.groupby("date", as_index=False)["revenue"].sum()
            # The required Line Chart
            fig_line = px.line(
                ts, x="date", y="revenue", 
                color_discrete_sequence=["#38bdf8"] # Neon blue accent
            )
            fig_line.update_traces(line=dict(width=3))
            fig_line.update_layout(**layout_opts, title="Daily Revenue")
            st.plotly_chart(fig_line, use_container_width=True)

            v1, v2 = st.columns(2, gap="large")
            with v1:
                st.subheader("By region")
                by_region = df.groupby("region", as_index=False)["revenue"].sum()
                # The required Bar Chart
                fig_bar = px.bar(
                    by_region, x="region", y="revenue",
                    color="region", 
                    color_discrete_sequence=["#38bdf8", "#818cf8", "#c084fc"] # Deep cyber purples/blues
                )
                fig_bar.update_layout(**layout_opts, title="Revenue by Region", showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with v2:
                st.subheader("Correlation")
                # The required Scatter/Heatmap
                # Grouping to show correlation between Orders and Revenue by Product Line
                scatter_df = df.groupby("product_line", as_index=False).agg({"revenue": "sum", "orders": "sum"})
                fig_scatter = px.scatter(
                    scatter_df, x="orders", y="revenue", size="revenue", color="product_line",
                    color_discrete_sequence=["#10b981", "#f43f5e", "#f59e0b"]
                )
                fig_scatter.update_layout(**layout_opts, title="Orders vs Revenue")
                st.plotly_chart(fig_scatter, use_container_width=True)

# --- Data table + code preview (minimal, optional) ---
with st.container(border=True):
    left, right = st.columns([1.3, 0.9], gap="large")

    with left:
        st.toggle("Show table", key="dash_show_table")
        if st.session_state.dash_show_table:
            st.dataframe(filtered_view, width="stretch")

    with right:
        if st.session_state.show_code:
            code_text = st.session_state.last_generated_code or "# (stub) generated dashboard code will appear here"
            st.code(code_text, language="python")
        else:
            st.caption("Enable **Show Generated Code** in the sidebar.")