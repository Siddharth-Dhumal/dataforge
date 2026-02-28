from __future__ import annotations
from datetime import date, timedelta
import random
from typing import Dict, List, Optional

REGIONS = ["West", "Central", "East"]
PRODUCT_LINES = ["Widgets", "Gadgets", "Services"]


def mask_email(email: str) -> str:
    # Simple display mask (governance is handled by governed views in the real system).
    if "@" not in email:
        return "***"
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        return f"{name[0:1]}***@{domain}"
    return f"{name[0:2]}***@{domain}"


def build_sales_rows(days: int, seed: int) -> List[Dict]:
    rng = random.Random(seed)
    today = date.today()
    rows: List[Dict] = []

    for i in range(days):
        d = today - timedelta(days=(days - 1 - i))
        for region in REGIONS:
            for pl in PRODUCT_LINES:
                orders = rng.randint(10, 120)
                revenue = round(orders * rng.uniform(20.0, 120.0), 2)
                customers = rng.randint(max(1, orders // 2), orders)
                email = f"customer{rng.randint(1000, 9999)}@example.com"

                rows.append(
                    {
                        "date": d.isoformat(),
                        "region": region,
                        "product_line": pl,
                        "orders": orders,
                        "revenue": revenue,
                        "customers": customers,
                        "customer_email": mask_email(email),
                    }
                )

    return rows


def try_pandas_frame(rows: List[Dict]):
    try:
        import pandas as pd  # type: ignore
        return pd.DataFrame(rows)
    except Exception:
        return None