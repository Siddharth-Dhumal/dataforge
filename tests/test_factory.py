import unittest
import os
import streamlit as st
from factory.factory import run_factory_pipeline

class TestFactoryPipeline(unittest.TestCase):
    def setUp(self):
        # Mocking streamlit session state for the dynamic renderer
        st.session_state = {}
        os.environ["ANTHROPIC_API_KEY"] = "dummy_test_key"

    def test_pipeline_integration(self):
        success, msg, spec, code = run_factory_pipeline(
            "I need a sales dashboard with a bar chart.",
            "analyst"
        )
        
        self.assertTrue(success, f"Pipeline failed: {msg}")
        self.assertIn("domain", spec)
        self.assertTrue(len(code) > 0)
        self.assertIn("import streamlit as st", code)
        self.assertIn("current_app_spec", st.session_state)

if __name__ == '__main__':
    unittest.main()
