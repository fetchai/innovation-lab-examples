import shared_clients.llm_client as llm_client
from langchain_core.messages import SystemMessage, HumanMessage
from typing import List
from langchain_core.messages import AnyMessage

def generate_question(topic: str, messages: List[AnyMessage]) -> str:
    prompt = f"""
    The conversation history is: {messages}
    Make sure NOT to repeat any questions that have already been asked in the conversation history.
    """
    question = llm_client.shared_llm.invoke([
        SystemMessage(content=prompt),
        SystemMessage(content=f"Generate a question about the following topic: {topic}")
    ])
    return question.content.strip() # type: ignore

def is_valid_answer(question: str,answer: str) -> bool:
    prompt = f"""
    You are a helpful assistant that determines if an answer is valid to a question.
    The question is: {question}
    The answer is: {answer}
    Return True if the answer is valid, False otherwise.
    """
    response = llm_client.shared_llm.invoke([
        SystemMessage(content=prompt),
    ])
    return response.content.strip() == "True" # type: ignore

if __name__ == "__main__":
    pass