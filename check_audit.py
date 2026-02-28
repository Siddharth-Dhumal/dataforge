import pandas as pd
from core.databricks_connect import get_audit_feed

try:
    df = get_audit_feed(limit=5)
    print("Audit feed results:")
    print(df)
    if not df.empty and "error" in df.columns:
        print(f"Error reading audit feed: {df['error'].iloc[0]}")
except Exception as e:
    print(f"Exception calling get_audit_feed: {e}")
