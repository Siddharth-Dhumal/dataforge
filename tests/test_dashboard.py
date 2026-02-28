from streamlit.testing.v1 import AppTest


def test_dashboard_loads_without_exception():
    at = AppTest.from_file("pages/2_Dashboard.py").run()
    assert len(at.exception) == 0


def test_dashboard_filters_exist_and_defaults_are_stable():
    at = AppTest.from_file("pages/2_Dashboard.py").run()

    assert at.title[0].value == "Dashboard"
    assert at.selectbox(key="dash_region").value == "All"
    assert at.slider(key="dash_days").value == 30
    assert at.multiselect(key="dash_product_lines").value == ["Widgets", "Gadgets", "Services"]


def test_dashboard_refresh_increments_refresh_count():
    at = AppTest.from_file("pages/2_Dashboard.py").run()

    assert at.session_state["dashboard_refresh_count"] == 0
    at.button(key="refresh_dashboard").click().run()
    assert at.session_state["dashboard_refresh_count"] == 1


def test_dashboard_kpis_and_table_render():
    at = AppTest.from_file("pages/2_Dashboard.py").run()

    # Metrics are supported by AppTest
    assert len(at.metric) == 3

    # Table exists by default (Show table = True)
    assert len(at.dataframe) >= 1