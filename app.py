import streamlit as st
import random
from ui.theme import apply_theme
from ui.state import init_state

st.set_page_config(
    page_title="DataForge",
    page_icon="⚒️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_theme()
init_state()

# Full-width like other pages + centered hero
st.markdown(
    """
    <style>
      .block-container{
        max-width: 100% !important;
        padding-left: clamp(18px, 4vw, 72px) !important;
        padding-right: clamp(18px, 4vw, 72px) !important;
      }

      /* Center hero area */
      .df-hero {
        height: calc(100vh - 240px);
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
      }

      .df-logo {
        font-size: 64px;
        line-height: 1;
        margin-bottom: 12px;
      }

      .df-name {
        font-size: 44px;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin: 0;
      }

      .df-tag {
        margin-top: 10px;
        color: rgba(226, 232, 240, 0.70);
        font-size: 16px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar controls (team plan + keep keys stable)
with st.sidebar:
    st.subheader("Controls")
    st.toggle("Demo Mode", key="demo_mode")
    st.toggle("Show Generated Code", key="show_code")
    st.toggle("Safe Mode", key="safe_mode")

# Centered logo + title
st.markdown(
    """
    <div class="df-hero">
      <div>
        <div class="df-logo">⚒️</div>
        <div class="df-name">DataForge</div>
        <div class="df-tag">Business intent → governed data app</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Quick start (centered, minimal)
mid_l, mid, mid_r = st.columns([1.0, 2.2, 1.0], gap="large")
with mid:
    with st.container(border=True):
        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            go_suggestions = st.button("Open Suggestions", width="stretch", key="go_suggestions")
        with c2:
            go_factory = st.button("Open Factory", width="stretch", key="go_factory")
        with c3:
            go_dashboard = st.button("Open Dashboard", width="stretch", key="go_dashboard")

# Navigate
if go_suggestions:
    try:
        st.switch_page("pages/4_Suggestions.py")
    except Exception:
        st.info("Use the sidebar to open Suggestions.")

if go_factory:
    try:
        st.switch_page("pages/1_Factory.py")
    except Exception:
        st.info("Use the sidebar to open Factory.")

if go_dashboard:
    try:
        st.switch_page("pages/2_Dashboard.py")
    except Exception:
        st.info("Use the sidebar to open Dashboard.")