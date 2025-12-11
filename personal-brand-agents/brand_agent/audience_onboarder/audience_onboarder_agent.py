from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from brand_agent.brand_agent_helpers import *
from brand_agent.brand_agent_helpers import *
from brand_agent.brand_agent_state_model import BrandAgentState, initialize_agent_state
from brand_agent.audience_onboarder.audience_onboarder_steps import Step
from brand_agent.audience_onboarder.audience_helpers import is_valid_name, extract_name, is_valid_contact, extract_contact, is_valid_role, extract_role, get_milestone_step_statuses, get_current_step, get_pretty_milestone_step_statuses
from shared_clients.supabase_client import supabase

def audience_onboarder_agent(state: BrandAgentState):
    """Initial entry point for the Audience Onboarder Agent, it will determine the next step to display to the user"""

    current_step = state.get("current_step")
    is_valid_step = current_step in [s.value for s in Step]

    if not current_step or not is_valid_step:
        # We could check what information we already have about the user at this point then route them properly
        inferred_step = get_current_step(get_milestone_step_statuses(state["asi_one_id"], state["brand_agent_id"]))
        current_step = inferred_step.value

    return {
        "current_step": current_step,
        "messages": state["messages"]
    }

def ask_name(state: BrandAgentState):
    """Ask the user for their name"""
    return {
        "current_step": Step.VERIFY_NAME.value,
        "messages": state["messages"] + [AIMessage(content="What is your name?")]
    }

def verify_name(state: BrandAgentState):
    """Verify the user's name"""
    user_input = str(state["messages"][-1].content)
    valid_name = is_valid_name(user_input)
    if not valid_name:
        return {
            "current_step": Step.VERIFY_NAME.value,
            "messages": state["messages"] + [AIMessage(content="That is not a valid name. Please try again.")]
        }
    
    name = extract_name(user_input)
    # This needs the personal brand agent id from the state
    # So we can link a user (their asi one id) to the current personal brand
    # This is so we can have a unique profile for each user PER personal brand they're talking to

    # We want to upsert using a compound unique constraint on audience_asi_one_id and personal_brand_agent_id
    supabase.table("audience_profiles").upsert(
        {
            "name": name,
            "personal_brand_agent_id": state["brand_agent_id"],
            "audience_asi_one_id": state["asi_one_id"],  # this is the asi one id of the current user chatting with the agent
        },
        on_conflict="audience_asi_one_id,personal_brand_agent_id"  # This ensures the upsert uses this composite key
    ).execute()

    return {
        "current_step": Step.VERIFY_ROLE.value,
        "messages": state["messages"] + [AIMessage(content="That is a valid name. Thank you!\nWhat is your role?")]
    }

def ask_role(state: BrandAgentState):
    """Ask the user for their role"""
    return {
        "current_step": Step.VERIFY_ROLE.value,
        "messages": state["messages"] + [AIMessage(content="What is your role?")]
    }

def verify_role(state: BrandAgentState):
    """Verify the user's role"""
    user_input = str(state["messages"][-1].content)
    valid_role = is_valid_role(user_input)

    if not valid_role:
        return {
            "current_step": Step.VERIFY_ROLE.value,
            "messages": state["messages"] + [AIMessage(content="That is not a valid role. Please try again.")]
        }

    role = extract_role(user_input)
    supabase.table("audience_profiles").upsert(
        {
            "role": role,
            "personal_brand_agent_id": state["brand_agent_id"],
            "audience_asi_one_id": state["asi_one_id"], #this is the asi one id of the current user chatting with the agent
        },
        on_conflict="audience_asi_one_id,personal_brand_agent_id"  # This ensures the upsert uses this composite key
    ).execute()
    return {
        "current_step": Step.VERIFY_CONTACT.value,
        "messages": state["messages"] + [AIMessage(content="That is a valid role. Thank you!\nWhat is your contact information?")]
    }

def ask_contact(state: BrandAgentState):
    """Ask the user for their contact information"""
    return {
        "current_step": Step.VERIFY_CONTACT.value,
        "messages": state["messages"] + [AIMessage(content="What is your contact information?")]
    }

def verify_contact(state: BrandAgentState):
    """Verify the user's contact information"""
    user_input = str(state["messages"][-1].content)
    valid_contact = is_valid_contact(user_input)

    if not valid_contact:
        return {
            "current_step": Step.VERIFY_CONTACT.value,
            "messages": state["messages"] + [AIMessage(content="That is not a valid contact information. Please try again.")]
        }

    contact = extract_contact(user_input)
    supabase.table("audience_profiles").upsert(
        {
            "contact": contact,
            "personal_brand_agent_id": state["brand_agent_id"],
            "audience_asi_one_id": state["asi_one_id"], #this is the asi one id of the current user chatting with the agent
        },
        on_conflict="audience_asi_one_id,personal_brand_agent_id"  # This ensures the upsert uses this composite key
    ).execute()
    return {
        "current_step": "",
        "current_agent": "",
        "messages": state["messages"] + [AIMessage(content="Thank you for onboarding!")]
    }

def fallback(state: BrandAgentState):
    """Fallback step for the Audience Onboarder Agent"""
    default_message = """
    [Unclear Intent]
    I am here to help you onboard as an audience. I can log your name, role, and contact information.
    """
    return {
        "current_step": Step.FALLBACK.value,
        "messages": state["messages"] + [AIMessage(content=default_message)]
    }

def complete(state: BrandAgentState):
    """Complete step for the Audience Onboarder Agent"""

    pretty_statuses = get_pretty_milestone_step_statuses(get_milestone_step_statuses(state["asi_one_id"], state["brand_agent_id"]))
    return {
        "current_step": Step.COMPLETE.value,
        "current_agent": "",
        "messages": state["messages"] + [AIMessage(content=f"Thank you for onboarding!\n\nYour onboarding status:\n{pretty_statuses}")]
    }
def build_audience_onboarder_graph():
    graph = StateGraph(BrandAgentState)

    graph.add_node(audience_onboarder_agent)
    for step in Step:
        graph.add_node(globals()[step.value])

    graph.add_edge(START, "audience_onboarder_agent")

    graph.add_conditional_edges(
        "audience_onboarder_agent",
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


def debugprint(state):
    print("\n" + "=" * 40)
    print(f"current_agent: {state['current_agent']}")
    print(f"current_step: {state['current_step']}")
    print(f"last_message: {state['messages'][-1].content}")
    print("=" * 40 + "\n")

def input_loop():
    graph = build_audience_onboarder_graph()
    new_state = initialize_agent_state("user123", "agent1qgerajmgluncfslmdmrgxww463ntt4c90slr0srq4lcc9vmyyavkyg2tzh7")
    new_state["messages"] = [HumanMessage(content="hello")]
    result = graph.invoke(new_state)

    while True:
        print(result["messages"][-1].content)
        answer = input("> ")
        new_state = BrandAgentState(**result)
        new_state["messages"].append(HumanMessage(content=answer))

        result = graph.invoke(new_state)
        new_state = result

        debugprint(result)

if __name__ == "__main__":
    input_loop()