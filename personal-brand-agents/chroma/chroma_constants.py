from enum import Enum

FACTS = "user_facts"
QUESTIONS = "questions"

class Source(Enum):
    UNKNOWN = "unknown"
    RESUME = "resume"
    GITHUB = "github"
    LINKEDIN = "linkedin"