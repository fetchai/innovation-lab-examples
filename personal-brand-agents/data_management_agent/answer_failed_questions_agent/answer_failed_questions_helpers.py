import random
from shared_clients.chroma_client import failed_questions_collection
from chroma.chroma_helpers import insert_resume_fact, get_most_relevant_facts
from brand_agent.brand_agent_helpers import get_brand_agent_id_from_asi_one_id

def get_all_failed_questions(personal_brand_agent_id: str) -> list[dict]:
    """
    Gets all failed questions for a personal brand agent.
    Args:
        personal_brand_agent_id: The personal brand agent ID
    Returns:
        List of dicts with keys: id, document, metadata
    """
    results = failed_questions_collection.get(
        where={"personal_brand_agent_id": personal_brand_agent_id}
    )
    
    questions = []
    if results['ids']:
        for i, question_id in enumerate(results['ids']):
            questions.append({
                "id": question_id,
                "question": results['documents'][i] if results['documents'] else "",
                "metadata": results['metadatas'][i] if results['metadatas'] else {}
            })
    
    return questions

def get_question_by_id(question_id: str) -> dict | None:
    """
    Gets a question by its ID.
    Args:
        question_id: The question ID
    Returns:
        Dict with id, question, metadata or None if not found
    """
    results = failed_questions_collection.get(ids=[question_id])
    
    if results['ids'] and len(results['ids']) > 0:
        return {
            "id": results['ids'][0],
            "question": results['documents'][0] if results['documents'] else "",
            "metadata": results['metadatas'][0] if results['metadatas'] else {}
        }
    
    return None

def get_random_question(personal_brand_agent_id: str) -> dict | None:
    """
    Gets a random failed question for a personal brand agent.
    Args:
        personal_brand_agent_id: The personal brand agent ID
    Returns:
        Dict with id, question, metadata or None if no questions found
    """
    questions = get_all_failed_questions(personal_brand_agent_id)
    
    if not questions:
        return None
    
    return random.choice(questions)

def delete_question(question_id: str):
    """
    Deletes a question from the failed questions collection.
    Args:
        question_id: The question ID to delete
    """
    failed_questions_collection.delete(ids=[question_id])

def delete_all_failed_questions(personal_brand_agent_id: str):
    """
    Deletes all failed questions for a personal brand agent.
    Args:
        personal_brand_agent_id: The personal brand agent ID
    """
    questions = get_all_failed_questions(personal_brand_agent_id)
    if questions:
        question_ids = [q["id"] for q in questions]
        failed_questions_collection.delete(ids=question_ids)

def format_questions_list(questions: list[dict], limit: int | None = None) -> str:
    """
    Formats a list of questions for display.
    Args:
        questions: List of question dicts
        limit: Optional limit on number of questions to show
    Returns:
        Formatted string
    """
    if not questions:
        return "No failed questions found."
    
    if limit:
        questions = questions[:limit]
    
    formatted = []
    for q in questions:
        formatted.append(f"ID: {q['id']}\nQuestion: {q['question']}")
    
    return "\n\n".join(formatted)

def save_answer_as_fact(asi_one_id: str, question: str, answer: str):
    """
    Saves the user's answer as a fact in the facts collection.
    Args:
        asi_one_id: The ASI:One ID
        question: The question that was answered
        answer: The user's answer
    """
    fact = f"Q: {question}\nA: {answer}"
    insert_resume_fact(asi_one_id, fact)

def wants_random_question(user_input: str, messages: list) -> bool:
    """
    Uses LLM to determine if the user wants a random question.
    Args:
        user_input: The user's input
        messages: The conversation history for context
    Returns:
        True if user wants random question, False otherwise
    """
    from shared_clients.llm_client import shared_llm
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    # Build context from recent messages
    context_parts = []
    for msg in messages[-5:]:
        role = "User" if isinstance(msg, HumanMessage) else "Agent"
        context_parts.append(f"{role}: {msg.content}")
    context = "\n".join(context_parts)
    
    prompt = f"""You are determining if the user wants a random question or provided a specific question ID.

Conversation context:
{context}

User's latest input: "{user_input}"

Determine if the user wants a random question. They might say things like:
- "random", "yes", "sure", "ok", "give me a random one", "pick one", etc.

Or they might provide a specific question ID (which would be a UUID-like string).

Respond with only "true" or "false" (lowercase, no quotes)."""
    
    response = shared_llm.invoke([
        SystemMessage(content="You are a helpful assistant that determines user intent. Respond with only 'true' or 'false'."),
        HumanMessage(content=prompt)
    ])
    
    return response.content.strip().lower() == "true" # type: ignore


if __name__ == "__main__":
    # delete_question("7f34414f-9463-419b-96ca-6021e00d8d7d")
    print(get_all_failed_questions("agent1qgerajmgluncfslmdmrgxww463ntt4c90slr0srq4lcc9vmyyavkyg2tzh7"))