from __future__ import annotations

from app.agents.orchestrator_agent import OrchestratorAgent
from app.models.messages import ChatRequest
from app.models.synthesis import SynthesisResult
from app.orchestration.correlation import new_correlation_id
from app.storage.session_store import SessionStore


class Coordinator:
    def __init__(self) -> None:
        self._orch = OrchestratorAgent()
        self._sessions = SessionStore()

    async def run(self, req: ChatRequest) -> tuple[SynthesisResult, dict, str]:
        cid = new_correlation_id()
        session_id = req.session_id or self._sessions.new_session()
        req = req.model_copy(update={"session_id": session_id})
        self._sessions.touch(session_id)

        result, structured = await self._orch.run(req, correlation_id=cid)
        return result, structured, session_id
