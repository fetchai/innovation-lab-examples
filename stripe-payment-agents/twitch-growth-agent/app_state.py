"""Global singletons shared across protocols and interval handlers."""

from twitch.eventsub import ListenerManager
from twitch.recap import get_buffer

listener_manager = ListenerManager(
    on_event_factory=lambda uid: (
        lambda event_type, event: get_buffer(uid).add(event_type, event)
    )
)

# Maps each user's ASI:One sender address to their most recent inbound session
# object, so proactive cards from on_interval can route into the open thread.
_user_sessions: "dict[str, object]" = {}
