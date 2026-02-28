import sys
from datetime import datetime
from core.databricks_connect import get_db_connection, execute_query
import traceback

def test_app_registry():
    """Verify that the script can connect and insert into app_registry."""
    print("Testing app_registry connection...", flush=True)
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        app_id = "test_app_123"
        app_name = "Hackathon Test App"
        created_by = "test_user@example.com"
        
        insert_sql = f"""
        INSERT INTO workspace.audit.app_registry 
        VALUES ('{app_id}', '{app_name}', '{created_by}', '{ts}')
        """
        
        print(f"Sql to run: {insert_sql}", flush=True)
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(insert_sql)
        print("✅ Insert successful.", flush=True)
        
        print("Reading from app_registry...", flush=True)
        df = execute_query("SELECT app_id, app_name, created_by, timestamp FROM workspace.audit.app_registry ORDER BY timestamp DESC LIMIT 5")
        if not df.empty and "error" in df.columns:
            print(f"❌ Read failed: {df['error'].iloc[0]}", flush=True)
            assert False, f"Read failed: {df['error'].iloc[0]}"
        else:
            print("✅ Read successful. Latest records:", flush=True)
            print(df, flush=True)
            assert not df.empty, "Dataframe is unexpectedly empty"
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        raise e

if __name__ == "__main__":
    test_app_registry()
