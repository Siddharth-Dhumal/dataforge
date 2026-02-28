import anthropic
import os
import logging

logger = logging.getLogger(__name__)

_api_key = os.environ.get("ANTHROPIC_API_KEY", "dummy_key")
client = anthropic.Anthropic(api_key=_api_key)


def call_claude(system: str, user_message: str, tool: dict) -> dict | None:
    """
    Universal wrapper for all Anthropic tool use calls (factory + agents).
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


def call_claude_text(
    user_prompt: str,
    system_prompt: str,
    model: str = "claude-sonnet-4-20250514",
    temperature: float = 0.0
) -> str:
    """
    Universal Claude text wrapper used by agents that need plain text responses
    (e.g., insight generator, self-healing agent retry prompts).
    Returns the text response string, or an error string on failure.
    """
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[LLM ERROR] call_claude_text | {e}")
        return f"Claude Error: {str(e)}"
