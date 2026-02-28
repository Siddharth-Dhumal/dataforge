import anthropic
import os

def call_claude(
    user_prompt: str,
    system_prompt: str,
    model: str = "claude-opus-4-6",
    temperature: float = 0.0
) -> str:
    """
    Universal Claude wrapper used by all agents.
    The caller is fully responsible for building the system_prompt —
    this function does nothing but send it and return the response.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            temperature=temperature,
            extra_headers={"anthropic-beta": "adaptive-thinking-2026-01-01"},
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Claude Error: {str(e)}"