from enum import Enum

class Step(Enum):
    ASK_NAME = "ask_name"
    VERIFY_NAME = "verify_name"
    ASK_RESUME = "ask_resume"
    STORE_FACTS_FROM_RESUME = "store_facts_from_resume"
    COMPLETE = "complete"
    INVALID_STEP = "invalid_step"