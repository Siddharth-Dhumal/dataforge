import streamlit as st
import time
from datetime import datetime, timezone

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
    st.session_state.business_request = "Build an inventory dashboard showing stock levels by SKU and region. Mask regional_manager. Add filters for region and SKU."

# --- Top: Preview & Export Area ---
with st.container(border=True):
    st.subheader("Factory Output")

    if st.session_state.last_generated_spec:
        st.json(st.session_state.last_generated_spec)
        
        st.markdown("---")
        
        c1, c2 = st.columns([2, 1])
        
        gen_code = st.session_state.get("last_generated_code") or "# (stub) Python Streamlit code\nimport streamlit as st\nst.title('Generated App')"
        
        with c1:
            with st.expander("💻 Show Generated Code"):
                st.code(gen_code, language="python")
                
        with c2:
            st.download_button(
                label="⬇️ Download Code (.py)",
                data=gen_code,
                file_name="generated_dashboard.py",
                mime="text/plain",
                use_container_width=True
            )
    else:
        st.caption("Generate a spec and your deployment-ready code will appear here.")

# --- Bottom: Input Area ---
with st.container(border=True):
    
    st.button("✨ What Should I Build?", on_click=prefill_suggestion, help="Click for an AI suggestion")
    
    st.text_area(
        "Business request",
        key="business_request",
        value=st.session_state.get(
            "business_request",
            "Build an order analytics dashboard by region and order type. Mask regional_manager.",
        ),
        height=100,
        placeholder="Describe the dashboard. Include filters + masking needs…",
    )

    st.selectbox(
        "Dataset",
        ["Orders (governed.orders)", "Inventory (governed.inventory)", "Shipping (governed.shipping)"],
        key="selected_dataset",
    )

    clicked = st.button("Generate Dashboard", key="generate_spec", width="stretch", type="primary")

    if clicked:
        # Animated Factory Progress Feed
        status_placeholder = st.empty()
        
        # Animated progress
        status_placeholder.markdown(
            """
            <div class="df-card processing-card">
              <div class="df-title">DataForge Engine Active</div>
              <div class="step-text">⏳ parsing intent via Claude...</div>
            </div>
            """, unsafe_allow_html=True
        )

        # Call the real factory pipeline
        from factory.factory import run_factory_pipeline
        user_desc = st.session_state.business_request
        user_role = "analyst"
        
        try:
            success, msg, spec, code = run_factory_pipeline(user_desc, user_role)
        except Exception as e:
            success = False
            msg = str(e)
            spec = {}
            code = ""

        # Show completion
        status_placeholder.markdown(
            """
            <div class="df-card processing-card">
              <div class="df-title">DataForge Engine Active</div>
              <div class="step-text step-done">✓ parsing intent</div>
              <div class="step-text step-done">✓ validating governance</div>
              <div class="step-text step-done">✓ generating code</div>
              <div class="step-text step-done">✓ rendering dashboard</div>
            </div>
            """, unsafe_allow_html=True
        )
        time.sleep(0.5)
        status_placeholder.empty()

        if success and spec:
            # Add governance info to the spec for display
            spec["governance"] = {
                "mask_columns": spec.get("mask_columns", ["regional_manager"]),
                "pii_policy": "regional_manager masked via Unity Catalog",
                "query_mode": "SELECT-only, LIMIT enforced",
            }
            
            st.session_state.last_generated_spec = spec
            st.session_state.last_generated_code = code or "# Code generation completed"
            
            st.session_state.audit_events.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "factory_generate",
                "status": "allowed",
                "note": f"Generated spec: {spec.get('app_name', spec.get('domain', 'Unnamed'))} | source: {spec.get('source', 'unknown')}",
            })
            
            st.success(f"✅ {msg}")
        else:
            st.error(f"❌ Pipeline failed: {msg}")
        
        st.rerun()