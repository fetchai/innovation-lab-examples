import chromadb
from chroma.chroma_constants import *

chroma_client = chromadb.PersistentClient()

def test_embedding():
    collection = chroma_client.create_collection(name="my_collection")
    # collection.add(
    #     ids=["id1", "id2"],
    #     documents=[
    #         "This is a document about pineapple",
    #         "This is a document about oranges"
    #     ]
    # )
    resume_entry = """
    1st Place – LAHacks | Agentic AI, LLM, React, Tailwind, Flask April 2025
    • Won $2,000 with a team of 3 against 1,000+ competitors at UCLA
    • Debugged through 5,000+ lines of AI generated code by applying fundamental knowledge in AI Agents, LLMs,
    Flask, and React
    """

    collection.add(
        ids=["id1", "id2", "id3"],
        documents=[resume_entry, "large codebase", "doc3"],
        metadatas=[{"chapter": 3, "verse": 16}, {"chapter": 3, "verse": 5}, {"chapter": 29, "verse": 11}]
    )

def test_query_resume_facts(query: str):
    collection = chroma_client.get_collection(FACTS)
    result = collection.query(query_texts=query, n_results=1)
    return result

if __name__ == "__main__":
    # Generate sample questions that a user might ask which the given resume_entry could answer.
    resume_questions = [
        "What awards or competitions have you won?",
        "Have you participated in any hackathons?",
        "What technical skills do you have experience with?",
        "Can you tell me about a team project where you handled a large codebase?",
        "What technologies did you use in your most recent project?",
        "Have you ever debugged AI-generated code?",
        "What is your experience with frameworks like Flask and React?",
        "Can you give an example of working with large teams under pressure?",
        "How much prize money have you won in tech competitions?",
        "Have you ever applied AI or LLMs in a real project?",
        "LA Hacks"
    ]

    print("Sample questions the resume_entry could answer:")
    for q in resume_questions:
        result = test_query_resume_facts(q)
        print(f"Question: {q}")
        # result['documents'] is a list of lists, get first hit for this query
        top_doc = result['documents'][0][0] if result['documents'] and result['documents'][0] else None
        print(f"Top matching document: {top_doc}\n")
