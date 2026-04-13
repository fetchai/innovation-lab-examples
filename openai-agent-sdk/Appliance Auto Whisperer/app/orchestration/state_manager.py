from __future__ import annotations

from app.models.messages import ChatRequest
from app.models.session_state import SessionState
from app.models.synthesis import SynthesisResult
from app.storage.session_store import SessionStore


class OrchestrationStateManager:
    def __init__(self, sessions: SessionStore) -> None:
        self._sessions = sessions

    async def update_after_turn(
        self,
        session_id: str,
        req: ChatRequest,
        result: SynthesisResult,
    ) -> SessionState:
        st = SessionState(
            session_id=session_id,
            appliance_type=req.appliance_type,
            last_symptoms=req.symptoms,
            turns=[{"summary": result.summary}],
        )
        self._sessions.put_state(session_id, st)
        return st
