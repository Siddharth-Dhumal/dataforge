"""
Chat engine that generates governed SQL and executes it against Databricks.
Falls back to demo data if Databricks is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def _try_real_query(sql: str) -> tuple[bool, list[dict]]:
    """Try to execute SQL against Databricks. Returns (success, rows)."""
    try:
        from core.databricks_connect import execute_query
        df = execute_query(sql)
        if "error" in df.columns:
            return False, []
        return True, df.to_dict("records")
    except Exception:
        return False, []


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
        sql = "-- CANNOT_ANSWER (request may involve sensitive fields; governed policy blocks this)"
        note = "Blocked by governance: request touches sensitive fields. Use aggregated questions (revenue, orders, trends)."
        return ChatResult(
            can_answer=False,
            assistant_text=(
                "CANNOT_ANSWER\n\n"
                "I can't help with sensitive fields. Ask about aggregates like orders by region, inventory levels, or shipping status."
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
        msg = "Here's the current inventory breakdown by SKU and region."
    elif wants_shipping:
        sql = (
            f"SELECT region, shipping_org, wms_shipment_status, COUNT(sku) AS shipment_count, SUM(intransit_value) AS total_value\n"
            f"FROM workspace.governed.shipping\n"
            f"GROUP BY region, shipping_org, wms_shipment_status\n"
            f"ORDER BY total_value DESC\n"
            f"LIMIT {limit}"
        )
        msg = "Here's the shipping status breakdown by region and carrier."
    elif wants_region:
        sql = (
            f"SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty\n"
            f"FROM workspace.governed.orders\n"
            f"GROUP BY region, order_type\n"
            f"ORDER BY total_qty DESC\n"
            f"LIMIT {limit}"
        )
        msg = "Here are orders grouped by region and type."
    elif wants_order or wants_top:
        sql = (
            f"SELECT order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty\n"
            f"FROM workspace.governed.orders\n"
            f"GROUP BY order_type\n"
            f"ORDER BY total_qty DESC\n"
            f"LIMIT {limit}"
        )
        msg = "Here are orders grouped by type."
    else:
        sql = (
            f"SELECT region, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty\n"
            f"FROM workspace.governed.orders\n"
            f"GROUP BY region\n"
            f"ORDER BY total_qty DESC\n"
            f"LIMIT {limit}"
        )
        msg = (
            "I can help with governed analytics. Try:\n"
            "- \"Orders by region\"\n"
            "- \"Inventory levels by SKU\"\n"
            "- \"Shipping status by region\""
        )

    # Try real Databricks query if not in demo mode
    preview = []
    data_source = "demo"
    if not demo_mode:
        ok, rows = _try_real_query(sql)
        if ok and rows:
            preview = rows[:20]
            data_source = "databricks"
            # Build a summary from real data
            if preview:
                msg += f"\n\n📊 **{len(preview)} rows returned from Databricks** (governed views, masked PII)."
    
    # Fallback to demo data
    if not preview:
        preview = _aggregate_by_key(days=days, seed=seed, key="region")
        data_source = "demo"

    policy_note = (
        "Allowed: governed views only • masked columns • SELECT-only • LIMIT enforced"
        + (f" • source: {data_source}" if data_source else "")
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


def _aggregate_by_key(*, days: int, seed: int, key: str) -> List[Dict]:
    rows = build_sales_rows(days=days, seed=seed)
    agg: Dict[str, float] = {}
    for r in rows:
        k = str(r[key])
        agg[k] = agg.get(k, 0.0) + float(r["revenue"])
    out = [{"key": k, "revenue": round(v, 2)} for k, v in agg.items()]
    out.sort(key=lambda x: x["revenue"], reverse=True)
    return out[:10]


def _aggregate_combo(*, days: int, seed: int) -> List[Dict]:
    rows = build_sales_rows(days=days, seed=seed)
    agg: Dict[Tuple[str, str], Dict[str, float]] = {}
    for r in rows:
        k = (str(r["region"]), str(r["product_line"]))
        if k not in agg:
            agg[k] = {"revenue": 0.0, "orders": 0.0}
        agg[k]["revenue"] += float(r["revenue"])
        agg[k]["orders"] += float(r["orders"])
    out = [
        {"region": k[0], "product_line": k[1], "revenue": round(v["revenue"], 2), "orders": int(v["orders"])}
        for k, v in agg.items()
    ]
    out.sort(key=lambda x: x["revenue"], reverse=True)
    return out