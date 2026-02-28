from agents.self_healing_agent import get_database_schema_context
from utils.llm import call_claude


def analyze_schema_and_suggest(catalog_name: str, schema_name: str) -> dict:
    """
    Schema Analyzer Agent.

    Input:  catalog_name, schema_name — the Databricks Unity Catalog location.
    Output: dict with a list of 5 structured app/dashboard suggestions.

    Workflow:
    1. Fetch live schema via the shared helper in self_healing_agent.
    2. Build a strategist system prompt with the schema concatenated in.
    3. Call Claude via the universal call_claude() wrapper.
    4. Parse the numbered response into a clean list of dicts and return.
    """

    # Step 1: Fetch the schema (shared helper — no duplication)
    schema_context = get_database_schema_context(catalog_name, schema_name)

    if schema_context.startswith("Error"):
        return {"success": False, "error": schema_context, "suggestions": []}

    # Step 2: Build the system prompt — persona + schema concatenated in
    system_prompt = (
        "You are a senior data product strategist. "
        "Your job is to look at a database schema and recommend exactly 5 "
        "specific, actionable dashboard or mini-app ideas that a business user "
        "would find immediately valuable. Each suggestion must be tailored to the "
        "actual tables and columns provided — no generic advice.\n\n"
        "Format each suggestion exactly like this:\n"
        "1. Title: <short name, max 6 words>\n"
        "   Description: <1-2 sentences on what it shows and why it matters>\n"
        "   Key Columns: <comma-separated list of actual column names from the schema>\n\n"
        f"{schema_context}"
    )

    user_prompt = (
        "Based on the schema in your instructions, suggest exactly 5 dashboards "
        "or mini-app ideas that would provide the most business value. "
        "Follow the format specified precisely."
    )

    # Step 3: Call Claude via the shared universal wrapper
    raw_response = call_claude(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.3  # Slightly higher than SQL — some creativity is valuable here
    )

    if raw_response.startswith("Claude Error:"):
        return {"success": False, "error": raw_response, "suggestions": []}

    # Step 4: Parse and return
    return {
        "success": True,
        "error": None,
        "raw_response": raw_response,
        "suggestions": _parse_suggestions(raw_response)
    }


def _parse_suggestions(raw_text: str) -> list:
    """
    Parses Claude's numbered list into a list of dicts.
    Each dict has: title, description, key_columns.
    """
    suggestions = []
    current = {}

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # New numbered item: "1.", "2.", etc.
        if len(line) >= 2 and line[0].isdigit() and line[1] == ".":
            if current:
                suggestions.append(current)
            # The title usually follows the number on the same line: "1. Title: Foo"
            rest = line.split(".", 1)[-1].strip()
            title = rest.split("Title:", 1)[-1].strip() if "Title:" in rest else rest
            current = {"title": title, "description": "", "key_columns": ""}

        elif line.lower().startswith("title:"):
            current["title"] = line.split(":", 1)[-1].strip()

        elif line.lower().startswith("description:"):
            current["description"] = line.split(":", 1)[-1].strip()

        elif line.lower().startswith("key columns:"):
            current["key_columns"] = line.split(":", 1)[-1].strip()

        elif current and not current.get("description"):
            # Catch freeform description lines that don't have a label
            current["description"] = line

    if current:
        suggestions.append(current)

    return suggestions
