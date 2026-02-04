"""
Shared test fixtures and configuration for the Human-in-the-Loop Agent System.

This module provides common fixtures used across unit and integration tests.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock


# -----------------------------------------------------------------------------
# Environment Setup
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key")
    os.environ.setdefault("VERCEL_URL", "http://localhost:3000")


# -----------------------------------------------------------------------------
# Mock Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for webhook tests."""
    client = AsyncMock()
    client.post = AsyncMock(return_value=MagicMock(status_code=200))
    return client


@pytest.fixture
def sample_task_id():
    """Generate a sample task ID for testing."""
    return "test-task-123"


@pytest.fixture
def sample_session_id():
    """Generate a sample session ID for testing."""
    return "test-session-456"


@pytest.fixture
def sample_webhook_url():
    """Sample webhook URL for testing."""
    return "http://localhost:3000/api/agent/webhook"


# -----------------------------------------------------------------------------
# Agent Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_task_prompt():
    """Sample task prompt for testing."""
    return "Create a simple hello.py file that prints 'Hello, World!'"


@pytest.fixture
def sample_clarification():
    """Sample clarification request for testing."""
    return {
        "question": "Which Python version should I use?",
        "context": "The task requires Python, but the version wasn't specified.",
        "options": ["Python 3.11", "Python 3.12", "Latest stable"],
    }


@pytest.fixture
def sample_task_result():
    """Sample successful task result for testing."""
    return {
        "summary": "Created hello.py with a simple print statement",
        "actions_taken": [
            "Used tool: Write",
            "Created file: hello.py",
        ],
        "files_created": ["hello.py"],
    }


# -----------------------------------------------------------------------------
# Webhook Event Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def webhook_session_started(sample_task_id, sample_session_id):
    """Sample session_started webhook event."""
    return {
        "type": "session_started",
        "taskId": sample_task_id,
        "sessionId": sample_session_id,
    }


@pytest.fixture
def webhook_status_update(sample_task_id):
    """Sample status_update webhook event."""
    return {
        "type": "status_update",
        "taskId": sample_task_id,
        "message": "Creating hello.py...",
        "tool": "Write",
    }


@pytest.fixture
def webhook_clarification_needed(sample_task_id, sample_session_id, sample_clarification):
    """Sample clarification_needed webhook event."""
    return {
        "type": "clarification_needed",
        "taskId": sample_task_id,
        "sessionId": sample_session_id,
        **sample_clarification,
    }


@pytest.fixture
def webhook_completed(sample_task_id, sample_session_id, sample_task_result):
    """Sample completed webhook event."""
    return {
        "type": "completed",
        "taskId": sample_task_id,
        "sessionId": sample_session_id,
        "result": sample_task_result,
    }


@pytest.fixture
def webhook_failed(sample_task_id):
    """Sample failed webhook event."""
    return {
        "type": "failed",
        "taskId": sample_task_id,
        "error": "Agent encountered an unexpected error",
    }
