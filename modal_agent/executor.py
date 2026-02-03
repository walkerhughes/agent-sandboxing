"""
Modal agent executor with checkpoint/resume pattern.

Key innovation: Containers never wait for human input.
When AskUser is called:
1. Send webhook with question
2. Exit container (no idle billing)
3. User responds via /api/agent/respond
4. NEW container spawns with resume=session_id
5. Claude SDK loads full context automatically
"""

import asyncio
from typing import Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
)

from .config import app, FUNCTION_CONFIG
from .tools import AskUserException, create_ask_user_tool
from .webhook import (
    send_session_started,
    send_status_update,
    send_clarification_needed,
    send_completed,
    send_failed,
)


@app.function(**FUNCTION_CONFIG)
async def execute_agent(
    task_id: str,
    prompt: str,
    webhook_url: str,
    resume_session_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute the agent loop with checkpoint/resume support.

    Args:
        task_id: Unique task identifier
        prompt: User's task description (or clarification response if resuming)
        webhook_url: Vercel webhook endpoint for events
        resume_session_id: Session ID to resume (None for new task)

    Returns:
        Final result dict with session_id, status, and result/error
    """
    session_id: str | None = None
    actions_taken: list[str] = []

    try:
        # Create custom AskUser tool
        ask_user_tool = create_ask_user_tool()

        # Create MCP server with our tools
        agent_server = create_sdk_mcp_server(
            name="agent",
            version="1.0.0",
            tools=[ask_user_tool]
        )

        # Configure agent options
        options = ClaudeAgentOptions(
            # Use Claude Code's preset system prompt
            system_prompt={"type": "preset", "preset": "claude_code"},
            # Resume from previous session if provided
            resume=resume_session_id,
            # Standard coding tools + our AskUser
            allowed_tools=[
                "Bash", "Read", "Write", "Edit", "Glob", "Grep",
                "mcp__agent__AskUser"
            ],
            # Auto-accept file edits (sandboxed environment)
            permission_mode="acceptEdits",
            # Register our MCP server
            mcp_servers={"agent": agent_server},
            # Limit turns to prevent runaway
            max_turns=50,
        )

        # Run agent with ClaudeSDKClient for better control
        async with ClaudeSDKClient(options=options) as client:
            # Send the prompt
            await client.query(prompt)

            # Process messages
            async for message in client.receive_messages():
                # Capture session ID from init message
                if isinstance(message, SystemMessage):
                    if message.subtype == "init" and "session_id" in message.data:
                        session_id = message.data["session_id"]
                        await send_session_started(webhook_url, task_id, session_id)

                # Track assistant actions
                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            tool_name = block.name
                            actions_taken.append(f"Used tool: {tool_name}")
                            await send_status_update(
                                webhook_url,
                                task_id,
                                f"Using {tool_name}...",
                                tool=tool_name
                            )
                        elif isinstance(block, TextBlock):
                            # Send text updates
                            if len(block.text) > 0:
                                await send_status_update(
                                    webhook_url,
                                    task_id,
                                    block.text[:200]  # Truncate for status
                                )

                # Handle final result
                elif isinstance(message, ResultMessage):
                    session_id = message.session_id

                    if message.is_error:
                        await send_failed(webhook_url, task_id, message.result or "Unknown error")
                        return {
                            "session_id": session_id,
                            "status": "failed",
                            "error": message.result,
                        }

                    # Success!
                    result = {
                        "summary": message.result or "Task completed successfully",
                        "actions_taken": actions_taken,
                        "usage": message.usage,
                        "cost_usd": message.total_cost_usd,
                    }
                    await send_completed(webhook_url, task_id, session_id, result)
                    return {
                        "session_id": session_id,
                        "status": "completed",
                        "result": result,
                    }

    except AskUserException as e:
        # Checkpoint! Send webhook and exit cleanly
        if session_id:
            await send_clarification_needed(
                webhook_url,
                task_id,
                session_id,
                e.question,
                e.context,
                e.options
            )
            return {
                "session_id": session_id,
                "status": "awaiting_input",
                "clarification": {
                    "question": e.question,
                    "context": e.context,
                    "options": e.options,
                }
            }
        else:
            # No session yet - this shouldn't happen
            await send_failed(webhook_url, task_id, "AskUser called before session initialized")
            return {
                "session_id": None,
                "status": "failed",
                "error": "AskUser called before session initialized"
            }

    except Exception as e:
        error_msg = str(e)
        await send_failed(webhook_url, task_id, error_msg)
        return {
            "session_id": session_id,
            "status": "failed",
            "error": error_msg,
        }

    # Should not reach here
    return {
        "session_id": session_id,
        "status": "unknown",
        "error": "Unexpected exit from agent loop"
    }


# Entry point for local testing
if __name__ == "__main__":
    import os

    async def test():
        result = await execute_agent.local(
            task_id="test-123",
            prompt="Create a simple hello.py file that prints 'Hello, World!'",
            webhook_url="http://localhost:3000/api/agent/webhook",
        )
        print(result)

    asyncio.run(test())
