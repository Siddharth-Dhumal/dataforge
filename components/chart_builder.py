"""
components/chart_builder.py — Plotly chart factory.

Supports: bar, line, scatter, heatmap, pie.
Per masterplan: No default Streamlit charts. Plotly everywhere. No exceptions.
"""
from __future__ import annotations
import plotly.express as px
import pandas as pd
from typing import Any, Dict, List, Optional


# Shared Plotly dark theme layout
_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#f8fafc", family="sans-serif"),
    margin=dict(l=20, r=20, t=40, b=20),
    hoverlabel=dict(bgcolor="rgba(15, 23, 42, 0.9)", font_size=14, font_family="monospace"),
    xaxis=dict(showgrid=False, zeroline=False),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False),
)

_COLORS = ["#38bdf8", "#818cf8", "#c084fc", "#f472b6", "#10b981", "#f59e0b", "#f43f5e"]


def build_chart(
    chart_type: str,
    data: List[Dict] | pd.DataFrame,
    *,
    x: Optional[str] = None,
    y: Optional[str] = None,
    color: Optional[str] = None,
    title: str = "",
) -> Any:
    """
    Build a Plotly figure from data and chart type.
    Returns a plotly Figure object.
    """
    if isinstance(data, list):
        df = pd.DataFrame(data) if data else pd.DataFrame()
    else:
        df = data

    if df.empty:
        fig = px.bar(pd.DataFrame({"No Data": [0]}), y="No Data", title=title or "No Data")
        fig.update_layout(**_LAYOUT)
        return fig

    # Auto-detect columns if not specified
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    str_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

    if x is None:
        x = str_cols[0] if str_cols else df.columns[0]
    if y is None:
        y = num_cols[0] if num_cols else df.columns[-1]
    if color is None and len(str_cols) > 1:
        color = str_cols[1]

    if chart_type == "bar":
        fig = px.bar(df, x=x, y=y, color=color, title=title, color_discrete_sequence=_COLORS)
    elif chart_type == "line":
        fig = px.line(df, x=x, y=y, color=color, title=title, color_discrete_sequence=_COLORS)
    elif chart_type == "scatter":
        fig = px.scatter(df, x=x, y=y, color=color, title=title, color_discrete_sequence=_COLORS)
    elif chart_type == "pie":
        fig = px.pie(df, values=y, names=x, title=title, color_discrete_sequence=_COLORS)
    elif chart_type == "heatmap":
        fig = px.density_heatmap(df, x=x, y=y, title=title)
    else:
        fig = px.bar(df, x=x, y=y, color=color, title=title, color_discrete_sequence=_COLORS)

    fig.update_layout(**_LAYOUT)
    return fig
