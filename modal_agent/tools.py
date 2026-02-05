"""Custom tools for the agent, including AskUser for human-in-the-loop.

Architecture: Single container per conversation.
When AskUser is called, the tool handler blocks on a modal.Queue waiting
for the user's response (with a 5-minute idle timeout). The container
stays alive for the entire conversation — no checkpoint/resume needed.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

# Idle timeout: how long to wait for a user response before timing out
IDLE_TIMEOUT_SECONDS = 300  # 5 minutes


class AskUserException(Exception):
    """
    Exception raised when the agent needs user input but the session
    is not yet initialized (no session_id available).

    In normal operation with the blocking AskUser tool, this is only
    raised as a fallback error condition.
    """

    def __init__(self, question: str, context: str, options: list[str] | None = None):
        self.question = question
        self.context = context
        self.options = options or []
        super().__init__(f"AskUser: {question}")


class IdleTimeoutError(Exception):
    """Raised when the container times out waiting for a user response."""

    def __init__(self, timeout_seconds: int = IDLE_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"No user response within {timeout_seconds} seconds")


@dataclass
class Tool:
    """Represents a tool that can be used by the agent."""
    name: str
    description: str
    handler: Callable


# Type alias for the callback that sends a webhook and waits for a response
AskUserCallback = Callable[[str, str, list[str]], Awaitable[str]]


def create_ask_user_tool(on_ask_user: AskUserCallback) -> Tool:
    """
    Create the AskUser tool for the agent.

    Args:
        on_ask_user: Async callback that:
            1. Sends the clarification webhook to Vercel
            2. Blocks waiting for the user's response on the modal.Queue
            3. Returns the user's response string

    When called by the agent, this tool invokes the callback and returns
    the user's response as the tool result. The container stays alive
    during the wait — no checkpoint/resume needed.
    """
    description = """Ask the user for clarification when you need more information to proceed.
Use this when:
- The task is ambiguous and could be interpreted multiple ways
- You need to confirm a destructive or irreversible action
- You need specific information the user hasn't provided
- You want to present options for the user to choose from

Do NOT use this for:
- Routine progress updates (use status messages instead)
- Rhetorical questions
- Asking permission for every small step"""

    async def handler(args: dict[str, Any]) -> str:
        """
        Calls the on_ask_user callback to send the webhook and wait for
        the user's response. Returns the response string as the tool result.
        """
        response = await on_ask_user(
            args["question"],
            args["context"],
            args.get("options", []),
        )
        return response

    return Tool(
        name="AskUser",
        description=description,
        handler=handler,
    )
