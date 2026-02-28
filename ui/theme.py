import streamlit as st

def apply_theme() -> None:
    st.markdown(
        """
        <style>
          /* Define the smooth panning animation */
          @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
          }

          .block-container {
            /* Stripe-ish: centered container that grows on large screens */
            max-width: 1480px;

            /* Responsive side gutters (never too small, never too huge) */
            padding-left: clamp(18px, 4vw, 72px);
            padding-right: clamp(18px, 4vw, 72px);

            /* Better vertical rhythm */
            padding-top: 28px;
            padding-bottom: 56px;
          }
          
          /* Make the main content area able to fill the viewport height */
          section.main > div {
            min-height: calc(100vh - 80px);
          }
          
          h1 {
            margin-bottom: 0.35rem;
            color: #f8fafc; /* Ensure main headers pop in dark mode */
          }
          
          /* The Animated Background */
          .stApp {
            /* Deep, moody blend of Midnight, Dark Indigo, and Deep Slate */
            background: linear-gradient(-45deg, 
                #0f172a, 
                #1e1b4b, 
                #020617, 
                #0f172a
            );
            background-size: 400% 400%;
            animation: gradientBG 18s ease infinite;
            color: #f8fafc; /* Default text color to light */
          }
          
          /* Glassmorphism Cards */
          .df-card {
            background: rgba(15, 23, 42, 0.65); /* Dark translucent background */
            border: 1px solid rgba(255, 255, 255, 0.08); /* Subtle light border */
            border-radius: 18px;
            padding: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4); /* Deeper shadow for dark mode */
            backdrop-filter: blur(12px); 
            -webkit-backdrop-filter: blur(12px);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
          }
          
          /* Subtle hover effect on cards */
          .df-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 14px 34px rgba(0, 0, 0, 0.6);
          }

          .df-title { font-size: 24px; font-weight: 780; letter-spacing: -0.02em; color: #f8fafc; }
          .df-subtitle { font-size: 14px; color: rgba(248, 250, 252, 0.65); margin-top: 4px; }
          
          #MainMenu {visibility: hidden;}
          footer {visibility: hidden;}
          header {background: transparent !important;} 

          /* The AI Processing Pulse */
          @keyframes aiPulse {
            0% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.4); border-color: rgba(56, 189, 248, 0.4); }
            70% { box-shadow: 0 0 15px 5px rgba(56, 189, 248, 0.1); border-color: rgba(56, 189, 248, 0.8); }
            100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); border-color: rgba(255, 255, 255, 0.08); }
          }

          .processing-card {
            animation: aiPulse 1.5s infinite;
            background: rgba(15, 23, 42, 0.85); /* Slightly darker to make the glow pop */
            border-left: 4px solid #38bdf8; /* Databricks-ish blue accent */
          }
          
          .step-text {
            font-family: 'Courier New', Courier, monospace;
            font-size: 15px;
            color: #e2e8f0;
            margin-bottom: 8px;
            transition: color 0.3s ease;
          }
          .step-done {
            color: #10b981; /* Emerald green for checkmarks */
          }
          /* Holographic AI Briefing Card */
          .ai-briefing-card {
            position: relative;
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 12px;
            padding: 20px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.1) inset;
          }

          /* The scanning laser line */
          .ai-briefing-card::after {
            content: "";
            position: absolute;
            top: 0;
            left: -100%;
            width: 50%;
            height: 100%;
            background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(56, 189, 248, 0.2) 50%, rgba(255,255,255,0) 100%);
            transform: skewX(-20deg);
            animation: hologramScan 4s infinite linear;
          }

          @keyframes hologramScan {
            0% { left: -100%; }
            50% { left: 200%; }
            100% { left: 200%; }
          }

          .ai-label {
            font-family: monospace;
            color: #38bdf8;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
          }
          
          /* Pulsing dot for the AI label */
          .ai-dot {
            width: 8px;
            height: 8px;
            background-color: #38bdf8;
            border-radius: 50%;
            box-shadow: 0 0 10px #38bdf8;
            animation: pulseDot 1.5s infinite;
          }

          @keyframes pulseDot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.8); }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )