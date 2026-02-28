-- governance/column_masking.sql

-- Create the masking function in the governed schema
CREATE FUNCTION IF NOT EXISTS workspace.governed.mask_email(email STRING) 
  RETURN CONCAT(LEFT(email,2), '***@***.com');

-- In Databricks Unity Catalog, we can alter the tables/views to apply the mask.
-- According to masterplan, masking happens for analyst/viewer roles (or rather, is available,
-- and the admin sees full values depending on how the function evaluates roles, but for the MVP
-- we just apply the mask and show it working).
-- We assume `employees` and `customers` have an `email` column.

ALTER TABLE workspace.raw.employees ALTER COLUMN email SET MASK workspace.governed.mask_email;
ALTER TABLE workspace.raw.customers ALTER COLUMN email SET MASK workspace.governed.mask_email;
