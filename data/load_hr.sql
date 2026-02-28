-- data/load_hr.sql
CREATE TABLE IF NOT EXISTS workspace.raw.employees (
    employee_id INT,
    name STRING,
    email STRING,
    salary DECIMAL(10,2),
    region STRING
) USING DELTA;

-- COPY INTO workspace.raw.employees FROM 'dbfs:/path/to/backup/hr_employees.csv' FILEFORMAT = CSV FORMAT_OPTIONS ('header' = 'true');
