from langchain_core.messages import HumanMessage
from shared_clients.llm_client import shared_llm
from shared_clients.chroma_client import facts_collection

def is_valid_delete_request(user_input: str) -> bool:
    """Check if the user's message is a valid delete request"""
    response = shared_llm.invoke([
        HumanMessage(content=f"""
        You are validating user input.

        The user was asked: "What data would you like to delete?"

        Determine if their response below *answers that question* by providing the data to delete.

        Respond with only 'yes' or 'no'.

        User response: "{user_input}"
        """)
    ])
    answer = response.content.strip().lower()  # type: ignore
    return answer == "yes"

def delete_data(ids_to_delete: list[str]):
    """Delete the data from the database."""
    facts_collection.delete(ids=ids_to_delete)

def select_ids_to_delete(data_ids_to_delete: list[str], user_input: str) -> list[str]:
    """Select the ids to delete based on the user's input."""
    response = shared_llm.invoke([
        HumanMessage(content=f"""
        You are selecting the ids to delete based on the user's input.

        The user was asked: "Please list the ids of the data you want to delete or 'all' to delete all of them."
        If the user doesn't want to delete any of the data, return an empty string.
        If the user responds with some ids, match the ids with the data ids.

        The data ids to are: {data_ids_to_delete}
        The user's input is: {user_input}

        Return the ids to delete separated by commas. Do not include any other text.
        """)
    ])
    if response.content.strip().lower() == "": # type: ignore
        return []
    ids_to_delete = response.content.strip().split(",") # type: ignore
    return ids_to_delete


def is_affirmative_response(user_input: str) -> bool:
    """Check if the user's message is an affirmative response"""
    response = shared_llm.invoke([
        HumanMessage(content=f"""
        You are validating user input.

        Did the user answer affirmatively to the question: "Would you like to delete the data?"

        Respond with only 'yes' or 'no'.

        User response: "{user_input}"
        """)
    ])
    answer = response.content.strip().lower()  # type: ignore
    return answer == "yes"

def to_delete_from_user_input(user_input: str, asi_one_id: str) -> list[str]:
    """Extract the data to delete from the user's input"""
    documents_and_ids = []

    result = facts_collection.query(query_texts=user_input,n_results=5, where={"asi_one_id": asi_one_id})
    for i in range(len(result["documents"][0])): # type: ignore
        if result["distances"][0][i] <= 1.5: # type: ignore
            documents_and_ids.append((result["documents"][0][i], result["ids"][0][i])) # type: ignore

    return documents_and_ids

if __name__ == "__main__":
    docs = to_delete_from_user_input("college", "agent1q29tg4sgdzg33gr7u63hfemq4hk54thsya3s7kygurrxg3j8p8f2qlnxz9f")
    print(docs)