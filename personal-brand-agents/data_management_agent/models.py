from langchain_core.messages import AnyMessage
from typing import Any
from langchain_core.load.serializable import Serializable


class GatherAgentState(Serializable):
    current_topic: str
    current_question: str

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)
    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "GatherAgentState":
        return cls(**data)

class DeleteAgentState(Serializable):
    data_ids_to_delete: list[str]
    
    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True
    
    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)
    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DeleteAgentState":
        return cls(**data)

class AnswerFailedQuestionsAgentState(Serializable):
    current_question_id: str
    current_question: str
    
    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True
    
    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)
    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AnswerFailedQuestionsAgentState":
        return cls(**data)

class AgentState(Serializable):
    asi_one_id: str
    current_agent: str
    current_step: str 
    gather_agent_state: GatherAgentState 
    delete_agent_state: DeleteAgentState
    answer_failed_questions_agent_state: AnswerFailedQuestionsAgentState
    messages: list[AnyMessage]
    
    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True
    
    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AgentState":
        return cls(
            asi_one_id=data["asi_one_id"],
            current_agent=data["current_agent"],
            current_step=data["current_step"],
            gather_agent_state=GatherAgentState.from_json(data["gather_agent_state"]),
            delete_agent_state=DeleteAgentState.from_json(data["delete_agent_state"]),
            answer_failed_questions_agent_state=AnswerFailedQuestionsAgentState.from_json(data.get("answer_failed_questions_agent_state", {"current_question_id": "", "current_question": ""})),
            messages=data.get("messages", []),
        )

def initialize_agent_state(asi_one_id: str) -> AgentState:
    return AgentState(
        asi_one_id=asi_one_id,
        current_agent="",
        current_step="",
        gather_agent_state=GatherAgentState(current_topic="", current_question=""),
        delete_agent_state=DeleteAgentState(data_ids_to_delete=[]),
        answer_failed_questions_agent_state=AnswerFailedQuestionsAgentState(current_question_id="", current_question=""),
        messages=[]
    )