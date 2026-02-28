"""
core/env_loader.py — Environment bootstrapper for DataForge.

On Databricks Apps:
  - DATABRICKS_HOST is auto-set by the platform
  - Reads other secrets from the 'dataforge-secrets' scope via SDK
  - Falls back to .env file for local development

This module MUST be imported before any other module that uses os.getenv()
for DATABRICKS_* or ANTHROPIC_API_KEY.
"""
import os
import sys
from pathlib import Path

_LOADED = False
SECRET_SCOPE = "dataforge-secrets"

# Map: env var name → secret key in the scope
_SECRET_MAP = {
    "DATABRICKS_HOST": "databricks-host",
    "DATABRICKS_HTTP_PATH": "databricks-http-path",
    "DATABRICKS_TOKEN": "databricks-token",
    "ANTHROPIC_API_KEY": "anthropic-api-key",
}


def _log(msg: str):
    """Print to stderr so it shows in Databricks app logs."""
    print(f"[env_loader] {msg}", file=sys.stderr, flush=True)


def load_env():
    """
    Bootstrap environment variables. Safe to call multiple times.
    
    Strategy:
      1. If .env file exists → read from it (local development)
      2. If running on Databricks Apps → read secrets from scope via SDK
      3. Skip any variable that's already set in the environment
    """
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    # --- Step 1: Load from .env file (local development) ---
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k and v and k not in os.environ:
                        os.environ[k] = v
            _log("Loaded .env file")
        except Exception as e:
            _log(f"Failed to read .env: {e}")

    # --- Step 2: Read from Databricks secret scope ---
    missing = [k for k in _SECRET_MAP if not os.environ.get(k)]
    if missing:
        _log(f"Missing env vars: {missing} — trying Databricks secret scope...")
        try:
            import base64
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            for env_key in missing:
                secret_key = _SECRET_MAP[env_key]
                try:
                    resp = w.secrets.get_secret(scope=SECRET_SCOPE, key=secret_key)
                    if resp and resp.value:
                        raw = resp.value
                        # SDK returns base64-encoded string — decode it
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        try:
                            val = base64.b64decode(raw).decode("utf-8")
                        except Exception:
                            # If base64 decode fails, use raw value
                            val = raw
                        os.environ[env_key] = val
                        _log(f"Loaded {env_key} from scope ({len(val)} chars)")
                except Exception as e:
                    _log(f"Could not read secret '{secret_key}': {e}")
        except Exception as e:
            _log(f"Databricks SDK unavailable: {e}")

    # --- Step 3: Try dotenv as last resort ---
    still_missing = [k for k in _SECRET_MAP if not os.environ.get(k)]
    if still_missing:
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_path, override=False)
            _log("Tried dotenv as fallback")
        except Exception:
            pass

    # --- Summary ---
    for k in _SECRET_MAP:
        val = os.environ.get(k, "")
        status = f"✅ ({len(val)} chars)" if val else "❌ MISSING"
        _log(f"{k}: {status}")
