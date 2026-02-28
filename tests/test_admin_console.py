from streamlit.testing.v1 import AppTest


def test_admin_console_loads_without_exception():
    at = AppTest.from_file("pages/5_IT_Admin_Console.py").run()
    assert len(at.exception) == 0
    assert at.title[0].value == "IT Admin Console"


def test_seed_audit_adds_events():
    at = AppTest.from_file("pages/5_IT_Admin_Console.py").run()
    assert len(at.session_state["audit_events"]) == 0

    at.button(key="seed_audit").click().run()
    assert len(at.session_state["audit_events"]) >= 3


def test_register_app_adds_registry_entry():
    at = AppTest.from_file("pages/5_IT_Admin_Console.py").run()
    assert len(at.session_state["app_registry"]) == 0

    at.button(key="register_app").click().run()
    assert len(at.session_state["app_registry"]) == 1
    assert at.session_state["app_registry"][0]["status"] == "registered"


def test_filters_exist_and_dataframe_renders():
    at = AppTest.from_file("pages/5_IT_Admin_Console.py").run()

    assert at.selectbox(key="admin_filter_status").value == "All"
    assert at.selectbox(key="admin_filter_event").value == "All"

    # We always render a dataframe (either real rows or a blank schema row)
    assert len(at.dataframe) >= 1