"""
Chat engine that generates governed SQL and executes it against Databricks.
Connects directly to Databricks — no wrappers, no caching, no silent fallbacks.
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


_BLOCKED_TERMS = [
    "email", "phone", "ssn", "address", "password",
    "credit card", "card number",
]


def _ensure_env():
    """Load .env if Databricks vars aren't set yet."""
    if not os.environ.get("DATABRICKS_HOST"):
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_path)
        logger.info(f"Loaded .env from {env_path}")


def _clean_value(v):
    """Convert Decimal and other non-serializable types to plain Python types."""
    if isinstance(v, Decimal):
        return float(v)
    return v


def _run_query(sql: str) -> Tuple[bool, List[Dict], str]:
    """
    Execute SQL directly against Databricks.
    Returns (success, rows_as_dicts, error_message).
    """
    _ensure_env()

    host = os.environ.get("DATABRICKS_HOST", "")
    http_path = os.environ.get("DATABRICKS_HTTP_PATH", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")

    if not host or not http_path or not token:
        return False, [], "Missing DATABRICKS_HOST, DATABRICKS_HTTP_PATH, or DATABRICKS_TOKEN in environment"

    # Validate query via guardrails
    try:
        from utils.query_validator import validate_query
        validated_sql = validate_query(sql)
    except Exception as e:
        return False, [], f"Query validation failed: {e}"

    # Execute against Databricks
    try:
        from databricks import sql as dbsql
        conn = dbsql.connect(
            server_hostname=host,
            http_path=http_path,
            access_token=token,
        )
        cursor = conn.cursor()
        cursor.execute(validated_sql)

        if not cursor.description:
            cursor.close()
            conn.close()
            return True, [], ""

        columns = [desc[0] for desc in cursor.description]
        raw_rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Convert to list of dicts with clean types
        rows = []
        for raw in raw_rows:
            row = {}
            for col, val in zip(columns, raw):
                row[col] = _clean_value(val)
            rows.append(row)

        return True, rows, ""

    except Exception as e:
        return False, [], f"Databricks query error: {e}"


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

    # Block PII requests
    if any(t in lower for t in _BLOCKED_TERMS):
        return ChatResult(
            can_answer=False,
            assistant_text=(
                "**BLOCKED** — I can't help with sensitive fields like emails, phone numbers, or SSNs.\n\n"
                "Try asking about:\n"
                "- Orders by region\n"
                "- Inventory stock levels\n"
                "- Shipping status"
            ),
            sql="-- BLOCKED: request involves sensitive/PII fields",
            policy_note="🛡️ Blocked by governance: request touches sensitive fields.",
            preview_rows=[],
        )

    # Intent router — map queries to real governed table SQL
    wants_region = "region" in lower
    wants_order = "order" in lower
    wants_inventory = "inventory" in lower or "stock" in lower or "sku" in lower
    wants_shipping = "ship" in lower or "transit" in lower
    wants_top = "top" in lower

    limit = 50 if safe_mode else 500

    if wants_inventory:
        sql = (
            f"SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost "
            f"FROM workspace.governed.inventory "
            f"GROUP BY sku, sku_description, region "
            f"ORDER BY total_cost DESC "
            f"LIMIT {limit}"
        )
        label = "📦 **Inventory levels by SKU and region** (from `governed.inventory`)"
    elif wants_shipping:
        sql = (
            f"SELECT region, shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value "
            f"FROM workspace.governed.shipping "
            f"GROUP BY region, shipping_org, wms_shipment_status "
            f"ORDER BY total_value DESC "
            f"LIMIT {limit}"
        )
        label = "🚚 **Shipping status by region and carrier** (from `governed.shipping`)"
    elif wants_region:
        sql = (
            f"SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty "
            f"FROM workspace.governed.orders "
            f"GROUP BY region, order_type "
            f"ORDER BY total_qty DESC "
            f"LIMIT {limit}"
        )
        label = "🌍 **Orders by region and type** (from `governed.orders`)"
    elif wants_order or wants_top:
        sql = (
            f"SELECT order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty "
            f"FROM workspace.governed.orders "
            f"GROUP BY order_type "
            f"ORDER BY total_qty DESC "
            f"LIMIT {limit}"
        )
        label = "📊 **Orders by type** (from `governed.orders`)"
    else:
        sql = (
            f"SELECT region, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty "
            f"FROM workspace.governed.orders "
            f"GROUP BY region "
            f"ORDER BY total_qty DESC "
            f"LIMIT {limit}"
        )
        label = "📋 **Orders summary by region** (from `governed.orders`)"

    # Execute against Databricks
    ok, rows, err = _run_query(sql)

    if ok and rows:
        msg = f"{label}\n\n✅ **{len(rows)} rows** returned live from Databricks (governed views, PII masked)."
        source = "databricks"
    elif ok and not rows:
        msg = f"{label}\n\n⚠️ Query returned 0 rows."
        source = "databricks (empty)"
    else:
        msg = f"{label}\n\n❌ **Databricks error:** {err}"
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