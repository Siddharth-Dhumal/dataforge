import pandas as pd

def execute_query(sql: str, params: dict = None) -> pd.DataFrame:
    # Stub for integration testing without live warehouse
    print(f"[DB STUB] Executing: {sql[:100]}...")
    return pd.DataFrame()

def get_schema_metadata(catalog: str, schema: str) -> dict:
    return {}

def log_query(payload: dict) -> None:
    pass

def get_audit_feed(limit: int = 50) -> pd.DataFrame:
    return pd.DataFrame()
