from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from data_management_agent.models import *
from data_management_agent.gather_agent.gather_agent import build_gather_graph
from data_management_agent.onboarding_agent.onboarding_agent import build_onboarding_graph
from data_management_agent.router_helpers import *
from data_management_agent.data_management_agent_definitions import *
from utils.data_serialization_helpers import *
from data_management_agent.linkedin_agent.linkedin_agent import build_linkedin_graph
from data_management_agent.deploy_agent.deploy import build_deploy_graph
from data_management_agent.delete_agent.delete_agent import build_delete_graph
from data_management_agent.answer_failed_questions_agent.answer_failed_questions_agent import build_answer_failed_questions_graph

# --- Intent Router ---
def intent_router(state: AgentState):
    if user_wants_to_exit_flow(state):
        return {"current_agent": Agent.END_AGENT.value, "current_step": ""}

    # Continuing where we left off, user is already working with an agent and is in some step
    if state["current_agent"] in [agent.value for agent in Agent]:
        return {"current_agent": state["current_agent"]}

    # New conversation or the user has exited one of the other agents 
    classified_agent = classify_intent(state, Agent, AGENT_DESCRIPTIONS)
    print("Classified agent: ", classified_agent)

    return {"current_agent": classified_agent.value}


def end_agent(state: AgentState):
    return {"current_agent": "", "current_step": "", "messages": [AIMessage(content="Gotcha, goodbye!")]}

def fallback_agent(state: AgentState):
    default_message = "Hm. I can't help you with that. As your personal brand data orchestrator, I can...\n- Onboard you as a user\n- Deploy your personal brand agent\n- Ingest facts from your resume\n- Help you manage your data\n- Connect your LinkedIn\n\nLet me know what you'd like to do!"
    return {
        "messages": [AIMessage(content=default_message)],
        "current_agent": "",
        "current_step": ""
    }

# --- Build Graph ---
def build_main_graph():
    graph = StateGraph(AgentState)
    graph.add_node(intent_router)
    graph.add_node(end_agent)

    onboarding_agent = build_onboarding_graph()
    linkedin_agent = build_linkedin_graph()
    delete_agent = build_delete_graph()
    deploy_agent = build_deploy_graph()
    gather_agent = build_gather_graph()
    answer_failed_questions_agent = build_answer_failed_questions_graph()

    graph.add_node(Agent.ONBOARDING.value, onboarding_agent)
    graph.add_node(Agent.LINKEDIN.value, linkedin_agent)
    graph.add_node(Agent.DELETE.value, delete_agent)
    graph.add_node(Agent.DEPLOY.value, deploy_agent)
    graph.add_node(Agent.GATHER.value, gather_agent)
    graph.add_node(Agent.ANSWER_FAILED_QUESTIONS.value, answer_failed_questions_agent)
    graph.add_node(Agent.FALLBACK.value, fallback_agent)

    graph.add_edge(START, "intent_router")

    graph.add_conditional_edges(
        "intent_router",
        lambda state: state["current_agent"],
        {
            **{agent.value: agent.value for agent in Agent},
        },
    )

    for node in [agent.value for agent in Agent]:
        graph.add_edge(node, END)

    graph = graph.compile()
    return graph


# --- Test ---
def debugprint(state):
    print("\n" + "=" * 40)
    print(f"current_agent: {state['current_agent']}")
    print(f"current_step: {state['current_step']}")
    print(f"last_message: {state['messages'][-1].content}")
    print("=" * 40 + "\n")

if __name__ == "__main__":
    graph = build_main_graph()
    new_state = initialize_agent_state("user123")
    new_state["messages"] = [HumanMessage(content="hello")]
    result = graph.invoke(new_state)

    while True:
        print(result["messages"][-1].content)
        answer = input("> ")
        new_state = AgentState(**result)
        new_state["messages"].append(HumanMessage(content=answer))

        result = graph.invoke(new_state)
        new_state = result

        debugprint(result)