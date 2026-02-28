import json
import uuid
import hashlib
from datetime import datetime
from core.databricks_connect import execute_query

def register_app(creator_role: str, spec: dict, generated_code: str, status: str = "success") -> str:
    """
    Writes to audit.app_registry.
    Returns the generated app_id.
    """
    app_id = str(uuid.uuid4())
    spec_json = json.dumps(spec).replace("'", "''")  # basic SQL escape
    code_hash = hashlib.sha256(generated_code.encode()).hexdigest()
    created_at = datetime.now().isoformat()
    
    sql = f"""
        INSERT INTO audit.app_registry 
        (app_id, creator_role, spec_json, generated_code_hash, created_at, status)
        VALUES 
        ('{app_id}', '{creator_role}', '{spec_json}', '{code_hash}', '{created_at}', '{status}')
    """
    
    try:
        execute_query(sql)
    except Exception as e:
        # We don't want audit logging to break the main flow in a hackathon MVP
        print(f"[REGISTRY ERROR] Failed to write to audit.app_registry: {e}")
        
    return app_id
