"""
An Example of a chat handler which composes the turn instruction
"""

from steering import SteeringInputs, build_turn_instruction
from app_setup import app


def route_intent(user_message: str) -> str:
    text = user_message.lower()
    if "compare" in text:
        return "compare"
    if "list" in text and "control" in text:
        return "list_controls"
    if "summarize" in text:
        return "summarize"
    return "answer"


INTENT_TO_GOAL = {
    "summarize": "Summarize ACME-42 in plain English.",
    "list_controls": "List mandatory controls from ACME-42 with one-line rationales.",
    "compare": "Compare ACME-42 to ISO 27001 at a high level, return a short markdown table inside the JSON 'answer'.",
    "answer": "Answer the user directly."
}


def get_flag(session_id: str, flag_name: str, default):
    """Get flag value from session (simplified - in production, use session state)."""
    # In production, this would query session state
    return default


def get_tenant_hint(session_id: str):
    """Get tenant hint (simplified - in production, use session state)."""
    # In production, this would query session state
    # e.g., "EU employees only" or None
    return None


def get_last_validation_error(session_id: str):
    """Get last validation error if any (simplified - in production, use session state)."""
    # In production, this would query session state
    return None


def chat(session_id: str, user_message: str, ui_style: str | None = None):
    """Chat handler that composes turn instruction and updates agent."""
    intent = route_intent(user_message)
    goal = INTENT_TO_GOAL.get(intent, f"Answer the user: {user_message[:120]}")
    
    style = ui_style or get_flag(session_id, "style", default="concise")
    max_cites = get_flag(session_id, "max_citations", default=2)
    tenant_hint = get_tenant_hint(session_id)     # e.g., "EU employees only" or None
    corrective = get_last_validation_error(session_id)  # None or short string
    
    turn_instruction = build_turn_instruction(
        SteeringInputs(
            goal=goal,
            style=style,
            max_cites=max_cites,
            tenant_hint=tenant_hint,
            corrective=(f"Your last reply failed validation: {corrective}. Fix it this turn." if corrective else None)
        )
    )
    
    # Update agent's dynamic instruction (static instruction remains cached)
    app.root_agent.instruction = turn_instruction
    
    # Return the instruction (actual agent execution happens via Runner in policy_agent.py)
    return turn_instruction

