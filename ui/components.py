import streamlit as st

def top_bar(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="df-card">
          <div class="df-title">{title}</div>
          <div class="df-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

def section_title(text: str) -> None:
    st.markdown(f"**{text}**")

def ai_briefing(text: str) -> None:
    st.markdown(
        f"""
        <div class="ai-briefing-card">
          <div class="ai-label"><div class="ai-dot"></div> AI-Generated Interpretation</div>
          <div style="font-size: 15px; line-height: 1.6; color: #e2e8f0;">
            {text}
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.write("")