import yaml
from pathlib import Path
from functools import lru_cache

CONFIG_DIR = Path(__file__).parent.parent / "config"

@lru_cache(maxsize=1)
def load_guardrails() -> dict:
    with open(CONFIG_DIR / "guardrails.yaml", "r") as f:
        return yaml.safe_load(f)

@lru_cache(maxsize=1)
def load_roles() -> dict:
    with open(CONFIG_DIR / "roles.yaml", "r") as f:
        return yaml.safe_load(f)
