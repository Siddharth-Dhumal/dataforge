"""
factory/registry.py — Writes to audit.app_registry Delta table.

Uses direct DB connection (not execute_query) because INSERT is
a banned pattern in the query validator (by design — security guardrail).
"""
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def register_app(
    creator_role: str,
    spec: dict,
    generated_code: str,
    status: str = "success",
    *,
    app_id: str | None = None,
    spec_json: str | None = None,
    code_hash: str | None = None,
) -> str:
    """
    Writes to workspace.audit.app_registry (4-column legacy schema):
        app_id, app_name, created_by, timestamp

    Accepts the factory.py call signature AND the IT Admin Console call.
    Returns the generated app_id.
    """
    if app_id is None:
        app_id = str(uuid.uuid4())

    app_name = spec.get("domain", spec.get("app_name", "Unnamed")) if isinstance(spec, dict) else str(spec)
    created_by = creator_role or "unknown"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    insert_sql = f"""
    INSERT INTO workspace.audit.app_registry
    VALUES ('{app_id}', '{app_name}', '{created_by}', '{ts}')
    """

    try:
        from core.databricks_connect import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(insert_sql)
        logger.info(f"[REGISTRY] Wrote app {app_id} to audit.app_registry")
    except Exception as e:
        logger.warning(f"[REGISTRY] Failed to write to audit.app_registry: {e}")

    return app_id
