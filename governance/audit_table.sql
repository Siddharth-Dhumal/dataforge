CREATE TABLE IF NOT EXISTS workspace.audit.query_log (
    user_email STRING,
    generated_sql STRING,
    execution_status STRING,
    timestamp TIMESTAMP
) USING DELTA;
