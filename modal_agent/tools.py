"""Custom tools for the agent, including AskUser for human-in-the-loop."""

from typing import Any


class AskUserException(Exception):
    """
    Exception raised when the agent needs user input.

    This triggers the checkpoint/resume pattern:
    1. Container sends webhook with question
    2. Container exits (no idle compute)
    3. User responds via /api/agent/respond
    4. NEW container spawns with resume=session_id
    """

    def __init__(self, question: str, context: str, options: list[str] | None = None):
        self.question = question
        self.context = context
        self.options = options or []
        super().__init__(f"AskUser: {question}")


def create_ask_user_tool():
    """
    Create the AskUser MCP tool for the agent.

    When called, this raises AskUserException to checkpoint the agent.
    """
    from claude_agent_sdk import tool

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
        {
            "question": str,
            "context": str,
            "options": list,  # Optional list of suggested answers
        }
    )
    async def ask_user(args: dict[str, Any]) -> dict[str, Any]:
        """
        This tool raises an exception to trigger checkpoint/resume.
        The executor catches this and handles the webhook/exit flow.
        """
        raise AskUserException(
            question=args["question"],
            context=args["context"],
            options=args.get("options", [])
        )

    return ask_user
