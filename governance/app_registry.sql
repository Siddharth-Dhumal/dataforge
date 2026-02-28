CREATE TABLE IF NOT EXISTS workspace.audit.app_registry (
    app_id STRING,
    creator_role STRING,
    spec_json STRING,
    generated_code_hash STRING,
    created_at TIMESTAMP,
    status STRING
) USING DELTA;
