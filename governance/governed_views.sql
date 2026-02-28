-- governance/governed_views.sql

-- Masterplan explicitly asks for parameterized queries scoping: 
-- "governed views accept a user_region parameter from the app. WHERE region = :user_region"

CREATE OR REPLACE VIEW workspace.governed.sales AS
SELECT * FROM workspace.raw.sales 
WHERE region = :user_region;

CREATE OR REPLACE VIEW workspace.governed.employees AS
SELECT * FROM workspace.raw.employees
WHERE region = :user_region;

CREATE OR REPLACE VIEW workspace.governed.customers AS
SELECT * FROM workspace.raw.customers
WHERE region = :user_region;

CREATE OR REPLACE VIEW workspace.governed.inventory AS
SELECT * FROM workspace.raw.inventory
WHERE region = :user_region;

CREATE OR REPLACE VIEW workspace.governed.products AS
SELECT * FROM workspace.raw.products;

CREATE OR REPLACE VIEW workspace.governed.shipments AS
SELECT * FROM workspace.raw.shipments
WHERE region = :user_region;
