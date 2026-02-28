from streamlit.testing.v1 import AppTest

def test_app_loads_without_exception():
    at = AppTest.from_file("app.py").run()
    assert len(at.exception) == 0

def test_sidebar_toggles_exist_by_key():
    at = AppTest.from_file("app.py").run()
    assert at.sidebar.toggle(key="demo_mode").value is True
    assert at.sidebar.toggle(key="show_code").value is True
    assert at.sidebar.toggle(key="safe_mode").value is True

def test_factory_page_generates_spec_and_shows_json():
    at = AppTest.from_file("pages/1_Factory.py").run()

    assert at.title[0].value == "Factory"

    at.button(key="generate_spec").click().run()

    assert len(at.success) == 1
    assert at.session_state["last_generated_spec"]["app_name"] == "Sales Performance"
    assert len(at.json) == 1