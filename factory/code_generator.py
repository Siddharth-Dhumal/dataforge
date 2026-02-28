import ast
import logging
from typing import Dict, Any, Tuple
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "config" / "app_templates"

def generate_code(spec: Dict[str, Any]) -> Tuple[str, str]:
    """
    Renders Jinja2 templates based on the spec.
    Validates Python syntax using ast.parse().
    Returns: (code_string, error_message)
    Error message is empty on success.
    """
    try:
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        
        if spec.get("chatbot", False):
            template = env.get_template("chatbot_template.py.jinja")
        else:
            template = env.get_template("dashboard_template.py.jinja")
            
        rendered_code = template.render(**spec)
    except Exception as e:
        logger.error(f"Template rendering failed: {e}")
        return "", f"Template rendering failed: {str(e)}"
        
    try:
        ast.parse(rendered_code)
    except Exception as e:
        logger.error(f"Generated code syntax validation failed: {e}")
        return "", f"Syntax validation failed on generated code: {str(e)}"
        
    return rendered_code, ""
