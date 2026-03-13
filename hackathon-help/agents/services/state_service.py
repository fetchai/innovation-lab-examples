from agents.models.models import SharedAgentState


class InMemoryStateService:
    """
    In-memory store for SharedAgentState keyed by chat_session_id.

    Demonstrates the persistence pattern — swap this for a database or Redis
    and nothing else in the pipeline needs to change.
    """

    def __init__(self) -> None:
        self._store: dict[str, SharedAgentState] = {}

    def set_state(self, chat_session_id: str, state: SharedAgentState) -> None:
        self._store[chat_session_id] = state

    def get_state(self, chat_session_id: str) -> SharedAgentState | None:
        return self._store.get(chat_session_id)


state_service = InMemoryStateService()
