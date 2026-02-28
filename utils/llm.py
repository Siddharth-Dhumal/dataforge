"""
utils/llm.py — Universal LLM call wrapper.

Every LLM call in this project uses call_claude() or call_claude_text().
All agents import from here. Nobody writes their own API call.
Nobody handles exceptions differently. Consistent behavior everywhere.

API key from environment variable only (loaded from .env if needed).
"""
import anthropic
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy client initialization — ensures .env is loaded before creating client
_client = None


def _get_client() -> anthropic.Anthropic:
    """Get or create the Anthropic client, loading .env if needed."""
    global _client
    if _client is None:
        # Load .env if ANTHROPIC_API_KEY not already in environment
        if not os.environ.get("ANTHROPIC_API_KEY"):
            try:
                from dotenv import load_dotenv
                load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
            except Exception:
                pass

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment or .env")

        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def call_claude(system: str, user_message: str, tool: dict) -> dict | None:
    """
    Universal wrapper for all Anthropic tool use calls (factory + agents).
    Returns tool input dict on success, None on any failure.
    Caller is responsible for handling None gracefully.
    """
    try:
        client = _get_client()
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
        client = _get_client()
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
