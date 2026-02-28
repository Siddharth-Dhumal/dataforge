"""
Chat engine that generates governed SQL and executes it against Databricks.
Falls back to demo data if Databricks is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from ui.demo_data import build_sales_rows


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


def _clean_row(row: dict) -> dict:
    """Convert Decimal and other non-serializable types to plain Python types."""
    cleaned = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            cleaned[k] = float(v)
        else:
            cleaned[k] = v
    return cleaned


def _try_real_query(sql: str) -> tuple[bool, list[dict], str]:
    """
    Try to execute SQL against Databricks.
    Returns (success, rows, error_message).
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from core.databricks_connect import execute_query
        df = execute_query(sql)
        if "error" in df.columns:
            return False, [], str(df["error"].iloc[0])
        rows = [_clean_row(r) for r in df.to_dict("records")]
        return True, rows, ""
    except Exception as e:
        return False, [], str(e)


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

    if any(t in lower for t in _BLOCKED_TERMS):
        sql = "-- BLOCKED: request involves sensitive/PII fields"
        note = "🛡️ Blocked by governance: request touches sensitive fields."
        return ChatResult(
            can_answer=False,
            assistant_text=(
                "**BLOCKED** — I can't help with sensitive fields like emails, phone numbers, or SSNs.\n\n"
                "Try asking about:\n"
                "- Orders by region\n"
                "- Inventory stock levels\n"
                "- Shipping status"
            ),
            sql=sql,
            policy_note=note,
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
            f"SELECT sku, sku_description, region, SUM(qoh) AS total_qty, SUM(qoh_cost) AS total_cost\n"
            f"FROM workspace.governed.inventory\n"
            f"GROUP BY sku, sku_description, region\n"
            f"ORDER BY total_cost DESC\n"
            f"LIMIT {limit}"
        )
        intent_label = "inventory"
        msg_ok = "📦 **Inventory levels by SKU and region** (from `governed.inventory`):"
    elif wants_shipping:
        sql = (
            f"SELECT region, shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value\n"
            f"FROM workspace.governed.shipping\n"
            f"GROUP BY region, shipping_org, wms_shipment_status\n"
            f"ORDER BY total_value DESC\n"
            f"LIMIT {limit}"
        )
        intent_label = "shipping"
        msg_ok = "🚚 **Shipping status by region and carrier** (from `governed.shipping`):"
    elif wants_region:
        sql = (
            f"SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty\n"
            f"FROM workspace.governed.orders\n"
            f"GROUP BY region, order_type\n"
            f"ORDER BY total_qty DESC\n"
            f"LIMIT {limit}"
        )
        intent_label = "orders_by_region"
        msg_ok = "🌍 **Orders grouped by region and type** (from `governed.orders`):"
    elif wants_order or wants_top:
        sql = (
            f"SELECT order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty\n"
            f"FROM workspace.governed.orders\n"
            f"GROUP BY order_type\n"
            f"ORDER BY total_qty DESC\n"
            f"LIMIT {limit}"
        )
        intent_label = "orders_by_type"
        msg_ok = "📊 **Orders grouped by type** (from `governed.orders`):"
    else:
        sql = (
            f"SELECT region, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty\n"
            f"FROM workspace.governed.orders\n"
            f"GROUP BY region\n"
            f"ORDER BY total_qty DESC\n"
            f"LIMIT {limit}"
        )
        intent_label = "orders_summary"
        msg_ok = "📋 **Orders summary by region** (from `governed.orders`):"

    # Try real Databricks query
    preview = []
    data_source = "demo"
    error_detail = ""

    if not demo_mode:
        ok, rows, err = _try_real_query(sql)
        if ok and rows:
            preview = rows[:20]
            data_source = "databricks"
        else:
            error_detail = err

    # Build response message
    if data_source == "databricks":
        msg = f"{msg_ok}\n\n✅ **{len(preview)} rows** returned live from Databricks."
    else:
        msg = f"{msg_ok}\n\n⚠️ Using demo data"
        if error_detail:
            msg += f" (Databricks: {error_detail[:100]})"
        # Generate query-specific demo data
        preview = _build_demo_for_intent(intent_label, days=days, seed=seed)

    policy_note = (
        f"Source: {data_source} • governed views • masked PII • SELECT-only • LIMIT {limit}"
        + (" • demo mode" if demo_mode else "")
        + (" • safe mode" if safe_mode else "")
    )

    return ChatResult(
        can_answer=True,
        assistant_text=msg,
        sql=sql,
        policy_note=policy_note,
        preview_rows=preview,
    )


def _build_demo_for_intent(intent: str, *, days: int, seed: int) -> List[Dict]:
    """Build intent-specific demo data so each query shows different columns."""
    import random
    rng = random.Random(seed)

    if intent == "inventory":
        skus = ["040-20004", "050-30001", "060-40002", "070-50003", "080-60004"]
        descs = ["PW3 DC Unit", "Solar Panel A", "Battery Pack B", "Inverter C", "Connector D"]
        regions = ["West", "Central", "East"]
        rows = []
        for sku, desc in zip(skus, descs):
            for region in regions:
                rows.append({
                    "sku": sku,
                    "sku_description": desc,
                    "region": region,
                    "total_qty": rng.randint(1000, 50000),
                    "total_cost": round(rng.uniform(10000, 500000), 2),
                })
        rows.sort(key=lambda x: x["total_cost"], reverse=True)
        return rows[:15]

    elif intent == "shipping":
        regions = ["West", "Central", "East", "Virtual Org"]
        orgs = ["CA92", "TX01", "NY03"]
        statuses = ["In Transit", "Delivered", "Pending"]
        rows = []
        for region in regions:
            for org in orgs:
                for status in statuses:
                    rows.append({
                        "region": region,
                        "shipping_org": org,
                        "wms_shipment_status": status,
                        "shipment_count": rng.randint(10, 500),
                        "total_value": round(rng.uniform(5000, 200000), 2),
                    })
        rows.sort(key=lambda x: x["total_value"], reverse=True)
        return rows[:15]

    elif intent == "orders_by_region":
        regions = ["West", "Central", "East"]
        types = ["TRANSFER_ORDER", "SALES_ORDER", "PURCHASE_ORDER", "RETURN_ORDER"]
        rows = []
        for region in regions:
            for otype in types:
                rows.append({
                    "region": region,
                    "order_type": otype,
                    "order_count": rng.randint(100, 2000),
                    "total_qty": rng.randint(5000, 300000),
                })
        rows.sort(key=lambda x: x["total_qty"], reverse=True)
        return rows

    elif intent == "orders_by_type":
        types = ["TRANSFER_ORDER", "SALES_ORDER", "PURCHASE_ORDER", "RETURN_ORDER", "INTERNAL_ORDER"]
        rows = []
        for otype in types:
            rows.append({
                "order_type": otype,
                "order_count": rng.randint(200, 3000),
                "total_qty": rng.randint(10000, 500000),
            })
        rows.sort(key=lambda x: x["total_qty"], reverse=True)
        return rows

    else:  # orders_summary
        regions = ["West", "Central", "East", "North", "South"]
        rows = []
        for region in regions:
            rows.append({
                "region": region,
                "order_count": rng.randint(500, 5000),
                "total_qty": rng.randint(50000, 500000),
            })
        rows.sort(key=lambda x: x["total_qty"], reverse=True)
        return rows