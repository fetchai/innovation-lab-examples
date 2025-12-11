from typing import Type
from enum import Enum
from shared_clients.llm_client import shared_llm
from data_management_agent.models import AgentState

def user_wants_to_exit_flow(state: AgentState) -> bool:
    """
    Uses LLM to check if the user wants to exit or stop the current agentic workflow,
    based on the latest message in the context of a running workflow.
    """
    messages = state["messages"]
    recent_context = messages[-1:]  # Use the last 5 messages for context

    prompt = (
        "You are a smart assistant monitoring if a user wants to exit or stop their agent workflow.\n"
        "Given the recent conversation below (user and assistant exchanges), reply ONLY with 'True' "
        "if the user's most recent message indicates they want to stop, quit, exit, or end the current process/workflow. "
        "Otherwise, reply with 'False'.\n\n"
        "Here is the conversation history:\n"
    )

    for msg in recent_context:
        role = "User" if getattr(msg, "role", None) == "user" or msg.__class__.__name__ == "HumanMessage" else "Assistant"
        prompt += f"{role}: {msg.content}\n"

    prompt += ("\nAgain, answer with only 'True' or 'False'.")

    response = shared_llm.invoke([{"role": "system", "content": prompt}])
    answer = str(response.content).strip().split("\n")[0]

    return answer == "True"

def classify_intent(state: AgentState, agent_enum: Type[Enum], agent_descriptions: dict) -> Enum:
    messages = state["messages"]
    recent_context = messages[-5:]

    agent_list = [
        f"{agent.value}: {desc}"
        for agent, desc in agent_descriptions.items()
    ]
    agent_list_str = "\n".join(agent_list)

    route_prompt = (
        "You are a smart router for a multi-agent system.\n"
        "Choose the most appropriate agent to handle the user's intent.\n\n"
        f"Available agents:\n{agent_list_str}\n\n"
        "Recent conversation context:\n"
    )
    for msg in recent_context:
        role = "User" if getattr(msg, "role", None) == "user" or msg.__class__.__name__ == "HumanMessage" else "Assistant"
        route_prompt += f"{role}: {msg.content}\n"

    route_prompt += (
        "\nRespond ONLY with the agent key. "
        "If unclear or greeting → 'fallback_agent'."
    )

    llm_response = shared_llm.invoke([{"role": "system", "content": route_prompt}])
    # print("LLM response: ", llm_response)
    agent_key = llm_response.content.strip().split("\n")[0] # type: ignore
    valid_keys = [a.value for a in agent_enum] # type: ignore
    if agent_key not in valid_keys:
        agent_key = agent_enum.FALLBACK# type: ignore

    return agent_enum(agent_key) # type: ignore


if __name__ == "__main__":
    pass