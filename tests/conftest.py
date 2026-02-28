import sys
from pathlib import Path

# Ensure project root is importable when AppTest runs Streamlit scripts.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
os.environ["DATAFORGE_TEST_MODE"] = "1"