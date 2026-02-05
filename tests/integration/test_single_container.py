"""
Integration tests for the single-container-per-conversation architecture.

These tests verify the container lifecycle:
1. New conversation → queue created, container spawned
2. AskUser called → webhook sent, container blocks on queue
3. User responds → response put on queue, container unblocks
4. Multiple rounds of AskUser → same container, same queue
5. Idle timeout → container exits with error
6. Queue naming → deterministic per task_id

Note: Webhook payload tests are in test_modal_executor.py.
Note: AskUser tool unit tests are in tests/unit/test_tools.py.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from modal_agent.tools import (
    IdleTimeoutError,
    IDLE_TIMEOUT_SECONDS,
    create_ask_user_tool,
)
from modal_agent.webhook import send_session_started


def _queue_name(task_id: str) -> str:
    """Mirror of modal_agent.executor._queue_name for testing without SDK imports."""
    return f"agent-conv-{task_id}"


class TestQueueNaming:
    """Test queue name generation."""

    def test_queue_name_format(self):
        """Queue name should follow the expected format."""
        assert _queue_name("abc-123") == "agent-conv-abc-123"

    def test_queue_name_handles_uuid(self):
        """Queue name should work with UUID-style task IDs."""
        assert _queue_name("550e8400-e29b-41d4-a716-446655440000") == \
            "agent-conv-550e8400-e29b-41d4-a716-446655440000"

    def test_queue_name_is_deterministic(self):
        """Same task_id should always produce the same queue name."""
        assert _queue_name("task-123") == _queue_name("task-123")

    def test_queue_name_is_unique_per_task(self):
        """Different task_ids should produce different queue names."""
        assert _queue_name("task-1") != _queue_name("task-2")


class TestNewConversation:
    """Test starting a new conversation."""

    @pytest.mark.asyncio
    async def test_new_conversation_triggers_webhook(self):
        """Starting a new conversation should send session_started webhook."""
        with patch("modal_agent.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await send_session_started(
                "http://localhost/webhook", "task-new", "sess-new",
            )

            assert result is True
            call_args = mock_send.call_args[0]
            assert call_args[1] == "session_started"
            assert call_args[3]["sessionId"] == "sess-new"


class TestAskUserBlocking:
    """Test the AskUser blocking pattern within a single container."""

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

        await asyncio.wait_for(is_blocking.wait(), timeout=5.0)
        assert not task.done()

        await response_queue.put("Answer")
        result = await asyncio.wait_for(task, timeout=5.0)
        assert result == "Answer"

    @pytest.mark.asyncio
    async def test_full_flow_webhook_then_queue_response(self):
        """Full flow: send webhook → block on queue → user responds → return."""
        webhook_sent = asyncio.Event()
        response_queue = asyncio.Queue()

        async def on_ask_user(question, context, options):
            webhook_sent.set()
            return await asyncio.wait_for(response_queue.get(), timeout=5.0)

        tool = create_ask_user_tool(on_ask_user)
        task = asyncio.create_task(
            tool.handler({"question": "Which DB?", "context": "Need DB"})
        )

        await asyncio.wait_for(webhook_sent.wait(), timeout=5.0)
        await response_queue.put("PostgreSQL")
        result = await asyncio.wait_for(task, timeout=5.0)
        assert result == "PostgreSQL"

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


class TestMultiTurnConversation:
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


class TestIdleTimeout:
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
    async def test_short_timeout_simulation(self):
        """Simulate a very short timeout to verify the timeout path."""
        queue = asyncio.Queue()

        async def on_ask_user(question, context, options):
            try:
                return await asyncio.wait_for(queue.get(), timeout=0.05)
            except asyncio.TimeoutError:
                raise IdleTimeoutError(0)

        tool = create_ask_user_tool(on_ask_user)

        with pytest.raises(IdleTimeoutError):
            await tool.handler({"question": "Q?", "context": "C"})


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

    def test_idle_timeout_less_than_function_timeout(self):
        """Idle timeout should be less than the function timeout."""
        from modal_agent.config import FUNCTION_CONFIG
        assert IDLE_TIMEOUT_SECONDS < FUNCTION_CONFIG["timeout"]
