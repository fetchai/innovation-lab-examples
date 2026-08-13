#!/usr/bin/env python3
"""
Run the Property Finder ASI1 agent.
Usage, from anywhere:
  python3 run_agent.py
"""

import sys
from pathlib import Path

# This file's directory holds the asi1_agent and repliers_client packages, so it
# is what has to be importable. The directory name has a hyphen and can never be
# a package itself, so it is added to sys.path rather than imported through.
_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

if __name__ == "__main__":
    from asi1_agent.property_agent import agent

    print("Property Finder agent address:", agent.address)
    agent.run()
