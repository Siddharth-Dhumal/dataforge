-- data/load_supply_chain.sql
CREATE TABLE IF NOT EXISTS workspace.raw.shipments (
    shipment_id INT,
    origin STRING,
    destination STRING,
    status STRING,
    region STRING
) USING DELTA;

-- COPY INTO workspace.raw.shipments FROM 'dbfs:/path/to/backup/supply_chain.csv' FILEFORMAT = CSV FORMAT_OPTIONS ('header' = 'true');
