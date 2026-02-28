from typing import Dict, Any, Tuple, List
from utils.yaml_loader import load_guardrails, load_roles

def validate_spec(spec: Dict[str, Any], user_role: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Checks the spec against guardrails and roles.
    Removes violations with reasons rather than throwing exceptions.
    Returns: (cleaned_spec, list_of_violation_reasons)
    """
    try:
        guardrails = load_guardrails()
        roles = load_roles()
    except Exception as e:
        # Fallback if config is broken
        return spec, [f"Could not load governance configs: {e}. Passing spec as-is but warnings apply."]

    violations = []
    cleaned_spec = spec.copy()
    
    # Ensure role exists, default to 'viewer' for maximum safety
    if user_role not in roles:
        violations.append(f"Role '{user_role}' not recognized. Defaulting to 'viewer' restrictions.")
        role_config = roles.get("viewer", {"allowed_tables": []})
    else:
        role_config = roles[user_role]
        
    allowed_tables_for_role = role_config.get("allowed_tables", [])
    allowed_tables_global = guardrails.get("allowed_tables", [])
    allowed_charts_global = guardrails.get("allowed_chart_types", [])
    
    # 1. Check Tables
    valid_tables = []
    if "tables" in cleaned_spec:
        for t in cleaned_spec["tables"]:
            if t not in allowed_tables_global:
                violations.append(f"Table '{t}' was removed because it is not an approved governed table.")
            elif allowed_tables_for_role != "all" and t not in allowed_tables_for_role:
                violations.append(f"Table '{t}' was removed because your role '{user_role}' does not have access to it.")
            else:
                valid_tables.append(t)
        cleaned_spec["tables"] = valid_tables
        
    # 2. Check Charts
    valid_charts = []
    if "charts" in cleaned_spec:
        for c in cleaned_spec["charts"]:
            if c not in allowed_charts_global:
                violations.append(f"Chart type '{c}' was removed because it is not supported by the platform.")
            else:
                valid_charts.append(c)
        cleaned_spec["charts"] = valid_charts
        
    return cleaned_spec, violations
