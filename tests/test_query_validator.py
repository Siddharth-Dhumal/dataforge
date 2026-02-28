import pytest
from utils.query_validator import validate_query, ValidationError

def test_valid_select():
    """Valid select queries should pass and have LIMIT appended if missing."""
    sql = "SELECT id, name FROM governed.sales"
    validated = validate_query(sql)
    assert "LIMIT 10000" in validated

def test_select_star_blocked():
    """SELECT * should be rejected."""
    with pytest.raises(ValidationError, match="SELECT \\* is not allowed"):
        validate_query("SELECT * FROM governed.sales")

def test_banned_patterns_blocked():
    """Adversarial queries with banned keywords should raise errors."""
    banned_queries = [
        "SELECT id FROM governed.sales WHERE name = 'DROP'",
        "SELECT id FROM governed.customers; DELETE FROM governed.customers WHERE id=1",
        "SELECT id FROM governed.inventory UNION UPDATE governed.inventory SET qty=0",
        "SELECT 1; INSERT INTO governed.sales (id) VALUES (1)",
        "SELECT id FROM TRUNCATE TABLE governed.shipments",
        "SELECT CREATE TABLE governed.hacked (id INT)",
        "SELECT id FROM ALTER TABLE"
    ]
    for q in banned_queries:
        with pytest.raises(ValidationError, match="Banned SQL pattern detected"):
            validate_query(q)

def test_limit_enforced():
    """If user requests limit > 10000, it should be clamped or replaced."""
    # Assuming the validator replaces or limits it. Our validator replaces it.
    sql = "SELECT id FROM governed.sales LIMIT 50000"
    validated = validate_query(sql)
    assert "LIMIT 10000" in validated
    assert "50000" not in validated

    # Valid lower limits should be kept
    sql2 = "SELECT id FROM governed.sales LIMIT 10"
    validated2 = validate_query(sql2)
    assert "LIMIT 10" in validated2

def test_only_select_allowed():
    """Queries that do not start with SELECT should be rejected outright."""
    with pytest.raises(ValidationError, match="Only SELECT queries are allowed"):
        validate_query("WITH cte AS (SELECT * FROM foo) SELECT * FROM cte")
