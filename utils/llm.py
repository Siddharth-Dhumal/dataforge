import anthropic
import os
import logging

logger = logging.getLogger(__name__)

# Uses dummy key if not present so it doesn't crash on import
_api_key = os.environ.get("ANTHROPIC_API_KEY", "dummy_key")
client = anthropic.Anthropic(api_key=_api_key)

def call_claude(system: str, user_message: str, tool: dict) -> dict | None:
    """
    Universal wrapper for all Anthropic tool use calls.
    Returns tool input dict on success, None on any failure.
    Caller is responsible for handling None gracefully.
    """
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            system=system,
            messages=[{"role": "user", "content": user_message}]
        )
        print(f"[LLM] {tool['name']} | in={response.usage.input_tokens} out={response.usage.output_tokens}")
        return response.content[0].input
    except Exception as e:
        print(f"[LLM ERROR] {tool['name']} | {e}")
        return None
