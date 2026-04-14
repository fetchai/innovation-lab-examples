import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from mcp_client import _enrich_with_images, execute_mcp_tools

# --- Unit Test: Image Enrichment ---


def test_enrich_with_images_injects_cdn_urls():
    """Verify that _enrich_with_images correctly transforms image_id into a bitmap CDN URL."""
    sample_data = {"offers": [{"id": "123", "image_id": 100085946}]}
    enriched = _enrich_with_images(sample_data)
    expected_url = (
        "https://bitmap.ticketlens.com/image/100085946/300x300?returnCrop=yes"
    )
    assert enriched["offers"][0]["image_url"] == expected_url


def test_enrich_with_images_handles_missing_id():
    """Verify that it doesn't crash if image_id is missing."""
    sample_data = {"offers": [{"id": "124"}]}
    enriched = _enrich_with_images(sample_data)
    assert "image_url" not in enriched["offers"][0]


# --- Unit Test: Persistent Caching Logic ---


@pytest.mark.asyncio
async def test_execute_mcp_tools_cache_hit():
    """Verify that execute_mcp_tools returns cached content if TTL is valid."""
    mock_storage = MagicMock()
    # Setup mock cache entry (valid for 1 hour)
    mock_storage.get.return_value = {
        "content": '{"cached": true}',
        "expiry": time.time() + 3600,
    }

    # Mock tool call object
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "search_tours"
    mock_tool_call.function.arguments = '{"payload": {"query": "London"}}'
    mock_tool_call.id = "call_abc"

    results, network_count = await execute_mcp_tools(mock_storage, [mock_tool_call])

    assert network_count == 0
    assert results[0][1] == '{"cached": true}'
    mock_storage.get.assert_called()


@pytest.mark.asyncio
async def test_execute_mcp_tools_cache_expiry_lazy_cleanup():
    """Verify that expired cache entries are cleaned up and a network call is made."""
    mock_storage = MagicMock()
    # Setup mock cache entry (expired 1 hour ago)
    mock_storage.get.return_value = {
        "content": '{"old": "data"}',
        "expiry": time.time() - 3600,
    }

    # Mock tool call object
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "search_tours"
    mock_tool_call.function.arguments = '{"payload": {"query": "London"}}'
    mock_tool_call.id = "call_abc"

    # Mock the network client and the session
    with (
        patch("mcp_client.streamablehttp_client") as mock_client,
        patch("mcp_client.ClientSession") as mock_session,
    ):
        # 1. Mock streamablehttp_client as a context manager yielding (r, w, s)
        mock_client.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )

        # 2. Mock ClientSession as a context manager yielding the functional session
        mock_sess_instance = AsyncMock()
        mock_sess_instance.call_tool.return_value = MagicMock(
            content=[MagicMock(text='{"fresh": "data"}')]
        )
        mock_session.return_value.__aenter__.return_value = mock_sess_instance

        results, network_count = await execute_mcp_tools(mock_storage, [mock_tool_call])

        assert network_count == 1
        # Expecting indented JSON as per the mcp_client implementation
        assert results[0][1] == '{\n  "fresh": "data"\n}'
