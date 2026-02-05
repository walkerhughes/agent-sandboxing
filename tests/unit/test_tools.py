"""
Unit tests for Modal agent tools.

Tests the AskUser tool, AskUserException, and IdleTimeoutError in isolation.
"""

import pytest
from unittest.mock import AsyncMock

import sys
sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0])

from modal_agent.tools import (
    AskUserException,
    IdleTimeoutError,
    IDLE_TIMEOUT_SECONDS,
    Tool,
    create_ask_user_tool,
)


class TestAskUserException:
    """Unit tests for AskUserException."""

    def test_preserves_all_attributes(self):
        """Exception attributes should be accessible after catching."""
        try:
            raise AskUserException(
                question="What is X?",
                context="Need X for Y",
                options=["Option 1", "Option 2"],
            )
        except AskUserException as e:
            assert e.question == "What is X?"
            assert e.context == "Need X for Y"
            assert e.options == ["Option 1", "Option 2"]

    def test_defaults_empty_options(self):
        """AskUserException should default to empty options list."""
        exc = AskUserException(question="Q?", context="C")
        assert exc.options == []

    def test_str_representation(self):
        """Exception should have useful string representation."""
        exc = AskUserException(question="What color?", context="Need to choose")
        assert "AskUser" in str(exc)
        assert "What color?" in str(exc)

    def test_handles_edge_cases(self):
        """Exception should handle empty strings and large inputs."""
        empty = AskUserException(question="", context="Some context")
        assert empty.question == ""

        long_ctx = AskUserException(question="Q?", context="A" * 10000)
        assert len(long_ctx.context) == 10000

        many_opts = AskUserException(
            question="Choose?", context="C",
            options=[f"Option {i}" for i in range(100)],
        )
        assert len(many_opts.options) == 100


class TestIdleTimeoutError:
    """Unit tests for IdleTimeoutError."""

    def test_default_timeout(self):
        """IdleTimeoutError should use IDLE_TIMEOUT_SECONDS by default."""
        exc = IdleTimeoutError()
        assert exc.timeout_seconds == IDLE_TIMEOUT_SECONDS

    def test_custom_timeout(self):
        """IdleTimeoutError should accept a custom timeout."""
        exc = IdleTimeoutError(timeout_seconds=60)
        assert exc.timeout_seconds == 60

    def test_message_contains_timeout(self):
        """Error message should mention the timeout duration."""
        assert "300" in str(IdleTimeoutError(timeout_seconds=300))

    def test_idle_timeout_is_5_minutes(self):
        """IDLE_TIMEOUT_SECONDS should be 300 (5 minutes)."""
        assert IDLE_TIMEOUT_SECONDS == 300


class TestCreateAskUserTool:
    """Test the AskUser tool creation with callback pattern."""

    def test_returns_tool_with_correct_metadata(self):
        """create_ask_user_tool should return a Tool with name and description."""
        callback = AsyncMock(return_value="response")
        tool = create_ask_user_tool(callback)
        assert isinstance(tool, Tool)
        assert tool.name == "AskUser"
        assert "clarification" in tool.description.lower()
        assert callable(tool.handler)

    @pytest.mark.asyncio
    async def test_handler_calls_callback_with_args(self):
        """Handler should pass question, context, and options to callback."""
        callback = AsyncMock(return_value="response")
        tool = create_ask_user_tool(callback)

        await tool.handler({
            "question": "Which DB?",
            "context": "Need a database",
            "options": ["Postgres", "MySQL"],
        })

        callback.assert_called_once_with(
            "Which DB?", "Need a database", ["Postgres", "MySQL"],
        )

    @pytest.mark.asyncio
    async def test_handler_returns_callback_response(self):
        """Handler should return the callback's response string."""
        callback = AsyncMock(return_value="Use Postgres")
        tool = create_ask_user_tool(callback)

        result = await tool.handler({
            "question": "Which DB?",
            "context": "Need a database",
        })

        assert result == "Use Postgres"

    @pytest.mark.asyncio
    async def test_handler_defaults_empty_options(self):
        """Handler should default to empty list when options not provided."""
        callback = AsyncMock(return_value="response")
        tool = create_ask_user_tool(callback)

        await tool.handler({"question": "What?", "context": "Why?"})

        callback.assert_called_once_with("What?", "Why?", [])

    @pytest.mark.asyncio
    async def test_handler_propagates_exceptions(self):
        """Handler should propagate exceptions from the callback."""
        for exc in [IdleTimeoutError(300), AskUserException(question="Q?", context="C")]:
            callback = AsyncMock(side_effect=exc)
            tool = create_ask_user_tool(callback)

            with pytest.raises(type(exc)):
                await tool.handler({"question": "Q?", "context": "C"})
