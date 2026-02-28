import logging
from typing import Dict, Any, Tuple

from factory.intent_parser import parse_intent
from factory.spec_validator import validate_spec
from factory.code_generator import generate_code
from factory.dynamic_renderer import render_dynamic_app
from factory.registry import register_app

logger = logging.getLogger(__name__)

def run_factory_pipeline(user_description: str, user_role: str) -> Tuple[bool, str, Dict[str, Any], str]:
    """
    Executes the full application factory pipeline end-to-end.
    Returns: (success_bool, message, final_spec, generated_code)
    """
    logger.info("Starting factory pipeline...")
    
    # Step 1: Parse Intent
    try:
        raw_spec = parse_intent(user_description)
    except Exception as e:
        return False, f"Failed to parse intent: {e}", {}, ""
        
    # Step 2: Validate Spec & Apply Governance
    try:
        validated_spec, violations = validate_spec(raw_spec, user_role)
    except Exception as e:
        return False, f"Governance validation failed: {e}", raw_spec, ""
        
    # Step 3: Generate Code
    generated_code, err = generate_code(validated_spec)
    if err:
        return False, f"Code generation failed: {err}", validated_spec, ""
        
    # Step 4: Dynamic Render Setup
    try:
        render_dynamic_app(validated_spec, generated_code)
    except Exception as e:
        # In a test environment without streamlit session_state, this may throw
        logger.warning(f"Could not update Streamlit session state: {e}")
        
    # Step 5: Registry Audit
    try:
        register_app(user_role, validated_spec, generated_code, "success")
    except Exception as e:
        logger.warning(f"Failed to register app: {e}")
        
    success_msg = "App successfully generated!"
    if violations:
        success_msg += "\nHowever, some requests were filtered by governance:\n- " + "\n- ".join(violations)
        
    return True, success_msg, validated_spec, generated_code
