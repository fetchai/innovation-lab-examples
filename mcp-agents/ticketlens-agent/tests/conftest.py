import os
import sys

# Add the project root to sys.path so tests can import the agent modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)
