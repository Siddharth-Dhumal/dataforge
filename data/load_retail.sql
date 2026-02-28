-- data/load_retail.sql
CREATE TABLE IF NOT EXISTS workspace.raw.sales (
    transaction_id INT,
    date DATE,
    store_id STRING,
    amount DECIMAL(10,2),
    region STRING
) USING DELTA;

-- COPY INTO command or explicit inserts to fall back on if required
-- COPY INTO workspace.raw.sales FROM 'dbfs:/path/to/backup/retail_sales.csv' FILEFORMAT = CSV FORMAT_OPTIONS ('header' = 'true');
