from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from brand_agent.brand_agent_state_model import BrandAgentState, initialize_agent_state
from brand_agent.router_helpers import *
from brand_agent.question_answerer.question_answerer_agent import build_question_answerer_graph
from brand_agent.brand_agent_definitions import Agent, AGENT_DESCRIPTIONS
from shared_clients.supabase_client import supabase
from brand_agent.brand_agent_helpers import get_asi_one_id_from_brand_agent_id
from brand_agent.audience_onboarder.audience_onboarder_agent import build_audience_onboarder_graph

# --- Intent Router ---
def intent_router(state: BrandAgentState):
    if user_wants_to_exit_flow(state):
        return {"current_agent": "END", "current_step": "", "messages": [AIMessage(content="Gotcha, goodbye!")]}

    # Continuing where we left off, user is already working with an agent and is in some step
    if "current_agent" in state and state["current_agent"] in [agent.value for agent in Agent]:
        return {"current_agent": state["current_agent"]}

    # New conversation or the user has exited one of the other agents 
    classified_agent = classify_intent(state, Agent, AGENT_DESCRIPTIONS)
    print(f"Classified agent: {classified_agent}")

    return {"current_agent": classified_agent.value}

def fallback_agent(state: BrandAgentState):
    # TODO fetch the user's name from db for fallback

    brand_agent_id = state["brand_agent_id"]
    asi_one_id = get_asi_one_id_from_brand_agent_id(brand_agent_id)

    data = supabase.table("user_profiles").select("name").eq("asi_one_id", asi_one_id).execute()
    name = data.data[0]["name"] # type: ignore

    default_message = f"""
    [Unclear Intent]
    I am {name}'s personal brand agent. I can do my best to answer your questions on behalf of {name} and tailor my responses based on your role and preferences. Try asking a question or request to set your preferences!
    """
    return {
        "messages": [AIMessage(content=default_message)],
        "current_agent": "",
        "current_step": ""
    }

# --- Build Graph ---
def build_main_graph():
    graph = StateGraph(BrandAgentState)
    graph.add_node(intent_router)

    question_answerer_agent = build_question_answerer_graph()
    audience_onboarder_agent = build_audience_onboarder_graph()

    graph.add_node(Agent.QUESTION_ANSWERER.value, question_answerer_agent)
    graph.add_node(Agent.AUDIENCE_ONBOARDER.value, audience_onboarder_agent)
    graph.add_node(Agent.FALLBACK.value, fallback_agent)

    graph.add_edge(START, "intent_router")

    graph.add_conditional_edges(
        "intent_router",
        lambda state: state["current_agent"],
        {
            **{agent.value: agent.value for agent in Agent},
            "END": END,
        },
    )

    for node in [agent.value for agent in Agent]:
        graph.add_edge(node, END)

    graph = graph.compile()
    return graph

if __name__ == "__main__":
    graph = build_main_graph()
    new_state: BrandAgentState = initialize_agent_state("agent1qdnhwqv3ekrzcuk597nrzc8xh9eyurlwvsrzzrytr6cl87zuwfuayh4xq6g", "agent1qgerajmgluncfslmdmrgxww463ntt4c90slr0srq4lcc9vmyyavkyg2tzh7")
    new_state["messages"] = [HumanMessage(content="does he work at home depot?")]
    result = graph.invoke(new_state)
    print(result["messages"][-1].content)

