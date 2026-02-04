"""
Integration tests for webhook functionality.

Tests the Modal -> Vercel webhook communication pattern.
"""

import hashlib
import hmac
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from modal_agent.webhook import (
    send_webhook,
    send_session_started,
    send_status_update,
    send_clarification_needed,
    send_completed,
    send_failed,
)


class TestWebhookSignature:
    """Test HMAC signature generation for webhooks."""

    def test_webhook_creates_valid_signature(self):
        """Webhook should create valid HMAC-SHA256 signature."""
        secret = "test-secret"
        body = '{"type": "test", "taskId": "123"}'

        expected = hmac.new(
            secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()

        # Verify the signature format
        assert len(expected) == 64  # SHA256 hex digest length
        assert all(c in "0123456789abcdef" for c in expected)


class TestSendWebhook:
    """Test the base send_webhook function."""

    @pytest.mark.asyncio
    async def test_send_webhook_success(self, sample_task_id, sample_webhook_url):
        """Webhook should return True on successful POST."""
        with patch("modal_agent.webhook.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await send_webhook(
                sample_webhook_url,
                "status_update",
                sample_task_id,
                {"message": "Test message"},
            )

            assert result is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_webhook_failure(self, sample_task_id, sample_webhook_url):
        """Webhook should return False on failed POST."""
        with patch("modal_agent.webhook.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=500))
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await send_webhook(
                sample_webhook_url,
                "status_update",
                sample_task_id,
                {"message": "Test message"},
            )

            assert result is False


class TestWebhookHelpers:
    """Test the convenience webhook helper functions."""

    @pytest.mark.asyncio
    async def test_send_session_started(self, sample_task_id, sample_session_id, sample_webhook_url):
        """send_session_started should send correct event type."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_session_started(
                sample_webhook_url,
                sample_task_id,
                sample_session_id,
            )

            assert result is True
            mock_send.assert_called_once_with(
                sample_webhook_url,
                "session_started",
                sample_task_id,
                {"sessionId": sample_session_id},
            )

    @pytest.mark.asyncio
    async def test_send_status_update(self, sample_task_id, sample_webhook_url):
        """send_status_update should include tool name when provided."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_status_update(
                sample_webhook_url,
                sample_task_id,
                "Writing file...",
                tool="Write",
            )

            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][3]["message"] == "Writing file..."
            assert call_args[0][3]["tool"] == "Write"

    @pytest.mark.asyncio
    async def test_send_status_update_without_tool(self, sample_task_id, sample_webhook_url):
        """send_status_update should work without tool name."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_status_update(
                sample_webhook_url,
                sample_task_id,
                "Processing...",
            )

            assert result is True
            call_args = mock_send.call_args
            assert "tool" not in call_args[0][3]

    @pytest.mark.asyncio
    async def test_send_clarification_needed(
        self,
        sample_task_id,
        sample_session_id,
        sample_webhook_url,
        sample_clarification,
    ):
        """send_clarification_needed should include question, context, and options."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_clarification_needed(
                sample_webhook_url,
                sample_task_id,
                sample_session_id,
                sample_clarification["question"],
                sample_clarification["context"],
                sample_clarification["options"],
            )

            assert result is True
            call_args = mock_send.call_args
            payload = call_args[0][3]
            assert payload["sessionId"] == sample_session_id
            assert payload["question"] == sample_clarification["question"]
            assert payload["context"] == sample_clarification["context"]
            assert payload["options"] == sample_clarification["options"]

    @pytest.mark.asyncio
    async def test_send_completed(
        self,
        sample_task_id,
        sample_session_id,
        sample_webhook_url,
        sample_task_result,
    ):
        """send_completed should include session ID and result."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_completed(
                sample_webhook_url,
                sample_task_id,
                sample_session_id,
                sample_task_result,
            )

            assert result is True
            call_args = mock_send.call_args
            assert call_args[0][1] == "completed"
            payload = call_args[0][3]
            assert payload["sessionId"] == sample_session_id
            assert payload["result"] == sample_task_result

    @pytest.mark.asyncio
    async def test_send_failed(self, sample_task_id, sample_webhook_url):
        """send_failed should include error message."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            error_msg = "Something went wrong"
            result = await send_failed(
                sample_webhook_url,
                sample_task_id,
                error_msg,
            )

            assert result is True
            call_args = mock_send.call_args
            assert call_args[0][1] == "failed"
            assert call_args[0][3]["error"] == error_msg
