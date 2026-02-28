import logging
import re
from typing import Dict, Any

from utils.llm import call_claude

logger = logging.getLogger(__name__)

INTENT_PARSER_SYSTEM_PROMPT = """
You are the DataForge intent parser.
Your job is to take a business user's plain English description of a data application and convert it into a structured JSON application specification.
You must use the `generate_app_spec` tool to output the result.
Ensure that missing fields get safe, reasonable defaults so that a partial application can still be generated.

IMPORTANT: You can ONLY use these governed tables (use the exact names below):

1. governed.orders — columns: order_nbr (STRING), regional_manager (STRING, PII-masked), order_type (STRING), ord_qty (DECIMAL), region (STRING)
2. governed.inventory — columns: regional_manager (STRING, PII-masked), sku (STRING), sku_description (STRING), qoh (DECIMAL), qoh_cost (DECIMAL), region (STRING)
3. governed.shipping — columns: region (STRING), regional_manager (STRING, PII-masked), shipping_org (STRING), ship_date_ts (STRING), wms_shipment_status (STRING), sku (STRING), intransit_value (DECIMAL)

Always use the exact table names above (e.g. 'governed.orders', not just 'orders').
The PII column 'regional_manager' is always masked via Unity Catalog.
"""

INTENT_PARSER_TOOL = {
    "name": "generate_app_spec",
    "description": "Generate a structured application specification from a natural language description.",
    "input_schema": {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "The business domain of the application (e.g., 'retail', 'supply chain', 'hr'). Default to 'general' if unclear."
            },
            "tables": {
                "type": "array",
                "items": {"type": "string", "enum": ["governed.orders", "governed.inventory", "governed.shipping"]},
                "description": "List of governed database tables to use. MUST be one of: governed.orders, governed.inventory, governed.shipping."
            },
            "kpis": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of key performance indicators (KPIs) to track."
            },
            "filters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of dimensions to filter the data by (e.g., 'date', 'region', 'category')."
            },
            "charts": {
                "type": "array",
                "items": {"type": "string", "enum": ["bar", "line", "scatter", "heatmap", "pie"]},
                "description": "List of chart types to include in the dashboard."
            },
            "chatbot": {
                "type": "boolean",
                "description": "Whether to include a conversational chatbot interface."
            }
        },
        "required": ["domain", "tables", "kpis", "filters", "charts"]
    }
}

# Known governed tables and their metadata for smart fallback
KNOWN_TABLES = {
    "orders": {
        "full_name": "governed.orders",
        "columns": ["order_nbr", "regional_manager", "order_type", "ord_qty", "region"],
        "kpis": ["Total Orders", "Total Quantity", "Orders by Type"],
        "filters": ["region", "order_type"],
        "keywords": ["order", "purchase", "sales", "buy", "transaction"],
    },
    "inventory": {
        "full_name": "governed.inventory",
        "columns": ["sku", "sku_description", "qoh", "qoh_cost", "region", "regional_manager"],
        "kpis": ["Total Stock (QoH)", "Inventory Value", "SKU Count"],
        "filters": ["region", "sku"],
        "keywords": ["inventory", "stock", "warehouse", "sku", "supply"],
    },
    "shipping": {
        "full_name": "governed.shipping",
        "columns": ["shipping_org", "ship_date_ts", "wms_shipment_status", "sku", "intransit_value", "region", "regional_manager"],
        "kpis": ["Shipments In Transit", "Total Transit Value", "Delivery Rate"],
        "filters": ["region", "shipping_org", "wms_shipment_status"],
        "keywords": ["ship", "shipping", "transit", "delivery", "logistics", "carrier"],
    },
}


def apply_safe_defaults(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Applies safe defaults to any missing fields in the parsed spec."""
    return {
        "domain": spec.get("domain") or "general",
        "tables": spec.get("tables") or [],
        "kpis": spec.get("kpis") or ["Total Count"],
        "filters": spec.get("filters") or ["date"],
        "charts": spec.get("charts") or ["bar", "line"],
        "chatbot": spec.get("chatbot", False)
    }


def parse_intent_from_text(user_description: str) -> Dict[str, Any]:
    """
    Pure-Python fallback parser — extracts intent from user text using keyword matching
    against known governed tables. Used when the AI API is unavailable.
    """
    lower = user_description.lower()
    
    # Find matching tables
    matched_tables = []
    all_kpis = []
    all_filters = set()
    
    for table_key, meta in KNOWN_TABLES.items():
        if any(kw in lower for kw in meta["keywords"]):
            matched_tables.append(meta["full_name"])
            all_kpis.extend(meta["kpis"])
            all_filters.update(meta["filters"])
    
    # If no tables matched, default to orders
    if not matched_tables:
        meta = KNOWN_TABLES["orders"]
        matched_tables = [meta["full_name"]]
        all_kpis = meta["kpis"]
        all_filters = set(meta["filters"])
    
    # Detect domain
    domain = "general"
    if any(w in lower for w in ["supply", "inventory", "warehouse", "logistics"]):
        domain = "supply_chain"
    elif any(w in lower for w in ["sale", "revenue", "customer", "retail"]):
        domain = "retail"
    elif any(w in lower for w in ["ship", "delivery", "transit"]):
        domain = "logistics"
    elif any(w in lower for w in ["order", "purchase"]):
        domain = "operations"
    
    # Detect chart types from text
    charts = ["bar", "line"]
    if "pie" in lower or "breakdown" in lower:
        charts.append("pie")
    if "scatter" in lower or "correlation" in lower:
        charts.append("scatter")
    if "heat" in lower:
        charts.append("heatmap")
    
    # Detect mask columns
    mask_cols = []
    if "mask" in lower and "regional" in lower:
        mask_cols.append("regional_manager")
    elif "mask" in lower:
        mask_cols.append("regional_manager")  # Default PII column
    
    # Detect chatbot
    chatbot = "chat" in lower or "conversational" in lower or "ask" in lower
    
    # Extract app name from first meaningful phrase
    app_name = "Dashboard"
    name_patterns = [
        r"build (?:a |an )?(.*?)(?:dashboard|app|application)",
        r"create (?:a |an )?(.*?)(?:dashboard|app|application)",
        r"(.*?)(?:dashboard|app|analytics)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, lower)
        if match:
            name = match.group(1).strip().title()
            if name and len(name) > 2:
                app_name = name + " Dashboard"
                break
    
    return {
        "app_name": app_name,
        "domain": domain,
        "tables": matched_tables,
        "kpis": all_kpis[:5],
        "filters": list(all_filters),
        "charts": charts,
        "chatbot": chatbot,
        "mask_columns": mask_cols,
    }


def parse_intent(user_description: str) -> Dict[str, Any]:
    """
    Parses a user's natural language description into a structured app spec.
    Tries AI first, falls back to keyword-based parsing.
    """
    result = call_claude(
        system=INTENT_PARSER_SYSTEM_PROMPT,
        user_message=user_description,
        tool=INTENT_PARSER_TOOL
    )
    
    if result is not None:
        spec = apply_safe_defaults(result)
        spec["source"] = "ai"
        return spec
    
    # AI unavailable — use smart keyword fallback
    logger.warning("LLM call failed, using keyword-based intent parser.")
    spec = parse_intent_from_text(user_description)
    spec["source"] = "keyword_fallback"
    return spec
