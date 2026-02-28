import re
from utils.yaml_loader import load_guardrails


class ValidationError(Exception):
    """Exception raised when a query violates guardrails."""
    pass


def validate_query(sql: str) -> str:
    """
    Validates a SQL query against the banned patterns in guardrails.yaml.
    Enforces that the query is a SELECT statement and appends a LIMIT if necessary.
    Returns the (possibly modified) SQL string on success.
    Raises ValidationError on failure.
    """
    if not sql:
        raise ValidationError("Empty query is not allowed.")

    # Clean up markdown code fences that LLMs sometimes wrap SQL in
    sql = re.sub(r"^\s*```(?:sql|SQL)?\s*", "", sql)
    sql = re.sub(r"\s*```\s*$", "", sql)

    guardrails = load_guardrails()
    sql_upper = sql.upper().strip()

    # Must start with SELECT or WITH (to allow CTEs)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        raise ValidationError("Only SELECT queries are allowed.")

    banned_patterns = guardrails.get("banned_sql_patterns", [])
    for pattern in banned_patterns:
        # Check for exact 'SELECT *' match
        if pattern == "SELECT *":
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
            sql = re.sub(r'(?i)(\bLIMIT\s+)\d+', fr'\g<1>{max_rows}', sql)
    else:
        sql = sql.rstrip("; \t\n\r") + f" LIMIT {max_rows}"

    return sql


def is_query_valid(sql: str) -> bool:
    """
    Bool wrapper around validate_query for agents that just need a pass/fail check.
    Returns True if the query passes all guardrail checks, False otherwise.
    """
    try:
        validate_query(sql)
        return True
    except (ValidationError, Exception):
        return False
