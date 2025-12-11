from chroma.chroma_models import *
from chroma.chroma_constants import *
import uuid
from datetime import datetime
from shared_clients.chroma_client import facts_collection
from shared_clients.chroma_client import failed_questions_collection

def insert_resume_fact(asi_one_id: str, fact: str) -> ChromaDocument:
    """Takes a resume fact and embeds it with additional metadata needed for chroma, returns the inserted document"""

    # TODO delete all the old resume facts if the user is uploading again to avoid stale information
    new_doc = ChromaDocument(
        id=str(uuid.uuid4()),
        asi_one_id=asi_one_id,
        document=fact,
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

    return new_doc

def get_most_relevant_facts(asi_one_id: str, query: str, n: int) -> list[ChromaDocument]:
    """
    Retrieves the most relevant facts from Chroma for a specific agent based on a query.
    
    Args:
        asi_one_id: The agent ID to filter documents by
        query: The search query to find relevant documents
        n: The number of most relevant documents to return
    
    Returns:
        List of ChromaDocument objects that match the query and belong to the agent
    """
    # Query the collection with filtering by agent_id
    results = facts_collection.query(
        query_texts=[query],
        n_results=n,
        where={"asi_one_id": asi_one_id}
    )
    
    # Convert results to ChromaDocument objects
    documents = []
    if results['documents'] and results['documents'][0]:
        for i, doc_text in enumerate(results['documents'][0]):
            # Extract metadata
            metadata = results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {}
            doc_id = results['ids'][0][i] if results['ids'] and results['ids'][0] else str(uuid.uuid4())
            doc_distance = results['distances'][0][i] if results['distances'] and results['distances'][0] else 0
            if doc_distance > 1.1:
                continue
            # Create ChromaDocument object
            chroma_doc = ChromaDocument(
                id=doc_id,
                asi_one_id=str(metadata['asi_one_id']),
                document=doc_text,
                source=str(metadata['source']),
                time_logged=datetime.fromisoformat(str(metadata['time_logged']))
            )
            documents.append(chroma_doc)
    
    return documents

def insert_question(asi_one_id: str, question: str, personal_brand_agent_id: str) -> bool:
    """Inserts a question into the questions collection"""
    failed_questions_collection.add(
        ids=[str(uuid.uuid4())],
        documents=[question],
        metadatas=[{
            "audience_asi_one_id": asi_one_id,
            "personal_brand_agent_id": personal_brand_agent_id,
            "time_logged": datetime.now().astimezone().isoformat()
        }]
    )
    return True

def similar_question_exists(question: str, personal_brand_agent_id: str) -> bool:
    """
    Checks if a similar question exists with distance <= 0.8 for the same personal brand agent.
    
    Args:
        question: The question text to search for
        personal_brand_agent_id: The personal brand agent ID to filter by
    
    Returns:
        True if a similar question exists with distance <= 0.8, False otherwise
    """
    results = failed_questions_collection.query(
        query_texts=[question],
        n_results=1,
        where={"personal_brand_agent_id": personal_brand_agent_id}
    )
    
    # Check if any results exist and have distance <= 0.8
    if results['distances'] and results['distances'][0]:
        for distance in results['distances'][0]:
            if distance <= 0.8:
                return True
    
    return False


if __name__ == "__main__":
    from shared_clients.chroma_client import chroma_client
    asi_one_id = "agent1q29tg4sgdzg33gr7u63hfemq4hk54thsya3s7kygurrxg3j8p8f2qlnxz9f"
    brand_agent_id = "agent1qgerajmgluncfslmdmrgxww463ntt4c90slr0srq4lcc9vmyyavkyg2tzh7"
    query = "what are ryans skills?"
    insert_question(asi_one_id, query, brand_agent_id)
    res = failed_questions_collection.query(
        query_texts=[query],
        n_results=1,
        where={"personal_brand_agent_id": brand_agent_id}
    )
    print(res)
    
    # # Test similar_question_exists
    # exists = similar_question_exists(query, brand_agent_id)
    # print(f"Similar question exists: {exists}")
    
    # # Test with a different question that shouldn't exist
    # different_query = "What is the capital of Mars?"
    # exists_different = similar_question_exists(different_query, brand_agent_id)
    # print(f"Different question exists: {exists_different}")
