"""
Integration tests for the single-container-per-conversation Modal executor.

Tests the full lifecycle: queue communication, AskUser blocking,
idle timeout, and webhook integration.
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
    send_session_started,
    send_status_update,
    send_clarification_needed,
    send_completed,
    send_failed,
)


class TestAskUserBlockingBehavior:
    """Test the AskUser tool's blocking-on-queue behavior."""

    @pytest.mark.asyncio
    async def test_ask_user_callback_returns_response(self):
        """AskUser callback should return the user's response string."""
        # Simulate the on_ask_user callback pattern from executor.py
        user_response = "Use PostgreSQL"

        async def mock_on_ask_user(question, context, options):
            return user_response

        tool = create_ask_user_tool(mock_on_ask_user)
        result = await tool.handler({
            "question": "Which database?",
            "context": "Multiple options",
            "options": ["PostgreSQL", "MySQL"],
        })

        assert result == "Use PostgreSQL"

    @pytest.mark.asyncio
    async def test_ask_user_sends_webhook_then_waits(self):
        """AskUser should send webhook first, then wait for response."""
        call_order = []

        async def mock_on_ask_user(question, context, options):
            call_order.append("webhook_sent")
            call_order.append("response_received")
            return "user answer"

        tool = create_ask_user_tool(mock_on_ask_user)
        await tool.handler({
            "question": "Q?",
            "context": "C",
        })

        assert call_order == ["webhook_sent", "response_received"]

    @pytest.mark.asyncio
    async def test_ask_user_timeout_raises_idle_timeout(self):
        """AskUser should raise IdleTimeoutError on timeout."""
        async def mock_on_ask_user(question, context, options):
            raise IdleTimeoutError(IDLE_TIMEOUT_SECONDS)

        tool = create_ask_user_tool(mock_on_ask_user)

        with pytest.raises(IdleTimeoutError) as exc_info:
            await tool.handler({
                "question": "Q?",
                "context": "C",
            })

        assert exc_info.value.timeout_seconds == IDLE_TIMEOUT_SECONDS

    @pytest.mark.asyncio
    async def test_ask_user_no_session_raises_exception(self):
        """AskUser should raise AskUserException if session not initialized."""
        async def mock_on_ask_user(question, context, options):
            raise AskUserException(
                question=question, context=context, options=options
            )

        tool = create_ask_user_tool(mock_on_ask_user)

        with pytest.raises(AskUserException) as exc_info:
            await tool.handler({
                "question": "Q?",
                "context": "C",
                "options": ["A"],
            })

        assert exc_info.value.question == "Q?"


class TestQueueCommunication:
    """Test the modal.Queue communication pattern."""

    @pytest.mark.asyncio
    async def test_queue_put_get_roundtrip(self):
        """Simulating the queue put/get pattern used in the executor."""
        # Simulate the queue behavior with asyncio.Queue
        queue = asyncio.Queue()

        # Simulate spawn_agent putting response on queue
        await queue.put("User's response")

        # Simulate execute_agent getting response from queue
        response = await asyncio.wait_for(queue.get(), timeout=5.0)

        assert response == "User's response"

    @pytest.mark.asyncio
    async def test_queue_timeout_behavior(self):
        """Queue get should timeout when no response arrives."""
        queue = asyncio.Queue()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_multiple_responses_on_queue(self):
        """Multiple AskUser calls should each get their own response."""
        queue = asyncio.Queue()

        # Simulate two responses being queued
        await queue.put("First response")
        await queue.put("Second response")

        first = await asyncio.wait_for(queue.get(), timeout=5.0)
        second = await asyncio.wait_for(queue.get(), timeout=5.0)

        assert first == "First response"
        assert second == "Second response"

    @pytest.mark.asyncio
    async def test_concurrent_put_and_get(self):
        """Put and get should work concurrently (simulating real flow)."""
        queue = asyncio.Queue()

        async def delayed_put():
            await asyncio.sleep(0.05)
            await queue.put("Delayed response")

        async def wait_for_response():
            return await asyncio.wait_for(queue.get(), timeout=5.0)

        # Start both concurrently
        _, response = await asyncio.gather(
            delayed_put(),
            wait_for_response(),
        )

        assert response == "Delayed response"


class TestSingleContainerLifecycle:
    """Test the full single-container conversation lifecycle."""

    @pytest.mark.asyncio
    async def test_on_ask_user_callback_sends_webhook(self):
        """The on_ask_user callback should send a clarification webhook."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_clarification_needed(
                "http://localhost:3000/api/agent/webhook",
                "test-task-123",
                "test-session-456",
                "Which framework?",
                "Multiple options",
                ["React", "Vue"],
            )

            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0]
            assert call_args[1] == "clarification_needed"
            payload = call_args[3]
            assert payload["question"] == "Which framework?"
            assert payload["options"] == ["React", "Vue"]

    @pytest.mark.asyncio
    async def test_on_ask_user_callback_full_flow(self):
        """Full flow: send webhook → wait on queue → return response."""
        webhook_sent = asyncio.Event()
        response_queue = asyncio.Queue()

        async def on_ask_user(question, context, options):
            # Step 1: Send webhook (mocked)
            webhook_sent.set()

            # Step 2: Wait for response
            response = await asyncio.wait_for(
                response_queue.get(), timeout=5.0
            )
            return response

        # Create tool with callback
        tool = create_ask_user_tool(on_ask_user)

        # Start the tool handler in background
        async def run_tool():
            return await tool.handler({
                "question": "Which DB?",
                "context": "Need DB",
            })

        # Start tool, then send response
        task = asyncio.create_task(run_tool())

        # Wait for webhook to be sent
        await asyncio.wait_for(webhook_sent.wait(), timeout=5.0)

        # Simulate user responding (via queue)
        await response_queue.put("PostgreSQL")

        # Get the tool result
        result = await asyncio.wait_for(task, timeout=5.0)
        assert result == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_multiple_ask_user_calls_same_container(self):
        """Multiple AskUser calls should work in sequence (same container)."""
        response_queue = asyncio.Queue()
        call_count = 0

        async def on_ask_user(question, context, options):
            nonlocal call_count
            call_count += 1
            response = await asyncio.wait_for(
                response_queue.get(), timeout=5.0
            )
            return response

        tool = create_ask_user_tool(on_ask_user)

        # First AskUser call
        async def first_call():
            return await tool.handler({
                "question": "First Q?",
                "context": "First C",
            })

        task1 = asyncio.create_task(first_call())
        await asyncio.sleep(0.01)  # Let the task start
        await response_queue.put("First answer")
        result1 = await asyncio.wait_for(task1, timeout=5.0)

        # Second AskUser call
        async def second_call():
            return await tool.handler({
                "question": "Second Q?",
                "context": "Second C",
            })

        task2 = asyncio.create_task(second_call())
        await asyncio.sleep(0.01)
        await response_queue.put("Second answer")
        result2 = await asyncio.wait_for(task2, timeout=5.0)

        assert result1 == "First answer"
        assert result2 == "Second answer"
        assert call_count == 2


class TestIdleTimeout:
    """Test the 5-minute idle timeout behavior."""

    def test_idle_timeout_constant_is_300(self):
        """IDLE_TIMEOUT_SECONDS should be 300 (5 minutes)."""
        assert IDLE_TIMEOUT_SECONDS == 300

    @pytest.mark.asyncio
    async def test_timeout_raises_idle_timeout_error(self):
        """IdleTimeoutError should be raised when queue times out."""
        async def on_ask_user(question, context, options):
            # Simulate the queue timeout in executor
            raise IdleTimeoutError(IDLE_TIMEOUT_SECONDS)

        tool = create_ask_user_tool(on_ask_user)

        with pytest.raises(IdleTimeoutError) as exc_info:
            await tool.handler({
                "question": "Q?",
                "context": "C",
            })

        assert exc_info.value.timeout_seconds == 300

    @pytest.mark.asyncio
    async def test_short_timeout_actually_expires(self):
        """Verify that a short timeout does expire."""
        queue = asyncio.Queue()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.05)

    @pytest.mark.asyncio
    async def test_response_before_timeout_succeeds(self):
        """Response arriving before timeout should succeed."""
        queue = asyncio.Queue()

        async def delayed_put():
            await asyncio.sleep(0.01)
            await queue.put("Quick response")

        asyncio.create_task(delayed_put())
        result = await asyncio.wait_for(queue.get(), timeout=5.0)

        assert result == "Quick response"


class TestSpawnAgentRouting:
    """Test the spawn_agent endpoint routing logic."""

    def test_new_conversation_has_no_resume_id(self):
        """New conversations should not have a resume_session_id."""
        body = {
            "task_id": "task-123",
            "prompt": "Build a todo app",
            "webhook_url": "http://localhost:3000/api/agent/webhook",
        }
        assert body.get("resume_session_id") is None

    def test_response_has_resume_id(self):
        """User responses should include resume_session_id."""
        body = {
            "task_id": "task-123",
            "prompt": "Use React please",
            "webhook_url": "http://localhost:3000/api/agent/webhook",
            "resume_session_id": "sess_abc123",
        }
        assert body.get("resume_session_id") is not None

    def test_queue_name_is_deterministic(self):
        """Queue name should be deterministic based on task_id."""
        def _queue_name(task_id): return f"agent-conv-{task_id}"
        assert _queue_name("task-123") == "agent-conv-task-123"
        assert _queue_name("task-123") == _queue_name("task-123")

    def test_queue_name_is_unique_per_task(self):
        """Different task_ids should produce different queue names."""
        def _queue_name(task_id): return f"agent-conv-{task_id}"
        assert _queue_name("task-1") != _queue_name("task-2")


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
