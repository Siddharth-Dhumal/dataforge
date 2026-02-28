"""
Chat engine — generates governed SQL from natural language and executes against Databricks.
Direct connection, no caching, no silent fallbacks. Comprehensive intent routing.
"""
from __future__ import annotations

import os
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


# ── PII / blocked terms ─────────────────────────────────────────────
_BLOCKED_TERMS = [
    "email", "phone", "ssn", "address", "password",
    "credit card", "card number", "social security",
    "personal info", "pii",
]

# ── Known schema catalog ─────────────────────────────────────────────
# Each entry describes a governed table, the keywords that trigger it,
# and a set of query templates for different "shapes" of question.
_TABLES = {
    "orders": {
        "fqn": "workspace.governed.orders",
        "icon": "🌍",
        "keywords": [
            "order", "orders", "purchase", "buy", "bought", "sales",
            "transaction", "quantity", "qty", "ord_qty",
            "order_type", "transfer", "return",
        ],
        "columns": {
            "dims": ["region", "order_type"],
            "measures": ["order_nbr", "ord_qty"],
            "pii": ["regional_manager"],
        },
        "queries": {
            "by_region": {
                "label": "Orders by region and type",
                "sql": "SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY region, order_type ORDER BY total_qty DESC",
                "triggers": ["region", "area", "geography", "where", "location", "by region"],
            },
            "by_type": {
                "label": "Orders by type",
                "sql": "SELECT order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY order_type ORDER BY total_qty DESC",
                "triggers": ["type", "kind", "category", "breakdown", "group"],
            },
            "totals": {
                "label": "Order totals",
                "sql": "SELECT COUNT(order_nbr) AS total_orders, SUM(ord_qty) AS total_qty FROM workspace.governed.orders",
                "triggers": ["total", "count", "how many", "sum", "overall", "all"],
            },
            "top": {
                "label": "Top orders",
                "sql": "SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY region, order_type ORDER BY total_qty DESC",
                "triggers": ["top", "largest", "biggest", "most", "highest", "best"],
            },
            "default": {
                "label": "Orders overview",
                "sql": "SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY region, order_type ORDER BY total_qty DESC",
            },
        },
    },
    "inventory": {
        "fqn": "workspace.governed.inventory",
        "icon": "📦",
        "keywords": [
            "inventory", "stock", "sku", "warehouse", "supply",
            "qoh", "quantity on hand", "product", "item", "goods",
            "cost", "value", "expensive", "cheap", "price",
        ],
        "columns": {
            "dims": ["region", "sku", "sku_description"],
            "measures": ["qoh", "qoh_cost"],
            "pii": ["regional_manager"],
        },
        "queries": {
            "by_sku": {
                "label": "Inventory by SKU",
                "sql": "SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY sku, sku_description, region ORDER BY total_cost DESC",
                "triggers": ["sku", "product", "item", "part", "description"],
            },
            "by_region": {
                "label": "Inventory by region",
                "sql": "SELECT region, COUNT(sku) AS sku_count, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY region ORDER BY total_cost DESC",
                "triggers": ["region", "area", "where", "location", "by region"],
            },
            "totals": {
                "label": "Inventory totals",
                "sql": "SELECT COUNT(DISTINCT sku) AS unique_skus, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_value FROM workspace.governed.inventory",
                "triggers": ["total", "count", "how many", "sum", "overall", "all", "value", "worth"],
            },
            "top": {
                "label": "Top inventory items by value",
                "sql": "SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY sku, sku_description, region ORDER BY total_cost DESC",
                "triggers": ["top", "most", "expensive", "highest", "largest", "biggest", "best"],
            },
            "low": {
                "label": "Lowest stock items",
                "sql": "SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY sku, sku_description, region ORDER BY total_qty ASC",
                "triggers": ["low", "lowest", "least", "minimum", "running out", "restock"],
            },
            "default": {
                "label": "Inventory overview",
                "sql": "SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY sku, sku_description, region ORDER BY total_cost DESC",
            },
        },
    },
    "shipping": {
        "fqn": "workspace.governed.shipping",
        "icon": "🚚",
        "keywords": [
            "ship", "shipping", "transit", "delivery", "deliver",
            "carrier", "logistics", "transport", "shipment",
            "status", "tracking", "in transit", "delayed",
            "intransit", "wms",
        ],
        "columns": {
            "dims": ["region", "shipping_org", "wms_shipment_status", "sku"],
            "measures": ["intransit_value"],
            "pii": ["regional_manager"],
        },
        "queries": {
            "by_status": {
                "label": "Shipping by status",
                "sql": "SELECT wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value FROM workspace.governed.shipping GROUP BY wms_shipment_status ORDER BY total_value DESC",
                "triggers": ["status", "state", "progress", "tracking", "delayed", "pending"],
            },
            "by_region": {
                "label": "Shipping by region",
                "sql": "SELECT region, shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value FROM workspace.governed.shipping GROUP BY region, shipping_org, wms_shipment_status ORDER BY total_value DESC",
                "triggers": ["region", "area", "where", "location", "by region"],
            },
            "by_carrier": {
                "label": "Shipping by carrier",
                "sql": "SELECT shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value FROM workspace.governed.shipping GROUP BY shipping_org, wms_shipment_status ORDER BY total_value DESC",
                "triggers": ["carrier", "org", "company", "shipper", "shipping_org"],
            },
            "totals": {
                "label": "Shipping totals",
                "sql": "SELECT COUNT(sku) AS total_shipments, SUM(intransit_value) AS total_transit_value FROM workspace.governed.shipping",
                "triggers": ["total", "count", "how many", "sum", "overall", "all", "value"],
            },
            "default": {
                "label": "Shipping overview",
                "sql": "SELECT region, shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value FROM workspace.governed.shipping GROUP BY region, shipping_org, wms_shipment_status ORDER BY total_value DESC",
            },
        },
    },
}

# ── Cross-table summary for truly generic questions ──────────────────
_CROSS_TABLE_QUERIES = [
    ("🌍 Orders", "SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY region, order_type ORDER BY total_qty DESC LIMIT 10"),
    ("📦 Inventory", "SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost FROM workspace.governed.inventory GROUP BY sku, sku_description, region ORDER BY total_cost DESC LIMIT 10"),
    ("🚚 Shipping", "SELECT region, shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value FROM workspace.governed.shipping GROUP BY region, shipping_org, wms_shipment_status ORDER BY total_value DESC LIMIT 10"),
]

_GENERIC_TRIGGERS = [
    "show", "give", "tell", "what", "data", "dashboard", "report",
    "summary", "overview", "help", "info", "information", "everything",
    "hi", "hello", "hey",
]


# ── Connection helpers ───────────────────────────────────────────────
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
        return False, [], "Missing Databricks credentials in environment"
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
        return False, [], f"Databricks: {e}"


# ── Intent detection ─────────────────────────────────────────────────
def _detect_table(lower: str) -> str | None:
    """Score each table by how many keywords match the prompt."""
    scores = {}
    for tname, meta in _TABLES.items():
        score = sum(1 for kw in meta["keywords"] if kw in lower)
        if score > 0:
            scores[tname] = score
    if not scores:
        return None
    return max(scores, key=scores.get)


def _detect_query_shape(lower: str, table_meta: dict) -> str:
    """Within a table, pick the best query template based on trigger words."""
    best_shape = "default"
    best_score = 0
    for shape, qinfo in table_meta["queries"].items():
        if shape == "default":
            continue
        triggers = qinfo.get("triggers", [])
        score = sum(1 for t in triggers if t in lower)
        if score > best_score:
            best_score = score
            best_shape = shape
    return best_shape


def _build_cross_table_response(limit: int) -> ChatResult:
    """For generic questions, query all three tables and combine results."""
    all_rows = []
    sections = []
    combined_sql = []

    for label, sql in _CROSS_TABLE_QUERIES:
        sql_with_limit = sql if "LIMIT" in sql else f"{sql} LIMIT {min(limit, 10)}"
        ok, rows, err = _run_query(sql_with_limit)
        combined_sql.append(f"-- {label}\n{sql_with_limit}")
        if ok and rows:
            sections.append(f"{label}: **{len(rows)} rows**")
            all_rows.extend(rows[:5])
        elif not ok:
            sections.append(f"{label}: ❌ {err[:50]}")

    if all_rows:
        msg = (
            "📋 **Cross-table summary** (from all governed tables)\n\n"
            + " | ".join(sections) + "\n\n"
            "✅ Showing top results from each table. Ask about a specific table for more detail:\n"
            "- *\"Show me orders by region\"*\n"
            "- *\"What are the inventory levels?\"*\n"
            "- *\"Shipping status breakdown\"*"
        )
        source = "databricks (cross-table)"
    else:
        msg = "❌ Could not fetch data from Databricks."
        source = "error"

    return ChatResult(
        can_answer=bool(all_rows),
        assistant_text=msg,
        sql="\n\n".join(combined_sql),
        policy_note=f"Source: {source} • governed views • masked PII • SELECT-only",
        preview_rows=all_rows[:20],
    )


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

    # 2. Detect which table the user is asking about
    table_name = _detect_table(lower)

    # 3. If no table matched, try a cross-table summary
    if table_name is None:
        return _build_cross_table_response(limit)

    # 4. Pick the best query shape within the matched table
    meta = _TABLES[table_name]
    shape = _detect_query_shape(lower, meta)
    qinfo = meta["queries"][shape]

    sql = qinfo["sql"]
    if "LIMIT" not in sql:
        sql = f"{sql} LIMIT {limit}"
    else:
        # Replace existing LIMIT with our limit
        import re
        sql = re.sub(r"LIMIT \d+", f"LIMIT {limit}", sql)

    label_text = qinfo["label"]
    icon = meta["icon"]

    # 5. Execute
    ok, rows, err = _run_query(sql)

    if ok and rows:
        msg = (
            f"{icon} **{label_text}** (from `{meta['fqn']}`)\n\n"
            f"✅ **{len(rows)} rows** returned live from Databricks."
        )
        source = "databricks"
    elif ok and not rows:
        msg = f"{icon} **{label_text}** — Query returned 0 rows."
        source = "databricks (empty)"
    else:
        msg = f"{icon} **{label_text}** — ❌ Error: {err}"
        source = f"error: {err[:60]}"

    policy_note = (
        f"Source: {source} • governed views • masked PII • SELECT-only • LIMIT {limit}"
        + (" • safe mode" if safe_mode else "")
    )

    return ChatResult(
        can_answer=ok,
        assistant_text=msg,
        sql=sql,
        policy_note=policy_note,
        preview_rows=rows[:20] if rows else [],
    )