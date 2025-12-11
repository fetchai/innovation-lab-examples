from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from data_management_agent.models import *
from data_management_agent.data_management_agent_definitions import Agent
from data_management_agent.delete_agent.delete_types import Step
from data_management_agent.delete_agent.delete_helpers import is_valid_delete_request, to_delete_from_user_input, select_ids_to_delete, delete_data
from shared_clients.chroma_client import facts_collection
from chroma.chroma_models import ChromaDocument
from chroma.chroma_constants import Source
import uuid
from datetime import datetime


def delete_agent(state: AgentState):
    """Initial entry point for the Delete Agent, it will determine the next step to display to the user"""
    current_step = state["current_step"]
    is_valid_step = current_step in [s.value for s in Step]

    if not current_step or not is_valid_step:
        # We could check what information we already have about the user at this point then route them properly
        # inferred_step = get_current_step(get_milestone_step_statuses(state["asi_one_id"]))
        # current_step = inferred_step.value
        current_step = Step.DESCRIBE_DATA_TO_DELETE.value

    return {
        "current_step": current_step,
        "messages": state["messages"]
    }

def describe_data_to_delete(state: AgentState):
    """Describe the data to delete"""
    return {
        "current_step": Step.CONFIRM_DELETE.value,
        "current_agent": Agent.DELETE.value,
        "messages": state["messages"] + [AIMessage(content=f"Please describe the data you want to delete. Example: 'I want to delete my work experience at Walmart'")]
    }

def confirm_delete(state: AgentState):
    """Select the data to delete"""

    # Get the described data to delete
    user_input = state["messages"][-1].content

    if not user_input or not is_valid_delete_request(user_input): # type: ignore
        return {
            "current_step": Step.DESCRIBE_DATA_TO_DELETE.value,
            "current_agent": Agent.DELETE.value,
            "messages": state["messages"] + [AIMessage(content=f"That doesn't seem right... Please describe the data you want to delete.")]
        }

    to_delete = to_delete_from_user_input(user_input, state["asi_one_id"]) # type: ignore
    if not to_delete:
        return {
            "current_step": Step.DESCRIBE_DATA_TO_DELETE.value,
            "current_agent": Agent.DELETE.value,
            "messages": state["messages"] + [AIMessage(content=f"No data found to delete. Please try describing other data.")]
        }

    state["delete_agent_state"]["data_ids_to_delete"] = [doc[1] for doc in to_delete]

    pretty_to_delete = "\n\n" + "\n\n".join([f"Document: {doc[0]}\n\n\nID: {doc[1]}" for doc in to_delete])

    return {
        "current_step": Step.COMPLETE.value,
        "current_agent": Agent.DELETE.value,
        "messages": state["messages"] + [AIMessage(content=f"The following was found: {pretty_to_delete}\n\nPlease list the ids of the data you want to delete or 'all' to delete all of them.")]
    }

def complete(state: AgentState):
    """Complete the deletion process"""

    user_input = state["messages"][-1].content
    data_ids_to_select_from = state["delete_agent_state"]["data_ids_to_delete"]

    """
    we first check fi the suer wants to delete all of them or just some of them
    pass the lsit of ids into a get_data_ids_to_delete function as well as the user's input
    """
    to_delete = select_ids_to_delete(data_ids_to_select_from, user_input) # type: ignore

    if not to_delete:
        return {
            "current_step":"",
            "current_agent": "",
            "messages": state["messages"] + [AIMessage(content=f"Aborted.")]
        }

    # actually perform the deletions
    print("to_delete", to_delete)
    delete_data(to_delete)

    return {
        "current_step": "",
        "current_agent": "",
        "messages": state["messages"] + [AIMessage(content=f"The deletion process has been completed.")]
    }

def build_delete_graph():
    graph = StateGraph(AgentState)

    graph.add_node(delete_agent)
    for step in Step:
        graph.add_node(globals()[step.value])

    graph.add_edge(START, "delete_agent")

    graph.add_conditional_edges(
        "delete_agent",
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



def add_test_data(data: str):
    new_doc = ChromaDocument(
        id=str(uuid.uuid4()),
        asi_one_id="agent1q29tg4sgdzg33gr7u63hfemq4hk54thsya3s7kygurrxg3j8p8f2qlnxz9f",
        document=data,
        source=Source.RESUME.value,
        time_logged=datetime.now().astimezone()
    )

    # Insert into Chroma
    facts_collection.add(
        ids=[new_doc.id],
        documents=[new_doc.document],
        metadatas=[{
            "source": new_doc.source,
            "asi_one_id": new_doc.asi_one_id,
            "time_logged": new_doc.time_logged.isoformat()
        }]
    )

if __name__ == "__main__":
    from pprint import pprint
    graph = build_delete_graph()

    new_chat: AgentState = initialize_agent_state("agent1q29tg4sgdzg33gr7u63hfemq4hk54thsya3s7kygurrxg3j8p8f2qlnxz9f")
    result = graph.invoke(new_chat)
    result["messages"].append(HumanMessage(content="bazalu"))
    result = graph.invoke(AgentState(**result))
    print("result", result)
