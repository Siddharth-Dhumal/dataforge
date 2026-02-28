CREATE TABLE IF NOT EXISTS workspace.audit.query_log (
    session_id STRING,
    user_role STRING,
    nl_input STRING,
    generated_sql STRING,
    sql_validated BOOLEAN,
    table_accessed STRING,
    rows_returned INT,
    agent_retried BOOLEAN,
    retry_diff STRING,
    timestamp TIMESTAMP,
    status STRING, -- success/healed/failed
    source STRING  -- chat/factory
) USING DELTA;
