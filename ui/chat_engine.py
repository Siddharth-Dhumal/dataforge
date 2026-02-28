"""
Chat engine — LLM-powered NL-to-SQL against governed Databricks tables.

Flow per the team plan:
  1. User NL → Agent 1 (Claude tool use) generates SQL
  2. SQL validated via query_validator
  3. Executed against Databricks via direct connection
  4. If SQL fails → Agent 2 (self-healing) retries once with error context
  5. Agent 3 (insight generator) produces AI briefing
  6. Keyword fallback if Claude is unavailable

All governed tables only. PII masked. SELECT-only. LIMIT enforced.
"""
from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatResult:
    can_answer: bool
    assistant_text: str
    sql: str
    policy_note: str
    preview_rows: List[Dict]
    insight: str = ""


# ── PII blocked terms ────────────────────────────────────────────────
_BLOCKED_TERMS = [
    "email", "phone", "ssn", "address", "password",
    "credit card", "card number", "social security",
    "personal info", "pii",
]

# ── Schema context for the LLM ───────────────────────────────────────
_SCHEMA_CONTEXT = """
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

# ── Agent 1: LLM SQL Generator (Claude tool use) ─────────────────────
_SQL_TOOL = {
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


def _generate_sql_via_llm(prompt: str, safe_mode: bool) -> Tuple[str | None, str, bool]:
    """
    Agent 1: Use Claude to convert natural language to SQL.
    Returns (sql_or_none, reason, cannot_answer).
    """
    try:
        from utils.llm import call_claude
    except ImportError:
        return None, "LLM module not available", True

    limit = 50 if safe_mode else 500
    system = (
        "You are the DataForge SQL Agent. Convert the user's natural language question "
        "into a single safe SQL SELECT query against the governed Databricks tables.\n\n"
        f"{_SCHEMA_CONTEXT}\n"
        f"Use LIMIT {limit} unless the user specifically asks for fewer rows.\n"
        "If the question cannot be answered with the available tables, set cannot_answer to true."
    )

    result = call_claude(system, prompt, _SQL_TOOL)
    if result is None:
        return None, "Claude API unavailable", True

    sql = result.get("sql", "")
    cannot = result.get("cannot_answer", False)
    reason = result.get("reason", "")

    if cannot or not sql.strip():
        return None, reason or "Cannot answer this question with available tables", True

    return sql.strip(), reason, False


# ── Agent 2: Self-healing retry ───────────────────────────────────────
MAX_RETRIES = 1


def _self_heal_sql(original_sql: str, error_msg: str, prompt: str, safe_mode: bool) -> Tuple[str | None, str]:
    """
    Agent 2: If the original SQL failed, retry once with error context.
    Returns (fixed_sql_or_none, reason).
    """
    try:
        from utils.llm import call_claude
    except ImportError:
        return None, "LLM unavailable for self-healing"

    limit = 50 if safe_mode else 500
    system = (
        "You are the DataForge SQL Self-Healing Agent. A SQL query failed with an error. "
        "Fix the query based on the error message. Return a corrected query.\n\n"
        f"{_SCHEMA_CONTEXT}\n"
        f"Use LIMIT {limit}.\n"
    )
    user_msg = (
        f"Original question: {prompt}\n\n"
        f"Failed SQL:\n{original_sql}\n\n"
        f"Error: {error_msg}\n\n"
        "Please fix this SQL query."
    )

    result = call_claude(system, user_msg, _SQL_TOOL)
    if result is None:
        return None, "Self-healing failed"

    sql = result.get("sql", "")
    reason = result.get("reason", "Fixed query")
    if result.get("cannot_answer") or not sql.strip():
        return None, reason or "Cannot fix this query"

    return sql.strip(), reason


# ── Agent 3: Insight generator ────────────────────────────────────────
def _generate_insight(rows: List[Dict], prompt: str) -> str:
    """
    Agent 3: Generate a plain English interpretation of the query results.
    Never sends raw data — only summary stats.
    """
    if not rows:
        return ""

    try:
        from utils.llm import call_claude_text
    except ImportError:
        return ""

    # Build summary stats (never raw data, never PII)
    cols = list(rows[0].keys())
    row_count = len(rows)
    stats = []
    for col in cols:
        vals = [r[col] for r in rows if r.get(col) is not None]
        if vals and isinstance(vals[0], (int, float)):
            stats.append(f"{col}: min={min(vals):.2f}, max={max(vals):.2f}, avg={sum(vals)/len(vals):.2f}")
        elif vals and isinstance(vals[0], str):
            unique = len(set(vals))
            stats.append(f"{col}: {unique} unique values (e.g. {vals[0]!r})")

    summary = f"Query: {prompt}\nRows: {row_count}\nColumns: {', '.join(cols)}\n"
    summary += "\n".join(stats)

    try:
        insight = call_claude_text(
            user_prompt=f"Provide a 2-3 sentence plain English insight about this data:\n\n{summary}",
            system_prompt=(
                "You are a data analyst. Given summary statistics of a query result, "
                "provide a brief, insightful interpretation. Focus on key patterns, "
                "notable values, and actionable observations. Keep it to 2-3 sentences."
            ),
        )
        if insight and not insight.startswith("Claude Error"):
            return insight
    except Exception:
        pass

    return ""


# ── Keyword fallback (when Claude is unavailable) ─────────────────────
_TABLES_META = {
    "orders": {
        "fqn": "workspace.governed.orders",
        "icon": "🌍",
        "keywords": [
            "order", "orders", "purchase", "buy", "bought", "sales",
            "transaction", "quantity", "qty", "transfer", "return",
        ],
        "queries": {
            "by_region": ("Orders by region and type", "SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY region, order_type ORDER BY total_qty DESC", ["region", "area", "geography", "where", "location"]),
            "by_type": ("Orders by type", "SELECT order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY order_type ORDER BY total_qty DESC", ["type", "kind", "category", "breakdown"]),
            "totals": ("Order totals", "SELECT COUNT(order_nbr) AS total_orders, SUM(ord_qty) AS total_qty FROM workspace.governed.orders", ["total", "count", "how many", "sum", "overall"]),
            "default": ("Orders overview", "SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY region, order_type ORDER BY total_qty DESC", []),
        },
    },
    "inventory": {
        "fqn": "workspace.governed.inventory",
        "icon": "📦",
        "keywords": [
            "inventory", "stock", "sku", "warehouse", "supply",
            "qoh", "product", "item", "goods", "cost", "value",
            "expensive", "cheap", "price",
        ],
        "queries": {
            "by_sku": ("Inventory by SKU", "SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY sku, sku_description, region ORDER BY total_cost DESC", ["sku", "product", "item", "part", "description"]),
            "by_region": ("Inventory by region", "SELECT region, COUNT(sku) AS sku_count, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY region ORDER BY total_cost DESC", ["region", "area", "where"]),
            "totals": ("Inventory totals", "SELECT COUNT(DISTINCT sku) AS unique_skus, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_value FROM workspace.governed.inventory", ["total", "count", "how many", "sum", "overall", "value", "worth"]),
            "top": ("Top inventory by value", "SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY sku, sku_description, region ORDER BY total_cost DESC", ["top", "most", "expensive", "highest", "largest", "biggest"]),
            "low": ("Lowest stock items", "SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY sku, sku_description, region ORDER BY total_qty ASC", ["low", "lowest", "least", "minimum", "running out"]),
            "default": ("Inventory overview", "SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY sku, sku_description, region ORDER BY total_cost DESC", []),
        },
    },
    "shipping": {
        "fqn": "workspace.governed.shipping",
        "icon": "🚚",
        "keywords": [
            "ship", "shipping", "transit", "delivery", "deliver",
            "carrier", "logistics", "transport", "shipment",
            "status", "tracking", "delayed", "intransit", "wms",
        ],
        "queries": {
            "by_status": ("Shipping by status", "SELECT wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value FROM workspace.governed.shipping GROUP BY wms_shipment_status ORDER BY total_value DESC", ["status", "state", "progress", "tracking", "delayed", "pending"]),
            "by_region": ("Shipping by region", "SELECT region, shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value FROM workspace.governed.shipping GROUP BY region, shipping_org, wms_shipment_status ORDER BY total_value DESC", ["region", "area", "where"]),
            "by_carrier": ("Shipping by carrier", "SELECT shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value FROM workspace.governed.shipping GROUP BY shipping_org, wms_shipment_status ORDER BY total_value DESC", ["carrier", "org", "company", "shipper"]),
            "totals": ("Shipping totals", "SELECT COUNT(sku) AS total_shipments, SUM(intransit_value) AS total_transit_value FROM workspace.governed.shipping", ["total", "count", "how many", "sum", "overall"]),
            "default": ("Shipping overview", "SELECT region, shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value FROM workspace.governed.shipping GROUP BY region, shipping_org, wms_shipment_status ORDER BY total_value DESC", []),
        },
    },
}


def _keyword_fallback(prompt: str, limit: int) -> Tuple[str, str, str]:
    """Fallback: keyword-match to a table and query template. Returns (sql, label, icon)."""
    lower = prompt.lower()
    scores = {}
    for tname, meta in _TABLES_META.items():
        score = sum(1 for kw in meta["keywords"] if kw in lower)
        if score > 0:
            scores[tname] = score

    if not scores:
        # Cross-table default
        return (
            f"SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY region, order_type ORDER BY total_qty DESC LIMIT {limit}",
            "Orders overview (default)",
            "📋",
        )

    tname = max(scores, key=scores.get)
    meta = _TABLES_META[tname]

    # Pick best sub-query
    best_shape, best_score = "default", 0
    for shape, (label, sql, triggers) in meta["queries"].items():
        if shape == "default":
            continue
        s = sum(1 for t in triggers if t in lower)
        if s > best_score:
            best_score = s
            best_shape = shape

    label, sql, _ = meta["queries"][best_shape]
    if "LIMIT" not in sql:
        sql = f"{sql} LIMIT {limit}"
    else:
        sql = re.sub(r"LIMIT \d+", f"LIMIT {limit}", sql)

    return sql, label, meta["icon"]


# ── Databricks connection ─────────────────────────────────────────────
def _ensure_env():
    if not os.environ.get("DATABRICKS_HOST"):
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


def _clean_value(v):
    return float(v) if isinstance(v, Decimal) else v


def _run_query(sql: str) -> Tuple[bool, List[Dict], str]:
    _ensure_env()
    host = os.environ.get("DATABRICKS_HOST", "")
    http_path = os.environ.get("DATABRICKS_HTTP_PATH", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if not all([host, http_path, token]):
        return False, [], "Missing Databricks credentials"
    try:
        from utils.query_validator import validate_query
        validated = validate_query(sql)
    except Exception as e:
        return False, [], f"Validation: {e}"
    try:
        from databricks import sql as dbsql
        conn = dbsql.connect(server_hostname=host, http_path=http_path, access_token=token)
        cur = conn.cursor()
        cur.execute(validated)
        if not cur.description:
            cur.close(); conn.close()
            return True, [], ""
        cols = [d[0] for d in cur.description]
        raw = cur.fetchall()
        cur.close(); conn.close()
        rows = [{c: _clean_value(v) for c, v in zip(cols, r)} for r in raw]
        return True, rows, ""
    except Exception as e:
        return False, [], str(e)


# ── Main entry point ─────────────────────────────────────────────────
def answer_chat(
    prompt: str,
    *,
    days: int,
    safe_mode: bool,
    demo_mode: bool,
    seed: int,
) -> ChatResult:
    p = (prompt or "").strip()
    lower = p.lower()

    # 1. Block PII
    if any(t in lower for t in _BLOCKED_TERMS):
        return ChatResult(
            can_answer=False,
            assistant_text=(
                "**🛡️ BLOCKED** — This request touches sensitive fields.\n\n"
                "I can help with:\n"
                "- 🌍 Orders by region / type\n"
                "- 📦 Inventory levels by SKU\n"
                "- 🚚 Shipping status by carrier"
            ),
            sql="-- BLOCKED: sensitive/PII fields",
            policy_note="🛡️ Blocked by governance: request touches sensitive fields.",
            preview_rows=[],
        )

    limit = 50 if safe_mode else 500
    source_label = "unknown"
    healed = False

    # 2. Try Agent 1: Claude NL-to-SQL
    sql, reason, cannot = _generate_sql_via_llm(p, safe_mode)

    if cannot or sql is None:
        # Claude unavailable or can't answer → keyword fallback
        sql, fallback_label, icon = _keyword_fallback(p, limit)
        source_label = "keyword_fallback"
        reason = fallback_label
    else:
        source_label = "ai"
        # Ensure LIMIT
        if "LIMIT" not in sql.upper():
            sql = f"{sql} LIMIT {limit}"

    # 3. Execute against Databricks
    ok, rows, err = _run_query(sql)

    # 4. Agent 2: Self-healing — if SQL failed and we used AI, retry once
    if not ok and source_label == "ai":
        healed_sql, heal_reason = _self_heal_sql(sql, err, p, safe_mode)
        if healed_sql:
            ok2, rows2, err2 = _run_query(healed_sql)
            if ok2:
                rows = rows2
                ok = True
                err = ""
                sql = healed_sql
                source_label = "ai (self-healed)"
                healed = True

    # 5. Build response message
    if ok and rows:
        msg = f"**{reason}**\n\n✅ **{len(rows)} rows** returned live from Databricks."
        if healed:
            msg += "\n\n🩹 *Query was auto-corrected by the self-healing agent.*"
    elif ok and not rows:
        msg = f"**{reason}**\n\n⚠️ Query returned 0 rows."
    else:
        msg = f"**{reason}**\n\n❌ **Error:** {err}"

    # 6. Agent 3: Generate AI insight
    insight_text = ""
    if ok and rows and len(rows) >= 1:
        insight_text = _generate_insight(rows, p)

    policy_note = (
        f"Source: {source_label} • governed views • masked PII • SELECT-only • LIMIT {limit}"
        + (" • safe mode" if safe_mode else "")
        + (" • self-healed" if healed else "")
    )

    return ChatResult(
        can_answer=ok,
        assistant_text=msg,
        sql=sql,
        policy_note=policy_note,
        preview_rows=rows[:20] if rows else [],
        insight=insight_text,
    )