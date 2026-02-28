import streamlit as st
from typing import Dict, Any

def render_dynamic_app(spec: Dict[str, Any], generated_code: str):
    """
    Saves the spec and generated code into session_state.
    Page 1 will read these to display the dashboard inline and show the code expander.
    """
    st.session_state["current_app_spec"] = spec
    st.session_state["current_app_code"] = generated_code
    
    return True
