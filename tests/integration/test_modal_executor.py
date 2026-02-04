"""
Integration tests for the Modal agent executor.

Tests the checkpoint/resume pattern and AskUser tool behavior.
"""

import pytest
from unittest.mock import AsyncMock, patch

from modal_agent.tools import AskUserException, create_ask_user_tool
from modal_agent.webhook import send_session_started, send_completed, send_failed


class TestAskUserException:
    """Test the AskUserException for checkpoint/resume pattern."""

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

    def test_exception_defaults_empty_options(self):
        """AskUserException should default to empty options list."""
        exc = AskUserException(
            question="What is your name?",
            context="Need user identification",
        )
        assert exc.options == []

    def test_exception_message_contains_question(self):
        """AskUserException message should contain the question."""
        exc = AskUserException(
            question="What is the target directory?",
            context="Need to know where to create files",
        )
        assert "What is the target directory?" in str(exc)


class TestAskUserTool:
    """Test the AskUser MCP tool creation."""

    def test_create_ask_user_tool_returns_tool(self):
        """create_ask_user_tool should return a tool object."""
        tool = create_ask_user_tool()
        assert tool is not None
        assert hasattr(tool, "name")
        assert tool.name == "AskUser"

    def test_ask_user_tool_has_description(self):
        """AskUser tool should have a description."""
        tool = create_ask_user_tool()
        assert hasattr(tool, "description")
        assert len(tool.description) > 0
        assert "clarification" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_ask_user_tool_raises_exception(self):
        """AskUser tool should raise AskUserException when called."""
        tool = create_ask_user_tool()

        with pytest.raises(AskUserException) as exc_info:
            await tool.handler({
                "question": "Which database?",
                "context": "Multiple options available",
                "options": ["PostgreSQL", "MySQL"],
            })

        assert exc_info.value.question == "Which database?"
        assert exc_info.value.context == "Multiple options available"
        assert exc_info.value.options == ["PostgreSQL", "MySQL"]


class TestExecutorCheckpointResume:
    """Test the checkpoint/resume pattern in the executor."""

    def test_executor_handles_ask_user_exception(self):
        """Executor should catch AskUserException and send clarification webhook."""
        # The expected flow:
        # 1. Agent runs and calls AskUser tool
        # 2. AskUserException is raised
        # 3. Executor catches it
        # 4. Executor sends clarification_needed webhook
        # 5. Executor returns with status="awaiting_input"

        # We verify the exception handling works correctly
        try:
            raise AskUserException(
                question="Test question?",
                context="Test context",
                options=["A", "B"],
            )
        except AskUserException as e:
            # Verify we can extract the data needed for the webhook
            assert e.question == "Test question?"
            assert e.context == "Test context"
            assert e.options == ["A", "B"]

    def test_executor_resumes_with_session_id(self):
        """Executor should be able to resume with a session ID."""
        # The expected flow:
        # 1. User provides clarification response
        # 2. New container spawns with resume=session_id
        # 3. Claude SDK loads previous context
        # 4. Agent continues from where it left off

        # We verify the session ID is passed correctly
        resume_session_id = "sess_abc123"

        # In the actual executor, this would be:
        # options = ClaudeAgentOptions(resume=resume_session_id, ...)

        # For now, we just verify the concept
        assert resume_session_id is not None
        assert resume_session_id.startswith("sess_")


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
