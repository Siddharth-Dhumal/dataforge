import yaml
from pathlib import Path

# Define the base directory (two levels up from utils)
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / 'config'

def load_guardrails() -> dict:
    """Loads guardrails configuration from YAML."""
    guardrails_path = CONFIG_DIR / 'guardrails.yaml'
    with open(guardrails_path, 'r') as f:
        return yaml.safe_load(f)

def load_roles() -> dict:
    """Loads roles configuration from YAML."""
    roles_path = CONFIG_DIR / 'roles.yaml'
    with open(roles_path, 'r') as f:
        return yaml.safe_load(f)
