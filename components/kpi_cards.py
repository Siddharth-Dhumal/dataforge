"""
components/kpi_cards.py — Reusable KPI metric card component.

Per masterplan: Top row has 5 KPI metric cards.
"""
import streamlit as st
from typing import List


def render_kpis(kpi_names: List[str], values: List = None) -> None:
    """
    Render KPI metric cards in a horizontal row.
    If values are not provided, displays placeholder dashes.
    """
    if not kpi_names:
        return

    cols = st.columns(len(kpi_names), gap="medium")
    for i, name in enumerate(kpi_names):
        val = values[i] if values and i < len(values) else "—"
        cols[i].metric(name, val)
