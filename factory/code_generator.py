"""
Code Generator — renders Jinja2 templates and validates syntax.

Bulletproofed: sanitizes filter names to valid Python identifiers,
validates with ast.parse(), and falls back to a safe minimal dashboard
if the template render or syntax check fails.
"""
import ast
import re
import logging
from typing import Dict, Any, Tuple
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "config" / "app_templates"


def _sanitize_identifier(name: str) -> str:
    """Convert any string into a valid Python identifier."""
    # Replace spaces, hyphens, dots with underscores
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
    # Remove leading digits
    clean = re.sub(r"^[0-9]+", "", clean)
    # Remove consecutive underscores
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean.lower() or "filter"


def _sanitize_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize the spec to prevent template rendering errors.
    Ensures all filter names are valid Python identifiers and
    all chart types are valid enum values.
    """
    # Sanitize filters
    raw_filters = spec.get("filters", [])
    sanitized_filters = []
    seen = set()
    for f in raw_filters:
        clean = _sanitize_identifier(str(f))
        # Deduplicate
        if clean not in seen:
            sanitized_filters.append(clean)
            seen.add(clean)
    spec["filters"] = sanitized_filters

    # Sanitize chart types — only allow valid Plotly chart types
    valid_charts = {"bar", "line", "scatter", "heatmap", "pie"}
    spec["charts"] = [c for c in spec.get("charts", ["bar"]) if c in valid_charts] or ["bar"]

    # Ensure tables is a list of strings
    spec["tables"] = [str(t) for t in spec.get("tables", ["governed.orders"])]

    # Ensure kpis is a list of strings
    spec["kpis"] = [str(k) for k in spec.get("kpis", ["Total Count"])]

    # Ensure domain is a simple string
    spec["domain"] = _sanitize_identifier(str(spec.get("domain", "general"))).replace("_", " ").title()
    if not spec["domain"]:
        spec["domain"] = "General"

    return spec


def _fallback_code(spec: Dict[str, Any]) -> str:
    """
    Generate safe minimal dashboard code when template rendering fails.
    This always produces valid Python.
    """
    domain = spec.get("domain", "Dashboard")
    tables = spec.get("tables", ["governed.orders"])
    kpis = spec.get("kpis", ["Total Count"])
    filters = spec.get("filters", ["region"])
    charts = spec.get("charts", ["bar"])

    table_str = tables[0] if tables else "governed.orders"
    kpis_repr = repr(kpis)
    filters_code = "\n".join(
        f'    {_sanitize_identifier(f)}_filter = st.sidebar.multiselect("Select {f.replace("_", " ").title()}", [])'
        for f in filters
    )
    charts_code = "\n".join(
        f'    st.plotly_chart(build_chart("{c}", []))'
        for c in charts
    )

    return f'''import streamlit as st
import pandas as pd
from core.databricks_connect import execute_query
from components.chart_builder import build_chart
from components.kpi_cards import render_kpis

def main():
    st.set_page_config(page_title="{domain} Dashboard", layout="wide")
    st.title("{domain} Dashboard")

    st.sidebar.header("Filters")
{filters_code}

    st.subheader("Key Performance Indicators")
    render_kpis({kpis_repr})

    st.subheader("Charts")
{charts_code}


if __name__ == "__main__":
    main()
'''


def generate_code(spec: Dict[str, Any]) -> Tuple[str, str]:
    """
    Renders Jinja2 templates based on the spec.
    Validates Python syntax using ast.parse().
    Falls back to safe minimal code on any failure.
    Returns: (code_string, error_message)
    Error message is empty on success.
    """
    # Sanitize spec first
    spec = _sanitize_spec(spec)

    # Try Jinja2 template rendering
    rendered_code = ""
    try:
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

        if spec.get("chatbot", False):
            template = env.get_template("chatbot_template.py.jinja")
        else:
            template = env.get_template("dashboard_template.py.jinja")

        rendered_code = template.render(**spec)
    except Exception as e:
        logger.warning(f"Template rendering failed, using fallback: {e}")
        rendered_code = _fallback_code(spec)

    # Validate syntax
    try:
        ast.parse(rendered_code)
    except SyntaxError as e:
        logger.warning(f"Template code had syntax error at line {e.lineno}, using fallback: {e}")
        # Use the failsafe fallback code
        rendered_code = _fallback_code(spec)
        # Validate fallback too (should never fail, but be safe)
        try:
            ast.parse(rendered_code)
        except SyntaxError as e2:
            logger.error(f"Even fallback code has syntax error: {e2}")
            return "", f"Code generation failed: {e2}"

    return rendered_code, ""
