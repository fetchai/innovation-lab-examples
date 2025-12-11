from enum import Enum

class Step(Enum):
    ASK_NAME = "ask_name"
    VERIFY_NAME = "verify_name" 
    ASK_ROLE = "ask_role"
    VERIFY_ROLE = "verify_role"
    ASK_CONTACT = "ask_contact"
    VERIFY_CONTACT = "verify_contact"
    FALLBACK = "fallback"   
    COMPLETE = "complete"