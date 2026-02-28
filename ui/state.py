import streamlit as st

def init_state() -> None:
    defaults = {
        "demo_mode": True,
        "show_code": True,
        "safe_mode": True,
        "selected_dataset": "Retail Sales (Demo)",
        "last_generated_spec": None,
        "last_generated_code": None,
        "last_dashboard_config": None,
        # Dashboard page state
        "dashboard_refresh_count": 0,
        "dash_region": "All",
        "dash_product_lines": ["Widgets", "Gadgets", "Services"],
        "dash_days": 30,
        "dash_show_table": True,
        # Chat page state
        "chat_history": [],              # list[dict] with {"role": "...", "content": "..."}
        "chat_days": 30,
        "chat_show_sql": True,
        "last_chat_sql": None,
        "last_chat_policy_note": None,
        "force_chat_prompt": None,
        # Shared audit (stub for now; IT Console will read this later)
        "audit_events": [],
        # Suggestions page state
        "suggested_chat_prompt": None,
        "demo_bundle_loaded": False,
        "business_request": "",
        "schema_suggestions": [],
        "suggestions_error": None,
        # Admin / registry state
        "app_registry": [],                 # list of dicts
        "admin_filter_status": "All",
        "admin_filter_event": "All",
        "admin_search": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v