"""
diff_util.py — difflib.unified_diff for original vs healed SQL display.

Used by Agent 2 (self-healing) to log the diff between original and fixed SQL.
Shown in IT Admin Console to prove self-healing happened.
"""
from __future__ import annotations

import difflib


def sql_diff(original_sql: str, healed_sql: str) -> str:
    """
    Generate a unified diff between the original failed SQL and the healed SQL.
    Returns a string suitable for display in the admin console.
    """
    original_lines = original_sql.strip().splitlines(keepends=True)
    healed_lines = healed_sql.strip().splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        healed_lines,
        fromfile="Original SQL (failed)",
        tofile="Healed SQL (succeeded)",
        lineterm="",
    )
    return "\n".join(diff)
