from pydantic import BaseModel 
from typing import List, Literal

"""
We have to store these as pydantic models because agent db only stores json
"""

class JsonMesasge(BaseModel):
    role: Literal["human", "ai"]
    content: str

class JsonAgentState(BaseModel):
    current_step: int
    current_agent: str
    messages: List[JsonMesasge]