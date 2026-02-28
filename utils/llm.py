"""
utils/llm.py — Universal LLM call wrapper.

Every LLM call in this project uses call_claude() or call_claude_text().
All agents import from here. Nobody writes their own API call.
Nobody handles exceptions differently. Consistent behavior everywhere.
"""
import os
import sys
import anthropic

# Lazy client initialization
_client = None

# Default model — works with the user's API key
MODEL = "claude-sonnet-4-20250514"


def _log(msg: str):
    """Print to stderr so it shows in Databricks app logs."""
    print(f"[LLM] {msg}", file=sys.stderr, flush=True)


def _get_client() -> anthropic.Anthropic:
    """Get or create the Anthropic client."""
    global _client
    if _client is None:
        # Ensure env is loaded (idempotent)
        try:
            from core.env_loader import load_env
            load_env()
        except Exception:
            pass

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            _log("ERROR: ANTHROPIC_API_KEY not set in environment")
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. "
                "Ensure the secret is stored in the 'dataforge-secrets' scope."
            )

        _client = anthropic.Anthropic(api_key=api_key)
        _log(f"Client initialized (key: {api_key[:8]}...)")
    return _client


def call_claude(system: str, user_message: str, tool: dict, *, max_tokens: int = 1024) -> dict | None:
    """
    Universal wrapper for all Anthropic tool use calls (factory + agents).
    Returns tool input dict on success, None on any failure.
    Caller is responsible for handling None gracefully.
    """
    try:
        client = _get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            system=system,
            messages=[{"role": "user", "content": user_message}]
        )
        _log(f"{tool['name']} | in={response.usage.input_tokens} out={response.usage.output_tokens}")
        return response.content[0].input
    except Exception as e:
        _log(f"ERROR in {tool['name']}: {type(e).__name__}: {e}")
        return None


def call_claude_text(
    user_prompt: str,
    system_prompt: str,
    model: str = MODEL,
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
        _log(f"ERROR in call_claude_text: {type(e).__name__}: {e}")
        return f"Claude Error: {str(e)}"
