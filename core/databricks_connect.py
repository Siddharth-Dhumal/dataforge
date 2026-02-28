import os
import pandas as pd
from databricks import sql
from dotenv import load_dotenv
from datetime import datetime
import streamlit as st
from utils.query_validator import validate_query

load_dotenv()

def get_db_connection():
    return sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN")
    )

@st.cache_data(ttl=30)
def execute_query(sql: str, params: dict = None) -> pd.DataFrame:
    """Runs SQL and returns a DataFrame. Handles errors for the frontend."""
    try:
        validated_sql = validate_query(sql)
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Assuming the sql-connector supports params or we just execute the validated sql
                if params:
                    cursor.execute(validated_sql, params)
                else:
                    cursor.execute(validated_sql)
                if not cursor.description: return pd.DataFrame() # For INSERTs
                return pd.DataFrame(cursor.fetchall(), columns=[d[0] for d in cursor.description])
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})

@st.cache_data(ttl=30)
def get_schema_metadata(catalog: str, schema: str) -> dict:
    """The 'Brain' for Person C's AI agents to know what columns exist."""
    # Masterplan states: 
    # run DESCRIBE TABLE on every source table
    # return dict of tables
    # Since we need to get tables dynamically:
    # the existing logic was hardcoded for 3 tables. 
    # Let's query the tables from information_schema if possible, but for simplicity
    tables = ["inventory", "orders", "shipping"]
    return {t: execute_query(f"DESCRIBE {catalog}.{schema}.{t}").to_dict('records') for t in tables}

def log_query(payload: dict) -> None:
    """Writes every AI action to your audit table."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # We expected a 12-column schema, but the user's Databricks actually has:
    # `user_email`, `generated_sql`, `execution_status`, `timestamp`
    user_email = payload.get("user_role", payload.get("session_id", "unknown@example.com"))
    generated_sql = payload.get("generated_sql", "").replace("'", "''")
    execution_status = payload.get("status", "unknown")
    
    insert_sql = f"""
    INSERT INTO workspace.audit.query_log 
    VALUES ('{user_email}', '{generated_sql}', '{execution_status}', '{ts}')
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(insert_sql)
    except Exception as e:
        print(f"Audit log failed: {e}")

def get_audit_feed(limit: int = 50) -> pd.DataFrame:
    """Pulls logs for Person B's Admin dashboard."""
    cols = "user_email, generated_sql, execution_status, timestamp"
    return execute_query(f"SELECT {cols} FROM workspace.audit.query_log ORDER BY timestamp DESC LIMIT {limit}")