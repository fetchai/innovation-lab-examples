import pytest
import time
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from agent import startup
from chat_protocol import handle_message, ChatMessage, TextContent

# --- Integration Test: Bootstrap Flow ---


@pytest.mark.asyncio
async def test_agent_startup_bootstrap_populates_storage():
    """Verify that the agent's startup event correctly fetches and stores tool metadata."""
    mock_ctx = MagicMock()
    mock_ctx.storage = MagicMock()
    # Mock the internal _data dict for the cleanup routine
    mock_ctx.storage._data = {}

    # Mock fetching MCP tools. Patching 'agent.fetch_mcp_tools' because it's imported there.
    with patch("agent.fetch_mcp_tools", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ["tool_a", "tool_b", "tool_c"]

        # Execute startup handler
        await startup(mock_ctx)

        # Verify tools_metadata was saved to storage
        mock_ctx.storage.set.assert_any_call(
            "tools_metadata", ["tool_a", "tool_b", "tool_c"]
        )


# --- Integration Test: Session Management ---


@pytest.mark.asyncio
async def test_chat_handler_stale_session_cleanup():
    """Verify that the chat handler prunes history if the session is older than 2 hours."""
    mock_ctx = AsyncMock()
    mock_ctx.storage = MagicMock()

    sender_addr = "agent1_test_sender"
    h_key = f"history_{sender_addr}"

    # Setup a stale session (last active 5 hours ago to be safe)
    stale_time = time.time() - (5 * 3600)

    def mock_get(key):
        if key == h_key:
            return {
                "messages": [{"role": "user", "content": "old_historical_message"}],
                "last_active": stale_time,
            }
        return None

    mock_ctx.storage.get.side_effect = mock_get

    # Mock incoming message
    msg = ChatMessage(
        msg_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        content=[TextContent(text="Hello fresh message")],
    )

    # Force the time in the handler to be exactly now
    current_time = time.time()

    # Patch both the LLM client and time.time() to ensure stale detection triggers
    with (
        patch(
            "chat_protocol._openai_client.chat.completions.create",
            new_callable=AsyncMock,
        ) as mock_create,
        patch("time.time", return_value=current_time),
    ):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Response", tool_calls=None))
        ]
        mock_create.return_value = mock_response

        await handle_message(mock_ctx, sender_addr, msg)

        # Verify history was wiped (set to a new state that doesn't include 'old_historical_message')
        called_args = mock_ctx.storage.set.call_args_list
        found_cleanup = False
        for call in called_args:
            if call[0][0] == h_key:
                msgs = call[0][1].get("messages", [])
                # Logic: If it reset, the 'old_historical_message' should be GONE.
                history_contents = [m.get("content") for m in msgs]
                if "old_historical_message" not in history_contents:
                    found_cleanup = True

        assert found_cleanup, (
            f"History still contained stale messages. History was: {called_args}"
        )
