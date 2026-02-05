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


class TestAskUserExceptionUnit:
    """Unit tests for AskUserException."""

    def test_exception_is_exception_subclass(self):
        """AskUserException should be a proper Exception subclass."""
        assert issubclass(AskUserException, Exception)

    def test_exception_can_be_raised(self):
        """AskUserException should be raisable."""
        with pytest.raises(AskUserException):
            raise AskUserException(
                question="Test?",
                context="Test context",
            )

    def test_exception_preserves_attributes_after_catch(self):
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

    def test_exception_with_empty_question(self):
        """Exception should handle empty question string."""
        exc = AskUserException(question="", context="Some context")
        assert exc.question == ""

    def test_exception_with_long_context(self):
        """Exception should handle long context strings."""
        long_context = "A" * 10000
        exc = AskUserException(question="Q?", context=long_context)
        assert len(exc.context) == 10000

    def test_exception_with_many_options(self):
        """Exception should handle many options."""
        many_options = [f"Option {i}" for i in range(100)]
        exc = AskUserException(
            question="Choose one?",
            context="Many choices",
            options=many_options,
        )
        assert len(exc.options) == 100

    def test_exception_options_is_list(self):
        """Exception options should always be a list."""
        exc = AskUserException(question="Q?", context="C")
        assert isinstance(exc.options, list)

    def test_exception_str_representation(self):
        """Exception should have useful string representation."""
        exc = AskUserException(
            question="What color?",
            context="Need to choose a color",
        )
        exc_str = str(exc)
        assert "AskUser" in exc_str
        assert "What color?" in exc_str

    def test_exception_defaults_empty_options(self):
        """AskUserException should default to empty options list."""
        exc = AskUserException(
            question="What is your name?",
            context="Need user identification",
        )
        assert exc.options == []

    def test_exception_stores_question(self):
        """AskUserException should store the question."""
        exc = AskUserException(
            question="What is the target directory?",
            context="Need to know where to create files",
        )
        assert exc.question == "What is the target directory?"

    def test_exception_stores_context(self):
        """AskUserException should store the context."""
        exc = AskUserException(
            question="What is the target directory?",
            context="Need to know where to create files",
        )
        assert exc.context == "Need to know where to create files"

    def test_exception_stores_options(self):
        """AskUserException should store options when provided."""
        exc = AskUserException(
            question="Which framework?",
            context="Multiple frameworks available",
            options=["React", "Vue", "Svelte"],
        )
        assert exc.options == ["React", "Vue", "Svelte"]


class TestIdleTimeoutError:
    """Unit tests for IdleTimeoutError."""

    def test_is_exception_subclass(self):
        """IdleTimeoutError should be a proper Exception subclass."""
        assert issubclass(IdleTimeoutError, Exception)

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
        exc = IdleTimeoutError(timeout_seconds=300)
        assert "300" in str(exc)

    def test_can_be_raised_and_caught(self):
        """IdleTimeoutError should be raisable and catchable."""
        with pytest.raises(IdleTimeoutError) as exc_info:
            raise IdleTimeoutError(timeout_seconds=120)
        assert exc_info.value.timeout_seconds == 120


class TestIdleTimeoutConstant:
    """Test the IDLE_TIMEOUT_SECONDS constant."""

    def test_idle_timeout_is_5_minutes(self):
        """IDLE_TIMEOUT_SECONDS should be 300 (5 minutes)."""
        assert IDLE_TIMEOUT_SECONDS == 300


class TestCreateAskUserTool:
    """Test the AskUser tool creation with callback pattern."""

    def test_returns_tool_object(self):
        """create_ask_user_tool should return a Tool dataclass."""
        callback = AsyncMock(return_value="user response")
        tool = create_ask_user_tool(callback)
        assert isinstance(tool, Tool)

    def test_tool_name_is_ask_user(self):
        """Tool name should be 'AskUser'."""
        callback = AsyncMock(return_value="user response")
        tool = create_ask_user_tool(callback)
        assert tool.name == "AskUser"

    def test_tool_has_description(self):
        """Tool should have a non-empty description mentioning clarification."""
        callback = AsyncMock(return_value="user response")
        tool = create_ask_user_tool(callback)
        assert len(tool.description) > 0
        assert "clarification" in tool.description.lower()

    def test_tool_has_callable_handler(self):
        """Tool should have a callable handler."""
        callback = AsyncMock(return_value="user response")
        tool = create_ask_user_tool(callback)
        assert callable(tool.handler)

    @pytest.mark.asyncio
    async def test_handler_calls_callback_with_args(self):
        """Handler should pass question, context, and options to callback."""
        callback = AsyncMock(return_value="user response")
        tool = create_ask_user_tool(callback)

        await tool.handler({
            "question": "Which DB?",
            "context": "Need a database",
            "options": ["Postgres", "MySQL"],
        })

        callback.assert_called_once_with(
            "Which DB?",
            "Need a database",
            ["Postgres", "MySQL"],
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

        await tool.handler({
            "question": "What?",
            "context": "Why?",
        })

        callback.assert_called_once_with("What?", "Why?", [])

    @pytest.mark.asyncio
    async def test_handler_propagates_callback_exception(self):
        """Handler should propagate exceptions from the callback."""
        callback = AsyncMock(side_effect=IdleTimeoutError(300))
        tool = create_ask_user_tool(callback)

        with pytest.raises(IdleTimeoutError):
            await tool.handler({
                "question": "Q?",
                "context": "C",
            })

    @pytest.mark.asyncio
    async def test_handler_propagates_ask_user_exception(self):
        """Handler should propagate AskUserException from callback."""
        callback = AsyncMock(side_effect=AskUserException(
            question="Q?", context="C"
        ))
        tool = create_ask_user_tool(callback)

        with pytest.raises(AskUserException):
            await tool.handler({
                "question": "Q?",
                "context": "C",
            })
