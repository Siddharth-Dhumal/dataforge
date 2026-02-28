-- governance/grants.sql

-- Grant usages
GRANT USAGE ON SCHEMA workspace.governed TO `viewer`;
GRANT USAGE ON SCHEMA workspace.governed TO `analyst`;
GRANT USAGE ON SCHEMA workspace.governed TO `admin`;

-- Grant permissions on governed views
GRANT SELECT ON SCHEMA workspace.governed TO `viewer`;
GRANT SELECT ON SCHEMA workspace.governed TO `analyst`;
GRANT SELECT ON SCHEMA workspace.governed TO `admin`;

-- Explicitly deny access to raw schemas
DENY SELECT ON SCHEMA workspace.raw TO `viewer`;
DENY SELECT ON SCHEMA workspace.raw TO `analyst`;
DENY SELECT ON SCHEMA workspace.raw TO `admin`;
