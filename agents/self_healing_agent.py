"""
Agent 2 — Self-Healing Agent (agents/self_healing_agent.py)

Wraps both Genie API (chat path) and Agent 1 (factory path).
The only place SQL executes.

MAX_RETRIES = 1  — NEVER change this constant during the hackathon

Flow:
  1. Get SQL from Genie or Agent 1
  2. Validate through query_validator.py
  3. Execute via execute_query() or direct connection
  4. Success → return DataFrame, log status=success
  5. Failure (SQL error) → build retry prompt with original SQL + error message + schema
     → call Anthropic (tool use) → validate again → execute again
  6. Retry success → return DataFrame, log agent_retried=True,
     log difflib.unified_diff() output in retry_diff
  7. Retry fail OR cannot_answer=True → return friendly error + 3 example buttons.
     Log status=failed.

Hard rules:
  - MAX_RETRIES = 1 is a named constant. Never a magic number. Never changed.
  - All exceptions caught. Nothing propagates to the UI.
  - The diff logged on retry uses difflib.unified_diff()
"""
from __future__ import annotations

import os
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_RETRIES = 1  # NEVER change this constant during the hackathon


def _clean_value(v):
    """Convert Decimal to float for JSON serialization."""
    return float(v) if isinstance(v, Decimal) else v


def execute_sql(sql: str) -> Tuple[bool, List[Dict], str]:
    """
    Validate and execute SQL against Databricks.
    Returns (success, rows, error_message).
    All exceptions caught — nothing propagates to the UI.
    """
    # Ensure env is loaded (idempotent)
    try:
        from core.env_loader import load_env
        load_env()
    except Exception:
        pass

    host = os.environ.get("DATABRICKS_HOST", "")
    http_path = os.environ.get("DATABRICKS_HTTP_PATH", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")

    if not all([host, http_path, token]):
        return False, [], "Missing Databricks credentials"

    # Validate through query_validator.py first
    try:
        from utils.query_validator import validate_query
        validated = validate_query(sql)
    except Exception as e:
        return False, [], f"Validation error: {e}"

    # Execute
    try:
        from databricks import sql as dbsql
        conn = dbsql.connect(server_hostname=host, http_path=http_path, access_token=token)
        cur = conn.cursor()
        cur.execute(validated)
        if not cur.description:
            cur.close()
            conn.close()
            return True, [], ""
        cols = [d[0] for d in cur.description]
        raw = cur.fetchall()
        cur.close()
        conn.close()
        rows = [{c: _clean_value(v) for c, v in zip(cols, r)} for r in raw]
        return True, rows, ""
    except Exception as e:
        return False, [], str(e)


def self_heal(
    original_sql: str,
    error_msg: str,
    nl_question: str,
    *,
    limit: int = 500,
) -> Tuple[Optional[str], str, str]:
    """
    Agent 2: If the original SQL failed, retry once with error context.

    Uses Anthropic tool use pattern via call_claude.

    Returns:
        (fixed_sql_or_none, reason, diff_text)
    """
    try:
        from utils.llm import call_claude
        from agents.sql_generator import SQL_TOOL, SCHEMA_CONTEXT
        from utils.diff_util import sql_diff
    except ImportError as ie:
        logger.warning(f"[Agent 2] Import error: {ie}")
        return None, "Self-healing dependencies not available", ""

    system = (
        "You are the DataForge SQL Self-Healing Agent. A SQL query failed with an error. "
        "Fix the query based on the error message. Return a corrected query.\n\n"
        f"{SCHEMA_CONTEXT}\n"
        f"Use LIMIT {limit}.\n"
    )
    user_msg = (
        f"Original question: {nl_question}\n\n"
        f"Failed SQL:\n{original_sql}\n\n"
        f"Error: {error_msg}\n\n"
        "Please fix this SQL query."
    )

    for attempt in range(MAX_RETRIES):
        result = call_claude(system, user_msg, SQL_TOOL)
        if result is None:
            return None, "Self-healing LLM call failed", ""

        sql = result.get("sql", "")
        reason = result.get("reason", "Fixed query")

        if result.get("cannot_answer") or not sql.strip():
            return None, reason or "Cannot fix this query", ""

        fixed_sql = sql.strip()
        diff_text = sql_diff(original_sql, fixed_sql)
        return fixed_sql, reason, diff_text

    return None, "Self-healing exhausted all retries", ""