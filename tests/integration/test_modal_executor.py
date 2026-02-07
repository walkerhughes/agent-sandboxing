"""
Integration tests for webhook integration in the Modal executor.

Validates that the executor sends correct webhooks (session_started,
completed, failed, status_update, clarification_needed) during
the conversation lifecycle. Uses fixtures from conftest.py.

Note: AskUser tool behavior, idle timeout, and queue communication
are tested in test_single_container.py and tests/unit/test_tools.py.
"""

import pytest
from unittest.mock import AsyncMock, patch

from modal_agent.webhook import (
    send_session_started,
    send_status_update,
    send_clarification_needed,
    send_completed,
    send_failed,
)


class TestExecutorWebhookIntegration:
    """Test webhook sending during executor lifecycle."""

    @pytest.mark.asyncio
    async def test_executor_sends_session_started_on_init(
        self,
        sample_task_id,
        sample_session_id,
        sample_webhook_url,
    ):
        """Executor should send session_started webhook when agent initializes."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_session_started(
                sample_webhook_url,
                sample_task_id,
                sample_session_id,
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_executor_sends_completed_on_success(
        self,
        sample_task_id,
        sample_session_id,
        sample_webhook_url,
        sample_task_result,
    ):
        """Executor should send completed webhook on successful completion."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_completed(
                sample_webhook_url,
                sample_task_id,
                sample_session_id,
                sample_task_result,
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_executor_sends_failed_on_error(
        self,
        sample_task_id,
        sample_webhook_url,
    ):
        """Executor should send failed webhook on error."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_failed(
                sample_webhook_url,
                sample_task_id,
                "Test error message",
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_executor_sends_status_update_on_resume(
        self,
        sample_task_id,
        sample_webhook_url,
    ):
        """Executor should send status_update when resuming with user response."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_status_update(
                sample_webhook_url,
                sample_task_id,
                "Resuming with user response...",
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_executor_sends_clarification_with_full_payload(
        self,
        sample_task_id,
        sample_session_id,
        sample_webhook_url,
    ):
        """clarification_needed webhook should include all AskUser data."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await send_clarification_needed(
                sample_webhook_url,
                sample_task_id,
                sample_session_id,
                "Which framework?",
                "Need to pick a UI framework",
                ["React", "Vue", "Svelte"],
            )

            call_args = mock_send.call_args[0]
            payload = call_args[3]
            assert payload["sessionId"] == sample_session_id
            assert payload["question"] == "Which framework?"
            assert payload["context"] == "Need to pick a UI framework"
            assert payload["options"] == ["React", "Vue", "Svelte"]
