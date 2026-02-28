import streamlit as st
import time

from ui.theme import apply_theme
from ui.state import init_state

apply_theme()
init_state()

# Factory-only: stretch to full width
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

st.title("DataForge Factory")
st.caption("Business request → governed spec → deployed code.")

# --- Callback for the Magic Button ---
def prefill_suggestion():
    st.session_state.business_request = "Build a supply chain dashboard tracking inventory by warehouse with supplier filters. Mask the supplier contact emails."

# --- Top: Preview & Export Area ---
with st.container(border=True):
    st.subheader("Factory Output")

    if st.session_state.last_generated_spec:
        # Keep exactly ONE st.json so tests stay stable
        st.json(st.session_state.last_generated_spec)
        
        st.markdown("---")
        
        # The required Code Export UI
        c1, c2 = st.columns([2, 1])
        
        mock_code = st.session_state.get("last_generated_code") or "# (stub) Python Streamlit code\nimport streamlit as st\nst.title('Generated App')"
        
        with c1:
            with st.expander("💻 Show Generated Code"):
                st.code(mock_code, language="python")
                
        with c2:
            st.download_button(
                label="⬇️ Download Code (.py)",
                data=mock_code,
                file_name="generated_dashboard.py",
                mime="text/plain",
                use_container_width=True
            )
    else:
        st.caption("Generate a spec and your deployment-ready code will appear here.")

# --- Bottom: Input Area ---
with st.container(border=True):
    
    # The required "What Should I Build" suggestion button
    st.button("✨ What Should I Build?", on_click=prefill_suggestion, help="Click for an AI suggestion")
    
    st.text_area(
        "Business request",
        key="business_request",
        value=st.session_state.get(
            "business_request",
            "Build a sales performance dashboard by region and product line. Mask customer_email.",
        ),
        height=100,
        placeholder="Describe the dashboard. Include filters + masking needs…",
    )

    st.selectbox(
        "Dataset",
        ["Retail Sales (Demo)", "Support Tickets (Demo)", "Bank Transactions (Demo)"],
        key="selected_dataset",
    )

    clicked = st.button("Generate Dashboard", key="generate_spec", width="stretch", type="primary")

    if clicked:
        # The required Animated Factory Progress Feed
        status_placeholder = st.empty()
        
        status_placeholder.markdown(
            """
            <div class="df-card processing-card">
              <div class="df-title">DataForge Engine Active</div>
              <div class="step-text">⏳ parsing intent...</div>
            </div>
            """, unsafe_allow_html=True
        )
        time.sleep(1.0)
        
        status_placeholder.markdown(
            """
            <div class="df-card processing-card">
              <div class="df-title">DataForge Engine Active</div>
              <div class="step-text step-done">✓ parsing intent</div>
              <div class="step-text">⏳ validating governance...</div>
            </div>
            """, unsafe_allow_html=True
        )
        time.sleep(1.2)
        
        status_placeholder.markdown(
            """
            <div class="df-card processing-card">
              <div class="df-title">DataForge Engine Active</div>
              <div class="step-text step-done">✓ parsing intent</div>
              <div class="step-text step-done">✓ validating governance</div>
              <div class="step-text">⏳ generating code...</div>
            </div>
            """, unsafe_allow_html=True
        )
        time.sleep(1.2)
        
        status_placeholder.markdown(
            """
            <div class="df-card processing-card">
              <div class="df-title">DataForge Engine Active</div>
              <div class="step-text step-done">✓ parsing intent</div>
              <div class="step-text step-done">✓ validating governance</div>
              <div class="step-text step-done">✓ generating code</div>
              <div class="step-text">⏳ rendering dashboard...</div>
            </div>
            """, unsafe_allow_html=True
        )
        time.sleep(0.8)

        status_placeholder.empty()
        
        st.session_state.last_generated_spec = {
            "app_name": "Sales Performance",
            "governance": {"mask_columns": ["customer_email"]},
            "dashboard": {
                "charts": ["Revenue by Region", "Top Products", "Trend"],
                "filters": ["region", "product_line"],
            },
        }
        st.success("Spec and code generated successfully.")
        st.rerun()