from data_management_agent.models import *
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.messages import AnyMessage
from database.agent_db_models import *

def json_agent_state_to_langgraph(json_data) -> AgentState:
    asi_one_id: str = json_data["asi_one_id"]
    current_agent: str = json_data["current_agent"]
    current_step: str = json_data["current_step"]
    messages: List[AnyMessage] = []

    for msg in json_data["messages"]:
        match msg["role"]:
            case "human":
                messages.append(HumanMessage(content=msg["content"]))
            case "ai":
                messages.append(AIMessage(content=msg["content"]))
            case _:
                raise ValueError(f"Unknown role: {msg['role']}")

    langgraph_agent_state = AgentState(
        asi_one_id=asi_one_id,
        current_agent=current_agent,
        current_step=current_step,
        messages=messages
    )
    return langgraph_agent_state

def langgraph_state_to_json(agent_state) -> dict:
    # Extract basic fields
    asi_one_id = agent_state["asi_one_id"]
    current_agent = agent_state["current_agent"]
    current_step = agent_state["current_step"]

    # Convert messages to JSON-safe list of dicts
    messages_json = []
    for msg in agent_state["messages"]:
        if isinstance(msg, HumanMessage):
            role = "human"
        elif isinstance(msg, AIMessage):
            role = "ai"
        else:
            # fallback or raise error for unsupported message types
            role = getattr(msg, "role", "unknown")
        messages_json.append({
            "role": role,
            "content": msg.content
        })

    # Build the JSON-safe dict
    return {
        "asi_one_id": asi_one_id,
        "current_agent": current_agent,
        "current_step": current_step,
        "messages": messages_json
    }