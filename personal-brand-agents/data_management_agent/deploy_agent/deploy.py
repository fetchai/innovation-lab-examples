from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from data_management_agent.models import *
from enum import Enum
from data_management_agent.deploy_agent.deploy_helpers import *
from shared_clients.llm_client import shared_llm
from shared_clients.supabase_client import supabase


class Step(Enum):
    ASK_AGENT_ID = "ask_agent_id"
    VERIFY_AGENT_ID = "verify_agent_id"
    INVALID_STEP = "invalid_step"

def deploy_agent(state: AgentState):
    """Initial entry point for the Deploy Agent, it will walk the user through the deployment process"""
    current_step = state["current_step"]
    is_valid_step = current_step in [s.value for s in Step]

    if not current_step or not is_valid_step:
        # We could check what information we already have about the user at this point then route them properly
        current_step = Step.ASK_AGENT_ID.value

    return {
        "current_step": current_step,
        "messages": state["messages"]
    }

def ask_agent_id(state: AgentState):
    """Asks the user for their agent id and moves on to the next step"""
    next_step = Step.VERIFY_AGENT_ID.value
    return {
        "current_step": next_step,
        "messages": state["messages"] + [AIMessage(content="What is the id of the agent that will be your personal brand?")],
    }

def verify_agent_id(state: AgentState):
    """Validates the user's agent id before proceeding to the next step"""

    user_response: str = state["messages"][-1].content if state["messages"] else ""  # type: ignore

    # Initialize LLM for agent id validation
    valid_agent_id = is_valid_agent_id(user_response, shared_llm)

    if not valid_agent_id:
        return {
            "current_step": Step.VERIFY_AGENT_ID.value,
            "messages": state["messages"] + [AIMessage(content="That doesn't seem like a valid agent id. Please try again.")],
        }

    # TODO save this into supabase
    extracted_agent_id = extract_agent_id(user_response)
    supabase.table("personal_brand_asi_one_relationships").insert(
        {
            "asi_one_id": state["asi_one_id"],
            "personal_brand_agent_id": extracted_agent_id,
        }
    ).execute()

    # Done with the onboarding flow 
    return {
        "current_step": "",
        "current_agent": "",
        "messages": state["messages"] + [AIMessage(content="Thanks! Your agent has been deployed successfully.")],
    }

def invalid_step(state: AgentState):
    return {
        "messages": state["messages"] + [
            AIMessage(content=f"⚠️ Invalid step `{state['current_step']}`")
        ],
        "current_agent":"",
        "current_step": "",
    }

def build_deploy_graph():
    graph = StateGraph(AgentState)

    # Automatically add all enum step functions as nodes, plus deploy_agent 
    graph.add_node(deploy_agent)
    for step in Step:
        graph.add_node(globals()[step.value])

    graph.add_edge(START, "deploy_agent")

    # Route based on current_step (resume logic)
    graph.add_conditional_edges(
        "deploy_agent",
        lambda state: state["current_step"],
        {
            **{
                step.value: step.value
                for step in Step
            }
        },
    )

    for node in [step.value for step in Step]:
        graph.add_edge(node, END)

    return graph.compile()


if __name__ == "__main__":
    from pprint import pprint
    graph = build_deploy_graph()
    new_chat = initialize_agent_state("user123")
    new_chat["current_step"] = "verify_agent_id"
    new_chat["messages"] = [HumanMessage(content="My agent id is agent1qt3qh62838nhu4u7j86azn55ylvfm767d9rhk5lae4qe8lnyspvhu7zxrsx")]
    result = graph.invoke(new_chat)
    pprint(result, indent=2)