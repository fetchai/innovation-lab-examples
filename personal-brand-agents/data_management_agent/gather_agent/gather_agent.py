from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from data_management_agent.models import *
from data_management_agent.gather_agent.gather_steps import Step
from data_management_agent.gather_agent.gather_helpers import generate_question, is_valid_answer

def gather_agent(state):
    current_step = state["current_step"]
    current_topic = state["gather_agent_state"]["current_topic"]

    is_valid_step = current_step in [s.value for s in Step]

    if not current_step or not is_valid_step or not current_topic:
        # Set a general prompt to guide the LLM to ask thought-provoking, interview-style questions.
        state["gather_agent_state"]["current_topic"] = (
            "Ask a brief interview-style question that prompts the user to describe an accomplishment, trait, or skill. Only provide the question, nothing else."
        )
        state["current_step"] = Step.ASK_QUESTION.value

    return state

def ask_question(state):
    current_topic = state["gather_agent_state"]["current_topic"]

    question = generate_question(current_topic, state["messages"])

    state["gather_agent_state"]["current_question"] = question

    return {
        "current_step": Step.ANSWER_QUESTION.value,
        "messages": state["messages"] + [AIMessage(content=question)]
    }

def answer_question(state):
    current_question = state["gather_agent_state"]["current_question"]
    user_answer = state["messages"][-1].content

    valid = is_valid_answer(current_question, user_answer)

    if valid:
        current_topic = state["gather_agent_state"]["current_topic"]
        followup_question = generate_question(current_topic, state["messages"])

        state["gather_agent_state"]["current_question"] = followup_question

        return {
            "current_step": Step.ANSWER_QUESTION.value,
            "messages": state["messages"] + [
                AIMessage(content=f"That's great! Let's keep going.\n\n{followup_question}")
            ]
        }
    else:
        return {
            "current_step": Step.ANSWER_QUESTION.value,
            "messages": state["messages"] + [AIMessage(content="I'm not sure what you mean. Please try again.")]
        }

def build_gather_graph():
    graph = StateGraph(AgentState)
    graph.add_node(gather_agent)
    for step in Step:
        graph.add_node(globals()[step.value])

    graph.add_edge(START, "gather_agent")

    graph.add_conditional_edges(
        "gather_agent",
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
    graph = build_gather_graph()

