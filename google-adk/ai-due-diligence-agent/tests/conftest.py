"""
Ensure the example root is on sys.path so ai_due_diligence_agent is importable,
and set placeholder credentials before anything imports the package (several
dependencies build clients at import time and refuse to import without a key).
"""

import os
import sys

os.environ.setdefault("AI_DUE_DILIGENCE_AGENT_SEED", "test-seed")
os.environ.setdefault("OPENAI_API_KEY", "test-placeholder-key")
os.environ.setdefault("ASI_ONE_API_KEY", "test-placeholder-key")
os.environ.setdefault("ASI1_API_KEY", "test-placeholder-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-placeholder-key")

parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent not in sys.path:
    sys.path.insert(0, parent)
