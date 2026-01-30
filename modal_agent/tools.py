"""Custom tools for the agent, including AskUser with checkpoint pattern."""

from claude_agent_sdk import tool, create_sdk_mcp_server
from typing import Any


class AskUserException(Exception):
    """
    Raised when AskUser is called to signal checkpoint.

    This exception triggers the checkpoint/resume pattern:
    1. Executor catches this exception
    2. Sends clarification_needed webhook
    3. Container exits (no idle billing)
    4. User responds via /api/agent/respond
    5. New container spawns with resume=session_id
    """

    def __init__(self, question: str, context: str, options: list[str] | None = None):
        self.question = question
        self.context = context
        self.options = options or []
        super().__init__(f"AskUser: {question}")


@tool(
    "AskUser",
    """Ask the user for clarification when you need more information to proceed.

Use this when:
- The task is ambiguous and could be interpreted multiple ways
- You need to confirm a destructive or irreversible action
- You need specific information the user hasn't provided
- You want to present options for the user to choose from

Do NOT use this for:
- Routine progress updates (use status messages instead)
- Rhetorical questions
- Asking permission for every small step""",
    {"question": str, "context": str, "options": list}
)
async def ask_user(args: dict[str, Any]) -> dict[str, Any]:
    """
    This tool triggers the checkpoint pattern:
    1. Raises exception to signal checkpoint
    2. Executor catches it and sends webhook
    3. Container exits cleanly
    """
    raise AskUserException(
        question=args["question"],
        context=args["context"],
        options=args.get("options", [])
    )


# Create MCP server with the AskUser tool
agent_tools = create_sdk_mcp_server(
    name="agent",
    version="1.0.0",
    tools=[ask_user]
)
