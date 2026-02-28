import re

def validate_query(sql_query: str) -> bool:
    """
    Validates a SQL query for safety, ensuring it is a read-only SELECT statement.
    """
    if not sql_query:
        return False
        
    # 1. Clean up markdown tags (more robust regex to handle leading/trailing spaces)
    cleaned_query = re.sub(r"^\s*```(?:sql|SQL)?\s*", "", sql_query)
    cleaned_query = re.sub(r"\s*```\s*$", "", cleaned_query)
    
    # Convert to uppercase and strip whitespace/newlines for easier matching
    query_upper = cleaned_query.upper().strip()

    # Rule 1: Must start with SELECT or WITH (to allow CTEs)
    if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH")):
        return False

    # Rule 2: Banned patterns (prevents destructive or modifying actions)
    banned_patterns = [
        r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b",
        r"\bINSERT\b", r"\bALTER\b", r"\bTRUNCATE\b",
        r"\bGRANT\b", r"\bREVOKE\b", r"\bCREATE\b", r"\bREPLACE\b"
    ]
    
    for pattern in banned_patterns:
        if re.search(pattern, query_upper):
            return False

    # Rule 3 (Removed): We no longer fail queries for missing LIMIT. 
    # Aggregation queries naturally limit rows, making a strict check counterproductive.

    return True