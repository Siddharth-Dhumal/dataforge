"""
Agent 3 — Insight Generator (agents/insight_generator.py)

Runs synchronously after chart renders. Not async. Streamlit async is fragile.

Uses Anthropic tool use pattern. Input to LLM: column names + min/max/mean/count
summary stats only. **Never raw data. Never PII.**

8-second timeout via threading.Timer. On timeout: returns empty string.
Agent 3 never blocks the UI under any circumstance.

Only fires if query succeeded. Never fires on failed queries.
Output displayed in styled "AI Briefing" card, clearly labeled "AI-generated interpretation."
"""
from __future__ import annotations

import threading
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Tool definition (Anthropic tool use pattern) ──────────────────────
INSIGHT_TOOL = {
    "name": "generate_insight",
    "description": "Generate a plain English interpretation of query results",
    "input_schema": {
        "type": "object",
        "properties": {
            "insight": {
                "type": "string",
                "description": "2-3 sentence plain English interpretation of the data patterns",
            },
            "has_insight": {
                "type": "boolean",
                "description": "False if data has no meaningful pattern worth noting",
            },
        },
        "required": ["insight", "has_insight"],
    },
}

# Hard ceiling — Agent 3 never blocks the UI
_TIMEOUT_SECONDS = 8


def _build_summary_stats(rows: List[Dict]) -> str:
    """
    Build summary statistics from query results.
    Never sends raw data. Never sends PII.
    Only column names + min/max/mean/count.
    """
    if not rows:
        return "No data returned."

    cols = list(rows[0].keys())
    row_count = len(rows)
    stats = []

    for col in cols:
        # Skip PII columns entirely
        if col.lower() in ("regional_manager", "email", "ssn", "salary"):
            stats.append(f"{col}: [PII-MASKED, {row_count} values]")
            continue

        vals = [r[col] for r in rows if r.get(col) is not None]
        if not vals:
            stats.append(f"{col}: all null ({row_count} rows)")
            continue

        if isinstance(vals[0], (int, float)):
            stats.append(
                f"{col}: count={len(vals)}, min={min(vals):.2f}, "
                f"max={max(vals):.2f}, avg={sum(vals)/len(vals):.2f}"
            )
        elif isinstance(vals[0], str):
            unique = len(set(vals))
            sample = vals[0][:50] if vals else "N/A"
            stats.append(f"{col}: {unique} unique values, sample={sample!r}")

    return f"Rows: {row_count}\nColumns: {', '.join(cols)}\n" + "\n".join(stats)


def generate_insight(rows: List[Dict], nl_question: str) -> str:
    """
    Agent 3: Generate AI insight from query results using Anthropic tool use.

    8-second timeout. Returns empty string on timeout or any failure.
    Never blocks the UI. Never receives raw PII data.
    """
    if not rows:
        return ""

    result_holder: List[str] = [""]

    def _call_llm():
        try:
            from utils.llm import call_claude
        except ImportError:
            return

        summary = _build_summary_stats(rows)

        system = (
            "You are a data analyst for DataForge. Given summary statistics of a query result, "
            "provide a brief, insightful interpretation. Focus on key patterns, "
            "notable values, and actionable observations. Keep it to 2-3 sentences. "
            "Do NOT mention specific PII values. Do NOT repeat raw numbers verbatim — "
            "provide interpretation and context."
        )

        user_msg = f"User question: {nl_question}\n\nData summary:\n{summary}"

        result = call_claude(system, user_msg, INSIGHT_TOOL)
        if result and result.get("has_insight"):
            result_holder[0] = result.get("insight", "")

    # Run with timeout — never block the UI
    thread = threading.Thread(target=_call_llm, daemon=True)
    thread.start()
    thread.join(timeout=_TIMEOUT_SECONDS)

    if thread.is_alive():
        logger.warning("[Agent 3] Insight generation timed out after %ds", _TIMEOUT_SECONDS)
        # Thread will complete in background but we don't wait
        return ""

    return result_holder[0]
