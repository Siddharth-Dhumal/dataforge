"""
Agent 4 — Schema Analyzer (agents/schema_analyzer.py)

Powers Page 4 ("What Should I Build?"). One LLM call using Anthropic tool use pattern.

Returns structured list of 5 app suggestions. Each suggestion includes a
`factory_prompt` field — the pre-filled text sent to the factory when user
clicks "Build This." Never empty. Always actionable.

Uses get_schema_metadata() from core/databricks_connect.py to fetch live schema,
then passes it to Claude via call_claude() with the suggest_apps tool.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Tool definition (Anthropic tool use pattern, per masterplan) ──────
SUGGEST_TOOL = {
    "name": "suggest_apps",
    "description": "Suggest 5 actionable dashboard/app ideas based on the database schema",
    "input_schema": {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short name, max 6 words"},
                        "description": {
                            "type": "string",
                            "description": "1-2 sentences on what it shows and why it matters",
                        },
                        "tables": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of tables used (e.g. workspace.governed.orders)",
                        },
                        "kpis": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key performance indicators this dashboard tracks",
                        },
                        "factory_prompt": {
                            "type": "string",
                            "description": "The exact text to pre-fill in the Factory when user clicks Build This",
                        },
                    },
                    "required": ["title", "description", "tables", "kpis", "factory_prompt"],
                },
            }
        },
        "required": ["suggestions"],
    },
}


# ── Schema context built from governed tables ────────────────────────
SCHEMA_CONTEXT = """Available governed tables in workspace.governed:

TABLE: workspace.governed.orders
COLUMNS: order_nbr (string), order_type (string), ord_qty (int),
         region (string), regional_manager (string — PII, masked)

TABLE: workspace.governed.inventory
COLUMNS: sku (string), sku_description (string), region (string),
         total_quantity_on_hand (bigint), total_cost (double),
         regional_manager (string — PII, masked)

TABLE: workspace.governed.shipping
COLUMNS: wms_shipment_nbr (string), wms_shipment_status (string),
         region (string), shipping_org (string),
         intransit_value (double), received_value (double),
         regional_manager (string — PII, masked)
"""




def _get_live_schema() -> str:
    """
    Try to get live schema from Databricks via get_schema_metadata().
    Falls back to hardcoded SCHEMA_CONTEXT if Databricks is unavailable.
    """
    try:
        from core.databricks_connect import get_schema_metadata
        metadata = get_schema_metadata("workspace", "governed")
        if metadata:
            lines = []
            for table_name, columns in metadata.items():
                cols_str = ", ".join(
                    f"{col.get('col_name', 'unknown')} ({col.get('data_type', 'unknown')})"
                    for col in columns
                    if col.get("col_name") and not col["col_name"].startswith("#")
                )
                lines.append(f"TABLE: workspace.governed.{table_name}\nCOLUMNS: {cols_str}")
            if lines:
                return "Available governed tables:\n\n" + "\n\n".join(lines)
    except Exception as e:
        logger.info(f"[Agent 4] Live schema fetch failed, using cached: {e}")

    return SCHEMA_CONTEXT


def analyze_schema() -> Dict:
    """
    Agent 4: Schema Analyzer — powers the Suggestions page.

    One LLM call using Anthropic tool use pattern.
    Returns dict with 'success', 'suggestions' (list of 5 dicts), and 'error'.

    Each suggestion dict has: title, description, tables, kpis, factory_prompt.
    """
    # Ensure env is loaded (idempotent)
    try:
        from core.env_loader import load_env
        load_env()
    except Exception:
        pass

    try:
        from utils.llm import call_claude
    except ImportError as ie:
        logger.warning(f"[Agent 4] Import error: {ie}")
        return {"success": False, "error": str(ie), "suggestions": []}

    schema = _get_live_schema()

    system = (
        "You are a senior data product strategist for DataForge, a governed analytics "
        "platform built on Databricks. Your job is to look at the available database schema "
        "and recommend exactly 5 specific, actionable dashboard or mini-app ideas that a "
        "business user would find immediately valuable.\n\n"
        "Each suggestion must be tailored to the actual tables and columns provided.\n"
        "Each factory_prompt must be a complete, detailed instruction that could be "
        "directly pasted into an AI dashboard generator — include specific tables, "
        "columns, chart types, and filters.\n\n"
        "Rules:\n"
        "- Never include PII columns (regional_manager, email, salary) in KPIs or prompts\n"
        "- Always reference the full table path (workspace.governed.tablename)\n"
        "- Factory prompts should mention chart types (bar, line, pie, scatter)\n"
        "- KPIs should be concrete and measurable\n\n"
        f"{schema}"
    )

    user_msg = (
        "Analyze the schema and suggest exactly 5 dashboards or mini-apps that would "
        "provide the most business value. Make each suggestion specific and actionable."
    )

    result = call_claude(system, user_msg, SUGGEST_TOOL, max_tokens=4096)

    if result is None:
        return {"success": False, "error": "LLM call failed", "suggestions": []}

    suggestions = result.get("suggestions", [])

    # Enforce max 5
    suggestions = suggestions[:5]

    # Validate each suggestion has required fields
    validated = []
    for s in suggestions:
        validated.append({
            "title": s.get("title", "Untitled Dashboard"),
            "description": s.get("description", "A data dashboard."),
            "tables": s.get("tables", []),
            "kpis": s.get("kpis", []),
            "factory_prompt": s.get("factory_prompt", "Build a dashboard"),
        })

    return {"success": True, "error": None, "suggestions": validated}


# ── Hardcoded fallback suggestions (when ALL APIs are down) ──────────
FALLBACK_SUGGESTIONS = [
    {
        "title": "Order Analytics by Region",
        "description": "Track order volume, types, and quantities across all regions to identify your highest-performing markets.",
        "tables": ["workspace.governed.orders"],
        "kpis": ["Total Orders", "Avg Quantity per Order", "Orders by Type"],
        "factory_prompt": (
            "Build an order analytics dashboard using workspace.governed.orders. "
            "Show a bar chart of order count by region, a pie chart of order types, "
            "and a line chart of quantity trends. Include filters for region and order_type. "
            "Mask regional_manager column."
        ),
    },
    {
        "title": "Inventory Stock Monitor",
        "description": "Monitor real-time stock levels by SKU and region to prevent stockouts and optimize warehouse allocation.",
        "tables": ["workspace.governed.inventory"],
        "kpis": ["Total Stock Value", "Low Stock SKUs", "Regional Inventory Balance"],
        "factory_prompt": (
            "Create an inventory monitoring dashboard using workspace.governed.inventory. "
            "Show bar chart of total_quantity_on_hand by region, scatter plot of cost vs quantity by SKU, "
            "and a table of top 20 SKUs by stock value. Include filters for region and sku. "
            "Mask regional_manager."
        ),
    },
    {
        "title": "Shipping & Transit Tracker",
        "description": "Visualize shipment status and transit values to optimize logistics operations and reduce delays.",
        "tables": ["workspace.governed.shipping"],
        "kpis": ["In-Transit Value", "Shipment Count by Status", "On-Time Rate"],
        "factory_prompt": (
            "Build a shipping tracker dashboard using workspace.governed.shipping. "
            "Show bar chart of shipment count by wms_shipment_status, bar chart of intransit_value by region, "
            "and pie chart of shipping_org distribution. Include filters for region and status. "
            "Mask regional_manager."
        ),
    },
    {
        "title": "Cross-Domain Supply Overview",
        "description": "Combine orders, inventory, and shipping data for an end-to-end supply chain visibility dashboard.",
        "tables": ["workspace.governed.orders", "workspace.governed.inventory", "workspace.governed.shipping"],
        "kpis": ["Order-to-Ship Ratio", "Stock Coverage Days", "Regional Supply Score"],
        "factory_prompt": (
            "Build a supply chain overview dashboard using workspace.governed.orders, "
            "workspace.governed.inventory, and workspace.governed.shipping. "
            "Show bar chart of orders vs shipments by region, inventory levels as heatmap, "
            "and shipping status breakdown. Include region filter. Mask regional_manager."
        ),
    },
    {
        "title": "Regional Performance Scorecard",
        "description": "Compare regions across orders, inventory, and logistics KPIs to identify top and underperforming areas.",
        "tables": ["workspace.governed.orders", "workspace.governed.inventory", "workspace.governed.shipping"],
        "kpis": ["Revenue by Region", "Fulfillment Rate", "Inventory Turnover"],
        "factory_prompt": (
            "Create a regional scorecard dashboard comparing all regions across "
            "workspace.governed.orders (order count, quantity), workspace.governed.inventory "
            "(stock value), and workspace.governed.shipping (transit value). "
            "Use bar charts for comparison and include region dropdown filter. Mask regional_manager."
        ),
    },
]
