from chroma.chroma_models import ChromaDocument
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_openai import ChatOpenAI
from shared_clients.supabase_client import supabase

def answer_query_with_facts(chroma_documents: List[ChromaDocument], query: str, llm: ChatOpenAI) -> str:
    """
    Uses GPT to answer a query based on provided facts from ChromaDocuments.
    
    Args:
        chroma_documents: List of ChromaDocument objects containing relevant facts
        query: The question/query to answer
        llm: The language model to use for generating responses
    
    Returns:
        String response from GPT based on the provided facts
    """
    if not chroma_documents:
        return "I don't have any relevant information to answer your question."
    
    # Prepare the facts for the prompt with source information
    facts_text = "\n".join([f"- {doc.document} (Source: {doc.source})" for doc in chroma_documents])
    
    # Create the prompt
    prompt = f"""You are acting as the personal brand agent representing an individual. Your role is to answer questions about this person using the provided facts. You are not the individual themself, but an agent communicating on their behalf, drawing only from the information given to you.

    Do not use first person ("I", "my") or speak as if you are the subject of the facts. Always refer to the individual in the third person (e.g., "Ryan" or "the candidate").

    Base your answers strictly on the facts given below. When you make reasonable inferences (for example, deducing that if someone can fix AI-generated code, they can also address common coding issues), explicitly state that an inference is being made and explain your reasoning.

    Do not invent information not directly suggested or implied by the facts, and avoid adding irrelevant details.

    When referencing information, mention the source if relevant (e.g., "According to the resume..." or "From the LinkedIn profile...").

    Facts:
    {facts_text}

    Query: {query}

    Please provide a clear, accurate answer based on the facts above, phrased in the third person. If you make an inference, say so and explain your reasoning. If the facts or reasonable inferences are not sufficient to answer, say so clearly."""

    try:
        response = llm.invoke([
            SystemMessage(content="You are a helpful assistant that answers questions based strictly on provided facts. Never make up information."),
            HumanMessage(content=prompt)
        ])
        return response.content.strip() # type: ignore
    
    except Exception as e:
        return f"Sorry, I encountered an error while generating a response: {str(e)}"

def get_asi_one_id_from_brand_agent_id(brand_agent_id: str) -> str:
    """
    Gets the ASI:One ID from the brand agent ID.
    Args:
        brand_agent_id: The ID of the brand agent
    
    Returns:
        The ASI:One ID
    """
    result = supabase.table("personal_brand_asi_one_relationships").select("asi_one_id").eq("personal_brand_agent_id", brand_agent_id).execute()
    return result.data[0]["asi_one_id"] if result.data else None # type: ignore

def get_brand_agent_id_from_asi_one_id(asi_one_id: str) -> str:
    """
    Gets the personal brand agent ID from the ASI:One ID.
    Args:
        asi_one_id: The ASI:One ID
    Returns:
        The personal brand agent ID
    """
    result = supabase.table("personal_brand_asi_one_relationships").select("personal_brand_agent_id").eq("asi_one_id", asi_one_id).execute()
    return result.data[0]["personal_brand_agent_id"] if result.data else None # type: ignore

if __name__ == "__main__":
    from chroma.chroma_helpers import *
    from dotenv import load_dotenv
    load_dotenv()

    # asi_one_id = "agent1q29tg4sgdzg33gr7u63hfemq4hk54thsya3s7kygurrxg3j8p8f2qlnxz9f"
    brand_agent_id = 'agent1qt3qh62838nhu4u7j86azn55ylvfm767d9rhk5lae4qe8lnyspvhu7zxrsx'
    # query = "What are ryans skills?"
    # query = "can ryan fix my ai coded app"
    # query = "does ryan have experience "
    # query = "What is Ryan's educational background?"
    # query = "Has Ryan worked with machine learning before?"
    # query = "List any programming languages Ryan is proficient in."
    # query = "Is Ryan available for freelance projects?"
    query = "Can Ryan lead a software project?"
    # query = "Has Ryan contributed to any open source projects?"
    # query = "What certifications does Ryan hold?"
    # query = "What are Ryan's professional experiences?"
    # query = "Has Ryan worked with AI before?"
    # query = "What is Ryan's technical expertise?"
    # query = "Can Ryan build a web application?"
    # query = "Has Ryan worked with databases before?"
    # query = "What is Ryan's experience with cloud computing?"
    # query = "Can Ryan create an AI agent?"

    res = get_asi_one_id_from_brand_agent_id(brand_agent_id)
    print(res)