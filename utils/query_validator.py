import re
from utils.yaml_loader import load_guardrails

class ValidationError(Exception):
    """Exception raised when a query violates guardrails."""
    pass

def validate_query(sql: str) -> str:
    """
    Validates a SQL query against the banned patterns in guardrails.yaml.
    Enforces that the query is a SELECT statement and appends a LIMIT if necessary.
    """
    guardrails = load_guardrails()
    sql_upper = sql.upper().strip()
    
    if not sql_upper.startswith("SELECT"):
        raise ValidationError("Only SELECT queries are allowed.")
    
    banned_patterns = guardrails.get("banned_sql_patterns", [])
    for pattern in banned_patterns:
        # Check for exact 'SELECT *' match
        if pattern == "SELECT *":
            # regex for SELECT * with possible spaces
            if re.search(r'\bSELECT\s+\*', sql_upper):
                raise ValidationError("SELECT * is not allowed. Please specify columns.")
        else:
            # Word boundary check for other keywords like DROP, DELETE, etc.
            if re.search(r'\b' + re.escape(pattern) + r'\b', sql_upper):
                raise ValidationError(f"Banned SQL pattern detected: {pattern}")
    
    # Check and enforce LIMIT
    max_rows = guardrails.get("max_rows_returned", 10000)
    limit_match = re.search(r'\bLIMIT\s+(\d+)\b', sql_upper)
    
    if limit_match:
        current_limit = int(limit_match.group(1))
        if current_limit > max_rows:
            # Replace the limit with the maximum allowed
            sql = re.sub(r'(?i)(\bLIMIT\s+)\d+', fr'\g<1>{max_rows}', sql)
    else:
        # Append LIMIT if missing
        # Remove trailing semicolons and whitespace before appending
        sql = sql.rstrip("; \t\n\r") + f" LIMIT {max_rows}"

    return sql
