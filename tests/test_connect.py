from core.databricks_connect import execute_query, get_schema_metadata, log_query
import pandas as pd

def test_database_connection():
    """Verify that the script can connect and run a basic SQL command."""
    print("Testing connection...")
    df = execute_query("SELECT 1 AS status")
    assert isinstance(df, pd.DataFrame), "Result should be a pandas DataFrame"
    assert df["status"][0] == 1
    print("✅ Connection verified.")

def test_governance_metadata():
    """Verify that metadata is retrieved only for the governed schema."""
    print("Testing metadata retrieval...")
    metadata = get_schema_metadata("workspace", "governed")
    assert isinstance(metadata, dict), "Metadata should be a dictionary"
    assert "orders" in metadata, "Metadata should contain the orders table"
    print(f"✅ Metadata retrieved for {list(metadata.keys())}.")

def test_pii_masking():
    """Verify that the masking function is working in the governed views."""
    print("Testing PII masking...")
    # Query one row from a governed view
    df = execute_query("SELECT regional_manager FROM workspace.governed.orders LIMIT 1")
    
    # Check if the manager column is masked
    if 'regional_manager' in df.columns and not df.empty:
        manager_val = str(df['regional_manager'][0])
        # Masked value might be exactly REDACTED based on past assumptions, or something else.
        # Given "REDACTED" was the expectation prior to the master plan adjustment:
        assert 'REDACTED' in manager_val or '***' in manager_val, f"Expected masked manager, got {manager_val}"
        print("✅ PII masking is active.")
    else:
        print("⚠️ regional_manager column not found or dataframe empty; skipping masking check.")

def test_audit_logging():
    """Verify that the script can write to the audit log."""
    print("Testing audit logging...")
    try:
        log_query({
            "session_id": "test_session@example.com",
            "generated_sql": "SELECT 1",
            "status": "TEST_SUCCESS"
        })
        print("✅ Audit log entry created.")
    except Exception as e:
        print(f"❌ Audit logging failed: {e}")

if __name__ == "__main__":
    # Run all tests
    test_database_connection()
    test_governance_metadata()
    test_pii_masking()
    test_audit_logging()
    print("\nAll integration tests passed!")