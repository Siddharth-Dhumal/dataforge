"""
Agent 1 — SQL Generator (agents/sql_generator.py)

Uses Anthropic tool use pattern to convert NL → SQL.
Used by: factory pipeline + Genie API fallback on chat path.

System prompt contains: full governed schema, guardrails, role permissions,
hard constraints: SELECT only, governed schema only, LIMIT ≤ 10000 required.

After generation, SQL passes through query_validator.py regex check.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional, Tuple

# ── Schema context for the LLM ───────────────────────────────────────
SCHEMA_CONTEXT = """
You have access to EXACTLY these governed tables in the workspace catalog:

TABLE: workspace.governed.orders
  Columns: order_nbr (STRING), regional_manager (STRING, PII-MASKED), order_type (STRING), ord_qty (DECIMAL), region (STRING)
  Notes: order_type values include TRANSFER_ORDER, PURCHASE_ORDER, SALES_ORDER, RETURN_ORDER, DPI, Multi Family, Solar Panel Installation Order

TABLE: workspace.governed.inventory
  Columns: regional_manager (STRING, PII-MASKED), sku (STRING), sku_description (STRING), qoh (DECIMAL, quantity on hand), qoh_cost (DECIMAL, cost value), region (STRING)
  Notes: qoh = quantity on hand, qoh_cost = dollar value of inventory

TABLE: workspace.governed.shipping
  Columns: region (STRING), regional_manager (STRING, PII-MASKED), shipping_org (STRING), ship_date_ts (STRING), wms_shipment_status (STRING), sku (STRING), intransit_value (DECIMAL)
  Notes: wms_shipment_status values include 'In Transit', 'Delivered', 'Pending'. intransit_value is dollar amount.

RULES:
- ONLY use these three tables. Do NOT reference any other tables.
- ALWAYS include LIMIT (max 500).
- SELECT only. No INSERT, UPDATE, DELETE, DROP, CREATE, ALTER.
- Never use SELECT *. Always specify column names.
- The column 'regional_manager' is PII-masked. You can GROUP BY it or filter on it but the values are masked.
- Use SUM(), COUNT(), AVG(), MIN(), MAX() for aggregation.
- Always use fully qualified names: workspace.governed.orders (not just 'orders').
"""

# ── Tool definition (Anthropic tool use pattern) ──────────────────────
SQL_TOOL = {
    "name": "generate_sql",
    "description": "Generate a safe SQL SELECT query against governed Databricks tables",
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "The SQL SELECT query. Must use workspace.governed.* tables only. Must include LIMIT. Empty string if cannot_answer is true.",
            },
            "cannot_answer": {
                "type": "boolean",
                "description": "True if the question cannot be answered safely with a SELECT query against the available tables",
            },
            "reason": {
                "type": "string",
                "description": "If cannot_answer, explain why in one sentence. Otherwise, brief description of what the query does.",
            },
        },
        "required": ["sql", "cannot_answer", "reason"],
    },
}


def generate_sql(nl_question: str, *, limit: int = 500) -> Tuple[Optional[str], str, bool]:
    """
    Agent 1: Convert natural language to SQL using Anthropic tool use.

    Returns:
        (sql_or_none, reason, cannot_answer)
    """
    try:
        from utils.llm import call_claude
    except ImportError:
        return None, "LLM module not available", True

    system = (
        "You are the DataForge SQL Agent. Convert the user's natural language question "
        "into a single safe SQL SELECT query against the governed Databricks tables.\n\n"
        f"{SCHEMA_CONTEXT}\n"
        f"Use LIMIT {limit} unless the user specifically asks for fewer rows.\n"
        "If the question cannot be answered with the available tables, set cannot_answer to true."
    )

    result = call_claude(system, nl_question, SQL_TOOL)
    if result is None:
        return None, "Claude API unavailable", True

    sql = result.get("sql", "")
    cannot = result.get("cannot_answer", False)
    reason = result.get("reason", "")

    if cannot or not sql.strip():
        return None, reason or "Cannot answer this question with available tables", True

    return sql.strip(), reason, False
