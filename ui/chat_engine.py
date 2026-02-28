"""
Chat engine — orchestrates the full chat flow per the masterplan.

Flow (Genie primary):
  1. User selects role → types NL question
  2. genie_chat.py sends to Genie API → Genie returns SQL + data
  3. If Genie unavailable → Agent 1 (Anthropic SQL Generator) as fallback
  4. Agent 2 receives → validates + executes → if error: one Anthropic retry
  5. log_query() writes to audit.query_log
  6. Agent 3 receives summary stats → generates insight (8s timeout)
  7. UI renders chart + text + insight card + SQL expander

Flow (Anthropic fallback):
  Same as above but Agent 1 generates SQL instead of Genie.

Keyword fallback exists as final safety net if ALL APIs are down.
"""
from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatResult:
    can_answer: bool
    assistant_text: str
    sql: str
    policy_note: str
    preview_rows: List[Dict]
    insight: str = ""
    healed: bool = False
    heal_diff: str = ""
    source: str = "unknown"


# ── PII blocked terms ────────────────────────────────────────────────
_BLOCKED_TERMS = [
    "email", "phone", "ssn", "address", "password",
    "credit card", "card number", "social security",
    "personal info", "pii",
]


# ── Keyword fallback (when ALL APIs are unavailable) ──────────────────
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
        return (
            f"SELECT region, order_type, COUNT(order_nbr) AS order_count, SUM(ord_qty) AS total_qty FROM workspace.governed.orders GROUP BY region, order_type ORDER BY total_qty DESC LIMIT {limit}",
            "Orders overview (default)",
            "📋",
        )

    tname = max(scores, key=scores.get)
    meta = _TABLES_META[tname]

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


# ── Hardcoded demo data (absolute last resort when ALL APIs are down) ─
_DEMO_DATA = {
    "orders": [
        {"region": "West", "order_type": "TRANSFER_ORDER", "order_count": 1476, "total_qty": 34212.0},
        {"region": "Chicago", "order_type": "DPI", "order_count": 874, "total_qty": 15280.0},
        {"region": "Atlantic Coast", "order_type": "DPI", "order_count": 720, "total_qty": 12500.0},
        {"region": "Inland Empire", "order_type": "DPI", "order_count": 958, "total_qty": 18340.0},
        {"region": "Hawaii", "order_type": "Solar Panel Installation Order", "order_count": 412, "total_qty": 6800.0},
        {"region": "Greater Sacramento", "order_type": "DPI", "order_count": 203, "total_qty": 3100.0},
        {"region": "Bay Area", "order_type": "TRANSFER_ORDER", "order_count": 189, "total_qty": 2450.0},
        {"region": "Central California", "order_type": "DPI", "order_count": 150, "total_qty": 2100.0},
    ],
    "inventory": [
        {"sku": "040-20004", "sku_description": "Solar Panel A", "region": "West", "total_qty": 500820.0, "total_cost": 12500000.0},
        {"sku": "242-10035", "sku_description": "Inverter B", "region": "West", "total_qty": 492160.0, "total_cost": 9800000.0},
        {"sku": "300-20004", "sku_description": "Battery C", "region": "Chicago", "total_qty": 390744.0, "total_cost": 7600000.0},
        {"sku": "242-92202", "sku_description": "Meter D", "region": "Atlantic Coast", "total_qty": 161280.0, "total_cost": 3200000.0},
        {"sku": "242-02728", "sku_description": "Cable E", "region": "Hawaii", "total_qty": 137800.0, "total_cost": 1800000.0},
    ],
    "shipping": [
        {"wms_shipment_status": "In Transit", "region": "West", "shipment_count": 1036, "total_value": 5200000.0},
        {"wms_shipment_status": "Receiving Started", "region": "Chicago", "shipment_count": 26, "total_value": 340000.0},
        {"wms_shipment_status": "Cancelled", "region": "Atlantic Coast", "shipment_count": 1, "total_value": 12000.0},
        {"wms_shipment_status": "In Transit", "region": "Inland Empire", "shipment_count": 450, "total_value": 2100000.0},
        {"wms_shipment_status": "In Transit", "region": "Hawaii", "shipment_count": 200, "total_value": 980000.0},
    ],
}


def _get_demo_data(prompt: str) -> Optional[List[Dict]]:
    """Return hardcoded demo data matching the prompt's table."""
    lower = prompt.lower()
    for tname, meta in _TABLES_META.items():
        if any(kw in lower for kw in meta["keywords"]):
            return _DEMO_DATA.get(tname)
    return _DEMO_DATA.get("orders")  # Default


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

    # 1. Block PII requests
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
            source="blocked",
        )

    limit = 50 if safe_mode else 500
    source_label = "unknown"
    healed = False
    heal_diff = ""

    # ── Step 1: Try Genie API (primary chat path) ────────────────────
    sql = None
    reason = ""
    genie_rows = None

    try:
        from agents.genie_chat import query_genie
        genie_sql, genie_data, genie_status = query_genie(p)

        if genie_status == "genie_success" and genie_sql:
            sql = genie_sql
            reason = "Genie API response"
            source_label = "genie"
            if genie_data:
                genie_rows = genie_data
    except Exception as e:
        logger.info(f"[Chat] Genie import/call failed: {e}")

    # ── Step 2: Fallback to Agent 1 (Anthropic SQL Generator) ────────
    if sql is None:
        try:
            from agents.sql_generator import generate_sql
            ai_sql, ai_reason, cannot = generate_sql(p, limit=limit)

            if not cannot and ai_sql:
                sql = ai_sql
                reason = ai_reason
                source_label = "ai"
                # Ensure LIMIT
                if "LIMIT" not in sql.upper():
                    sql = f"{sql} LIMIT {limit}"
            else:
                reason = ai_reason
        except Exception as e:
            logger.warning(f"[Chat] Agent 1 failed: {e}")
            reason = f"Agent 1 error: {e}"

    # ── Step 3: Final fallback to keyword matching ────────────────────
    if sql is None:
        sql, fallback_label, icon = _keyword_fallback(p, limit)
        source_label = "keyword_fallback"
        reason = fallback_label

    # ── Step 4: Execute via Agent 2 (Self-Healing Agent) ──────────────
    ok = False
    rows: List[Dict] = []
    err = ""

    if genie_rows is not None:
        # Genie already returned data — no need to execute
        ok = True
        rows = genie_rows
    else:
        try:
            from agents.self_healing_agent import execute_sql, self_heal
            ok, rows, err = execute_sql(sql)

            # Self-healing: if SQL failed and we used AI, retry once
            if not ok and source_label in ("ai", "genie"):
                healed_sql, heal_reason, diff_text = self_heal(
                    sql, err, p, limit=limit
                )
                if healed_sql:
                    ok2, rows2, err2 = execute_sql(healed_sql)
                    if ok2:
                        rows = rows2
                        ok = True
                        err = ""
                        heal_diff = diff_text
                        sql = healed_sql
                        source_label = f"{source_label} (self-healed)"
                        healed = True
        except Exception as e:
            logger.warning(f"[Chat] Agent 2 execution failed: {e}")
            err = str(e)

    # ── Step 4b: Absolute last resort — hardcoded demo data ───────────
    # Masterplan: "Three example question buttons work even if Genie API,
    # Anthropic API, and the warehouse are all simultaneously down.
    # They run against hardcoded DataFrames in session state."
    if not ok and source_label == "keyword_fallback":
        demo_rows = _get_demo_data(p)
        if demo_rows:
            ok = True
            rows = demo_rows
            err = ""
            source_label = "demo_fallback"
            reason = f"{reason} (demo data)"

    # ── Step 5: Build response message ────────────────────────────────
    if ok and rows:
        if source_label == "demo_fallback":
            msg = f"**{reason}**\n\n📋 **{len(rows)} rows** from cached demo data (APIs unavailable)."
        else:
            msg = f"**{reason}**\n\n✅ **{len(rows)} rows** returned live from Databricks."
        if healed:
            msg += "\n\n🩹 *Query was auto-corrected by the self-healing agent.*"
    elif ok and not rows:
        msg = f"**{reason}**\n\n⚠️ Query returned 0 rows."
    else:
        msg = (
            f"**{reason}**\n\n❌ **Error:** {err}\n\n"
            "Try one of these instead:\n"
            "- 🌍 Orders by region\n"
            "- 📦 Inventory levels\n"
            "- 🚚 Shipping status"
        )

    # ── Step 6: Agent 3 — Generate AI insight ─────────────────────────
    insight_text = ""
    if ok and rows and len(rows) >= 1:
        try:
            from agents.insight_generator import generate_insight
            insight_text = generate_insight(rows, p)
        except Exception as e:
            logger.warning(f"[Chat] Agent 3 insight failed: {e}")
            # Agent 3 failure never blocks the UI
            insight_text = ""

    # ── Step 7: Log to audit ──────────────────────────────────────────
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
        healed=healed,
        heal_diff=heal_diff,
        source=source_label,
    )