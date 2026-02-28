CREATE TABLE IF NOT EXISTS workspace.audit.app_registry (
    app_id STRING,
    app_name STRING,
    created_by STRING,
    timestamp TIMESTAMP
) USING DELTA;
