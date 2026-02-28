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
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_LOADED = False
SECRET_SCOPE = "dataforge-secrets"

# Map: env var name → secret key in the scope
_SECRET_MAP = {
    "DATABRICKS_HOST": "databricks-host",
    "DATABRICKS_HTTP_PATH": "databricks-http-path",
    "DATABRICKS_TOKEN": "databricks-token",
    "ANTHROPIC_API_KEY": "anthropic-api-key",
}


def load_env():
    """
    Bootstrap environment variables.
    
    Strategy:
      1. If running on Databricks Apps → read secrets from scope via SDK
      2. If running locally → read from .env file
      3. Skip any variable that's already set in the environment
    """
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    # --- Attempt 1: Load from .env (local development) ---
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
            logger.info("[env_loader] Loaded .env file")
        except Exception as e:
            logger.warning(f"[env_loader] Failed to read .env: {e}")

    # --- Attempt 2: Read from Databricks secret scope (deployed environment) ---
    # Only try if some vars are still missing
    missing = [k for k in _SECRET_MAP if not os.environ.get(k)]
    if missing:
        try:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            for env_key in missing:
                secret_key = _SECRET_MAP[env_key]
                try:
                    resp = w.secrets.get_secret(scope=SECRET_SCOPE, key=secret_key)
                    if resp and resp.value:
                        # SDK returns bytes, decode to string
                        val = resp.value if isinstance(resp.value, str) else resp.value.decode("utf-8")
                        os.environ[env_key] = val
                        logger.info(f"[env_loader] Loaded {env_key} from secret scope")
                except Exception as e:
                    logger.debug(f"[env_loader] Could not read secret {secret_key}: {e}")
        except Exception as e:
            logger.debug(f"[env_loader] Databricks SDK not available: {e}")

    # --- Summary ---
    for k in _SECRET_MAP:
        status = "✅" if os.environ.get(k) else "❌"
        logger.info(f"[env_loader] {k}: {status}")
