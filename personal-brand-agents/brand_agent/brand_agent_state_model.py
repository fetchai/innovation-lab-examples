from langgraph.graph import MessagesState

class BrandAgentState(MessagesState):
    asi_one_id: str
    brand_agent_id: str
    current_agent: str
    current_step: str 

def initialize_agent_state(asi_one_id: str, brand_agent_id: str) -> BrandAgentState:
    return BrandAgentState(
        asi_one_id=asi_one_id,
        brand_agent_id=brand_agent_id,
        current_agent="",
        current_step="",
        messages=[]
    )


