"""Demo: list the battle.training tools, or ask one question via a LangGraph agent.

Usage:
    python agent_demo.py --list-tools
    BT_DEMO_MODEL=gpt-4o-mini python agent_demo.py "Who leads the ladder?"

--list-tools prints the local tool catalog (names, descriptions, argument
schemas) — no network and no model involved. Question mode builds a
one-agent LangGraph ReAct agent with all read tools attached (plus the
account tools if BT_ACCOUNT_KEY is set in the environment) and runs one
question through it. The model is chosen at runtime via BT_DEMO_MODEL and
needs that provider's API key in the environment.
"""

from __future__ import annotations

import json
import os
import sys

from battle_training_tools import BattleTrainingClient, build_tools
from battle_training_tools.tools import TOOL_SPECS


def list_tools() -> None:
    for name, (args_model, needs_key, description) in TOOL_SPECS.items():
        scope = "account key required" if needs_key else "anonymous"
        print(f"battle_training_{name} ({scope})")
        print(f"  {description}")
        print(
            f"  args: {json.dumps(args_model.model_json_schema().get('properties', {}))}"
        )


def ask(question: str) -> None:
    model_name = os.environ.get("BT_DEMO_MODEL")
    if not model_name:
        raise SystemExit("Set BT_DEMO_MODEL (e.g. gpt-4o-mini) to run question mode.")
    from langchain.chat_models import init_chat_model
    from langgraph.prebuilt import create_react_agent

    client = BattleTrainingClient(key=os.environ.get("BT_ACCOUNT_KEY"))
    tools = build_tools(client)
    agent = create_react_agent(init_chat_model(model_name), tools)
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    print(result["messages"][-1].content)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--list-tools":
        list_tools()
    elif len(sys.argv) > 1:
        ask(" ".join(sys.argv[1:]))
    else:
        print(__doc__)
