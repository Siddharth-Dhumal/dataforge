from streamlit.testing.v1 import AppTest


def test_suggestions_loads_without_exception():
    at = AppTest.from_file("pages/4_Suggestions.py").run()
    assert len(at.exception) == 0
    assert at.title[0].value == "Suggestions"


def test_template_loads_into_factory_sets_request_and_dataset():
    at = AppTest.from_file("pages/4_Suggestions.py").run()

    at.button(key="tpl_factory_sales").click().run()

    assert "Build a sales performance dashboard" in at.session_state["business_request"]
    assert at.session_state["selected_dataset"] == "Retail Sales (Demo)"


def test_run_chat_demo_appends_chat_history_and_sql():
    at = AppTest.from_file("pages/4_Suggestions.py").run()

    # Run chat demo for sales template
    at.button(key="tpl_chat_sales").click().run()

    assert len(at.session_state["chat_history"]) >= 2
    assert at.session_state["chat_history"][0]["role"] == "user"
    assert at.session_state["chat_history"][1]["role"] == "assistant"
    assert at.session_state["last_chat_sql"] is not None


def test_full_demo_bundle_populates_spec_code_chat_and_audit():
    at = AppTest.from_file("pages/4_Suggestions.py").run()

    at.button(key="load_full_demo").click().run()

    assert at.session_state["demo_bundle_loaded"] is True
    assert at.session_state["last_generated_spec"] is not None
    assert at.session_state["last_generated_code"] is not None
    assert len(at.session_state["chat_history"]) >= 2
    assert len(at.session_state["audit_events"]) >= 1