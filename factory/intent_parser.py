import logging
from typing import Dict, Any

from utils.llm import call_claude

logger = logging.getLogger(__name__)

INTENT_PARSER_SYSTEM_PROMPT = """
You are the DataForge intent parser.
Your job is to take a business user's plain English description of a data application and convert it into a structured JSON application specification.
You must use the `generate_app_spec` tool to output the result.
Ensure that missing fields get safe, reasonable defaults so that a partial application can still be generated.
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
                "items": {"type": "string"},
                "description": "List of database tables required. Make reasonable guesses based on the domain if not explicitly mentioned."
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

def parse_intent(user_description: str) -> Dict[str, Any]:
    """
    Parses a user's natural language description into a structured app spec.
    """
    result = call_claude(
        system=INTENT_PARSER_SYSTEM_PROMPT,
        user_message=user_description,
        tool=INTENT_PARSER_TOOL
    )
    
    if result is None:
        logger.warning("LLM call failed, returning safe default fallback spec.")
        return apply_safe_defaults({})
        
    return apply_safe_defaults(result)
