from enum import Enum

class Agent(Enum):
    QUESTION_ANSWERER = "question_answerer"
    AUDIENCE_ONBOARDER = "audience_onboarder"
    FALLBACK = "fallback_agent"

AGENT_DESCRIPTIONS = {
    Agent.QUESTION_ANSWERER: "Answers questions on behalf of a user's personal brand. Use this whenever you receive a question that can be answered on behalf of a user. For example, asking where they work or what they do.",
    Agent.AUDIENCE_ONBOARDER: "Onboards a user as an audience member.",
    Agent.FALLBACK: "Handles unsupported user intents.",
}