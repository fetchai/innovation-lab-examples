"""Unit tests for periodic_cleanup — no GCS calls, no network, no uAgents runtime.

Regression test for the bug where periodic_cleanup always targeted a
hardcoded bucket instead of the bucket configured via ADK_GCS_BUCKET_NAME
(the same env var the artifact service reads).
"""

from unittest.mock import MagicMock, patch

import pytest

from ai_due_diligence_agent.executor import periodic_cleanup


def _make_ctx():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_periodic_cleanup_uses_configured_bucket(monkeypatch):
    monkeypatch.setenv("ADK_GCS_BUCKET_NAME", "my-configured-bucket")

    mock_bucket = MagicMock()
    mock_bucket.list_blobs.return_value = []
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch(
        "ai_due_diligence_agent.executor.storage.Client", return_value=mock_client
    ):
        await periodic_cleanup(_make_ctx())

    mock_client.bucket.assert_called_once_with("my-configured-bucket")


@pytest.mark.asyncio
async def test_periodic_cleanup_falls_back_to_default_bucket(monkeypatch):
    monkeypatch.delenv("ADK_GCS_BUCKET_NAME", raising=False)

    mock_bucket = MagicMock()
    mock_bucket.list_blobs.return_value = []
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch(
        "ai_due_diligence_agent.executor.storage.Client", return_value=mock_client
    ):
        await periodic_cleanup(_make_ctx())

    mock_client.bucket.assert_called_once_with("ai-due-diligence-agent")
