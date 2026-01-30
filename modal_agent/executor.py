"""
Agent executor using Claude Agent SDK with checkpoint/resume pattern.

This module implements the core agent loop that:
1. Creates or resumes a Claude Agent SDK session
2. Handles tool execution
3. Catches AskUserException for checkpoint/resume
4. Sends webhooks for status updates
"""

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage, ToolUseBlock, SystemMessage
from modal_agent.tools import AskUserException, agent_tools
from modal_agent.webhook import (
    send_session_started,
    send_status_update,
    send_clarification_needed,
    send_completed,
    send_failed
)
import os


async def run_agent(
    task_id: str,
    prompt: str,
    webhook_url: str,
    resume_session_id: str | None = None,
    execution_segment: int = 1
) -> None:
    """
    Execute the agent with checkpoint/resume support.

    Args:
        task_id: Unique task identifier
        prompt: The task prompt (or user's response on resume)
        webhook_url: URL to send webhook events to
        resume_session_id: Session ID to resume (None for new session)
        execution_segment: Which segment of execution this is (1, 2, 3...)
    """
    session_id: str | None = None

    try:
        # Configure Claude Agent SDK
        options = ClaudeAgentOptions(
            resume=resume_session_id,  # None for new, session_id for resume
            mcp_servers={"agent": agent_tools},
            allowed_tools=[
                "Bash", "Read", "Write", "Edit", "Glob", "Grep",
                "mcp__agent__AskUser"
            ],
            permission_mode="acceptEdits",
            cwd="/tmp/workspace",
            model="claude-sonnet-4-5-20250514"
        )

        # Create workspace directory
        os.makedirs("/tmp/workspace", exist_ok=True)

        print(f"Starting agent - task: {task_id}, segment: {execution_segment}")
        print(f"Resume session: {resume_session_id or 'NEW'}")
        print(f"Prompt: {prompt[:100]}...")

        # Run agent loop
        async for message in query(prompt=prompt, options=options):
            # Handle different message types
            if isinstance(message, SystemMessage):
                # System messages include session info
                if message.subtype == "init" and "session_id" in message.data:
                    session_id = message.data["session_id"]
                    print(f"Session ID: {session_id}")

                    # Send session_started webhook (only for new sessions)
                    if not resume_session_id:
                        await send_session_started(webhook_url, task_id, session_id)

            elif isinstance(message, AssistantMessage):
                # Process assistant response
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        # Send status update for tool usage
                        await send_status_update(
                            webhook_url,
                            task_id,
                            f"Using {block.name}...",
                            tool=block.name
                        )

            elif isinstance(message, ResultMessage):
                # Final result
                session_id = message.session_id
                print(f"Task completed - session: {session_id}")

                # Send completed webhook
                await send_completed(
                    webhook_url,
                    task_id,
                    session_id,
                    summary=message.result or "Task completed successfully",
                    actions_taken=[]
                )

    except AskUserException as e:
        # CHECKPOINT: Agent needs user input
        print(f"Checkpoint - AskUser: {e.question}")

        if not session_id:
            # This shouldn't happen, but handle gracefully
            await send_failed(webhook_url, task_id, "Session ID not captured before AskUser")
            return

        # Send clarification webhook
        await send_clarification_needed(
            webhook_url,
            task_id,
            session_id,
            question=e.question,
            context=e.context,
            options=e.options
        )

        # Container exits here - no idle waiting!
        print("Container exiting after AskUser (checkpoint)")

    except Exception as e:
        # Handle any other errors
        print(f"Agent failed: {e}")
        await send_failed(webhook_url, task_id, str(e))
        raise
