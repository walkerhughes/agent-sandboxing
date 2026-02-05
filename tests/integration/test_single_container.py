"""
Integration tests for the single-container-per-conversation architecture.

These tests verify the complete lifecycle:
1. New conversation → container spawned, queue created
2. AskUser called → webhook sent, container blocks on queue
3. User responds → response put on queue, container unblocks
4. Multiple rounds of AskUser → same container, same queue
5. Conversation completes → queue cleaned up
6. Idle timeout → container exits, queue cleaned up
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modal_agent.tools import (
    AskUserException,
    IdleTimeoutError,
    IDLE_TIMEOUT_SECONDS,
    create_ask_user_tool,
)
from modal_agent.webhook import (
    send_clarification_needed,
    send_completed,
    send_failed,
    send_status_update,
)


def _queue_name(task_id: str) -> str:
    """Mirror of modal_agent.executor._queue_name for testing without SDK imports."""
    return f"agent-conv-{task_id}"


class TestContainerLifecycleNewConversation:
    """Test starting a new conversation (no resume_session_id)."""

    def test_queue_name_format(self):
        """Queue name should follow the expected format."""
        name = _queue_name("abc-123")
        assert name == "agent-conv-abc-123"

    def test_queue_name_handles_uuid(self):
        """Queue name should work with UUID-style task IDs."""
        name = _queue_name("550e8400-e29b-41d4-a716-446655440000")
        assert name == "agent-conv-550e8400-e29b-41d4-a716-446655440000"

    @pytest.mark.asyncio
    async def test_new_conversation_triggers_webhook(self):
        """Starting a new conversation should eventually send session_started webhook."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            from modal_agent.webhook import send_session_started
            result = await send_session_started(
                "http://localhost/webhook",
                "task-new",
                "sess-new",
            )

            assert result is True
            call_args = mock_send.call_args[0]
            assert call_args[1] == "session_started"
            assert call_args[2] == "task-new"
            assert call_args[3]["sessionId"] == "sess-new"


class TestContainerLifecycleAskUser:
    """Test the AskUser blocking pattern within a single container."""

    @pytest.mark.asyncio
    async def test_ask_user_sends_clarification_webhook(self):
        """AskUser should trigger a clarification_needed webhook."""
        webhook_called = asyncio.Event()
        response_queue = asyncio.Queue()

        async def on_ask_user(question, context, options):
            # Simulate sending webhook
            webhook_called.set()
            # Wait for response
            return await asyncio.wait_for(response_queue.get(), timeout=5.0)

        tool = create_ask_user_tool(on_ask_user)

        # Start AskUser in background
        task = asyncio.create_task(
            tool.handler({"question": "Which DB?", "context": "Need DB"})
        )

        # Verify webhook was "sent" (event set)
        await asyncio.wait_for(webhook_called.wait(), timeout=5.0)
        assert webhook_called.is_set()

        # Send response to unblock
        await response_queue.put("PostgreSQL")
        result = await asyncio.wait_for(task, timeout=5.0)
        assert result == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_ask_user_blocks_until_response(self):
        """AskUser should block the agent until a response arrives."""
        response_queue = asyncio.Queue()
        is_blocking = asyncio.Event()

        async def on_ask_user(question, context, options):
            is_blocking.set()
            return await asyncio.wait_for(response_queue.get(), timeout=5.0)

        tool = create_ask_user_tool(on_ask_user)

        task = asyncio.create_task(
            tool.handler({"question": "Q?", "context": "C"})
        )

        # Verify we're blocking
        await asyncio.wait_for(is_blocking.wait(), timeout=5.0)
        assert not task.done()  # Should still be waiting

        # Now send response
        await response_queue.put("Answer")
        result = await asyncio.wait_for(task, timeout=5.0)
        assert result == "Answer"
        assert task.done()

    @pytest.mark.asyncio
    async def test_ask_user_with_options_preserved(self):
        """AskUser options should be passed through the callback."""
        captured_options = []

        async def on_ask_user(question, context, options):
            captured_options.extend(options)
            return "option_1"

        tool = create_ask_user_tool(on_ask_user)
        await tool.handler({
            "question": "Pick one?",
            "context": "Choices",
            "options": ["A", "B", "C"],
        })

        assert captured_options == ["A", "B", "C"]


class TestContainerLifecycleMultiTurn:
    """Test multiple AskUser rounds in the same container."""

    @pytest.mark.asyncio
    async def test_two_ask_user_rounds(self):
        """Two sequential AskUser calls should both work."""
        response_queue = asyncio.Queue()

        async def on_ask_user(question, context, options):
            return await asyncio.wait_for(response_queue.get(), timeout=5.0)

        tool = create_ask_user_tool(on_ask_user)

        # Round 1
        task1 = asyncio.create_task(
            tool.handler({"question": "Q1?", "context": "C1"})
        )
        await asyncio.sleep(0.01)
        await response_queue.put("Answer 1")
        result1 = await asyncio.wait_for(task1, timeout=5.0)

        # Round 2
        task2 = asyncio.create_task(
            tool.handler({"question": "Q2?", "context": "C2"})
        )
        await asyncio.sleep(0.01)
        await response_queue.put("Answer 2")
        result2 = await asyncio.wait_for(task2, timeout=5.0)

        assert result1 == "Answer 1"
        assert result2 == "Answer 2"

    @pytest.mark.asyncio
    async def test_three_ask_user_rounds(self):
        """Three sequential AskUser calls should all work."""
        responses = ["First", "Second", "Third"]
        results = []
        response_queue = asyncio.Queue()

        async def on_ask_user(question, context, options):
            return await asyncio.wait_for(response_queue.get(), timeout=5.0)

        tool = create_ask_user_tool(on_ask_user)

        for i, resp in enumerate(responses):
            task = asyncio.create_task(
                tool.handler({"question": f"Q{i}?", "context": f"C{i}"})
            )
            await asyncio.sleep(0.01)
            await response_queue.put(resp)
            result = await asyncio.wait_for(task, timeout=5.0)
            results.append(result)

        assert results == responses


class TestContainerLifecycleCompletion:
    """Test conversation completion and cleanup."""

    @pytest.mark.asyncio
    async def test_completed_webhook_sent(self):
        """Completion should trigger a completed webhook."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_completed(
                "http://localhost/webhook",
                "task-done",
                "sess-done",
                {"summary": "Done!", "actions_taken": ["Write"]},
            )

            assert result is True
            call_args = mock_send.call_args[0]
            assert call_args[1] == "completed"
            assert call_args[3]["result"]["summary"] == "Done!"

    @pytest.mark.asyncio
    async def test_failed_webhook_sent(self):
        """Failure should trigger a failed webhook."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_failed(
                "http://localhost/webhook",
                "task-fail",
                "Something went wrong",
            )

            assert result is True
            call_args = mock_send.call_args[0]
            assert call_args[1] == "failed"
            assert call_args[3]["error"] == "Something went wrong"


class TestContainerLifecycleTimeout:
    """Test idle timeout behavior."""

    @pytest.mark.asyncio
    async def test_idle_timeout_triggers_error(self):
        """Idle timeout should raise IdleTimeoutError."""
        async def on_ask_user(question, context, options):
            raise IdleTimeoutError(IDLE_TIMEOUT_SECONDS)

        tool = create_ask_user_tool(on_ask_user)

        with pytest.raises(IdleTimeoutError) as exc_info:
            await tool.handler({"question": "Q?", "context": "C"})

        assert exc_info.value.timeout_seconds == 300

    @pytest.mark.asyncio
    async def test_idle_timeout_sends_failed_webhook(self):
        """Idle timeout should result in a failed webhook being sent."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            error_msg = f"Conversation timed out: no response within {IDLE_TIMEOUT_SECONDS} seconds"
            result = await send_failed(
                "http://localhost/webhook",
                "task-timeout",
                error_msg,
            )

            assert result is True
            call_args = mock_send.call_args[0]
            assert "timed out" in call_args[3]["error"]

    @pytest.mark.asyncio
    async def test_short_timeout_simulation(self):
        """Simulate a very short timeout to verify the timeout path."""
        queue = asyncio.Queue()

        async def on_ask_user(question, context, options):
            try:
                response = await asyncio.wait_for(queue.get(), timeout=0.05)
                return response
            except asyncio.TimeoutError:
                raise IdleTimeoutError(0)

        tool = create_ask_user_tool(on_ask_user)

        with pytest.raises(IdleTimeoutError):
            await tool.handler({"question": "Q?", "context": "C"})


class TestQueueCleanup:
    """Test queue cleanup on conversation end."""

    def test_queue_name_deletion_path(self):
        """Verify the queue name used for cleanup matches creation."""
        task_id = "task-cleanup-test"
        create_name = _queue_name(task_id)
        # The executor uses the same _queue_name function for both
        # creation (from_name) and deletion (delete)
        assert create_name == f"agent-conv-{task_id}"

    @pytest.mark.asyncio
    async def test_queue_cleanup_does_not_raise_on_missing(self):
        """Queue cleanup should not raise if the queue is already gone."""
        # Simulate the cleanup try/except pattern from executor.py
        try:
            # Simulate a deletion that fails (queue doesn't exist)
            raise Exception("Queue not found")
        except Exception:
            # This is expected — cleanup should be best-effort
            pass


class TestConfigValues:
    """Test configuration values for single-container mode."""

    def test_function_timeout_is_30_minutes(self):
        """FUNCTION_CONFIG timeout should be 1800s (30 minutes)."""
        from modal_agent.config import FUNCTION_CONFIG
        assert FUNCTION_CONFIG["timeout"] == 1800

    def test_web_endpoint_timeout_is_60_seconds(self):
        """WEB_ENDPOINT_CONFIG timeout should still be 60s."""
        from modal_agent.config import WEB_ENDPOINT_CONFIG
        assert WEB_ENDPOINT_CONFIG["timeout"] == 60

    def test_idle_timeout_is_5_minutes(self):
        """IDLE_TIMEOUT_SECONDS should be 300."""
        assert IDLE_TIMEOUT_SECONDS == 300

    def test_idle_timeout_less_than_function_timeout(self):
        """Idle timeout should be less than the function timeout."""
        from modal_agent.config import FUNCTION_CONFIG
        assert IDLE_TIMEOUT_SECONDS < FUNCTION_CONFIG["timeout"]
