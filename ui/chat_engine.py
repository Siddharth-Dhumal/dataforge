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
    "email",
    "phone",
    "ssn",
    "address",
    "password",
    "credit card",
    "card number",
]


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
                "I can’t help with sensitive fields. Ask about aggregates like revenue by region, top products, or trends."
            ),
            sql=sql,
            policy_note=note,
            preview_rows=[],
        )

    # Very small intent router (demo-safe)
    wants_region = "region" in lower
    wants_product = "product" in lower or "product line" in lower
    wants_trend = "trend" in lower or "over time" in lower or "daily" in lower
    wants_top = "top" in lower

    limit = 50 if safe_mode else 500

    # We only “pretend” to query governed views here; Person C/A will wire real governed SQL execution.
    if wants_top and wants_product:
        sql = (
            "SELECT product_line, SUM(revenue) AS revenue\n"
            "FROM governed.sales\n"
            f"WHERE date >= date_sub(current_date(), {days})\n"
            "GROUP BY product_line\n"
            "ORDER BY revenue DESC\n"
            f"LIMIT {limit};"
        )
        preview = _aggregate_by_key(days=days, seed=seed, key="product_line")
        msg = f"Here are the top product lines by revenue for the last {days} days."
    elif wants_region or ("revenue" in lower and wants_region):
        sql = (
            "SELECT region, SUM(revenue) AS revenue\n"
            "FROM governed.sales\n"
            f"WHERE date >= date_sub(current_date(), {days})\n"
            "GROUP BY region\n"
            "ORDER BY revenue DESC\n"
            f"LIMIT {limit};"
        )
        preview = _aggregate_by_key(days=days, seed=seed, key="region")
        msg = f"Here’s revenue by region for the last {days} days."
    elif wants_trend:
        sql = (
            "SELECT date, SUM(revenue) AS revenue\n"
            "FROM governed.sales\n"
            f"WHERE date >= date_sub(current_date(), {days})\n"
            "GROUP BY date\n"
            "ORDER BY date ASC\n"
            f"LIMIT {limit};"
        )
        preview = _aggregate_by_key(days=days, seed=seed, key="date")
        msg = f"Here’s the revenue trend (daily) for the last {days} days."
    else:
        sql = (
            "SELECT region, product_line, SUM(revenue) AS revenue, SUM(orders) AS orders\n"
            "FROM governed.sales\n"
            f"WHERE date >= date_sub(current_date(), {days})\n"
            "GROUP BY region, product_line\n"
            "ORDER BY revenue DESC\n"
            f"LIMIT {limit};"
        )
        preview = _aggregate_combo(days=days, seed=seed)[:10]
        msg = (
            "I can help with governed analytics. Try:\n"
            "- “Revenue by region last 30 days”\n"
            "- “Top product lines by revenue”\n"
            "- “Revenue trend over time”"
        )

    policy_note = (
        "Allowed: governed views only • masked columns • SELECT-only • LIMIT enforced"
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