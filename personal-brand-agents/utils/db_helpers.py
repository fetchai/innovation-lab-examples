from utils.data_serialization_helpers import *
from langchain_core.load import dumps, loads

def get_most_recent_state_from_agent_db(chat_id: str, ctx):
    """Fetches the most recent AgentState from the agent's db storage.""" 
    chat_data = ctx.storage.get(chat_id)
    if chat_data is None:
        return None
    return loads(chat_data, valid_namespaces=["data_management_agent"])