"""
Modal agent executor with checkpoint/resume pattern.

Key innovation: Containers never wait for human input.
When AskUser is called:
1. Send webhook with question
2. Exit container (no idle billing)
3. User responds via /api/agent/respond
4. NEW container spawns with resume=session_id
5. Claude SDK loads full context automatically

Session Management (per Claude Agent SDK docs):
https://platform.claude.com/docs/en/agent-sdk/sessions

- First query creates a session, returns session_id in init message
- Subsequent queries can resume with: ClaudeAgentOptions(resume=session_id)
- The SDK automatically handles loading conversation history and context
"""

import asyncio
from typing import Any

import modal
from fastapi import Request
from fastapi.responses import JSONResponse

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

from .config import app, FUNCTION_CONFIG, WEB_ENDPOINT_CONFIG, CLAUDE_FOLDER_PATH
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
    chat_context: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Execute the agent loop with checkpoint/resume support.

    Args:
        task_id: Unique task identifier
        prompt: User's task description (or clarification response if resuming)
        webhook_url: Vercel webhook endpoint for events
        resume_session_id: Session ID to resume (None for new task)
        chat_context: Previous chat messages for context (new sessions only)
                      Format: [{"role": "user"|"assistant", "content": "..."}]

    Returns:
        Final result dict with session_id, status, and result/error
    """
    session_id: str | None = None
    actions_taken: list[str] = []

    try:
        # Create custom AskUser tool for human-in-the-loop
        ask_user_tool = create_ask_user_tool()

        # Create MCP server with our custom tools
        agent_server = create_sdk_mcp_server(
            name="agent",
            version="1.0.0",
            tools=[ask_user_tool]
        )

        # Build system prompt with optional chat context appended
        # Using append keeps context available throughout the session
        system_prompt_config: dict = {"type": "preset", "preset": "claude_code"}

        if chat_context and not resume_session_id:
            # New session with chat history: append context to system prompt
            context_lines = [
                "",
                "# Prior Conversation Context",
                "The user had the following conversation before starting this action task.",
                "Use this context to understand their goals and any decisions already made.",
                "",
            ]
            for msg in chat_context:
                role = msg.get("role", "user").capitalize()
                content = msg.get("content", "")
                context_lines.append(f"**{role}**: {content}")
            context_lines.append("")

            system_prompt_config["append"] = "\n".join(context_lines)
            print(f"[Agent] Appending {len(chat_context)} chat messages to system prompt")

        # Configure agent options
        # Per docs: use resume=session_id to continue a previous session
        options = ClaudeAgentOptions(
            # Specify model to use (SDK accepts: "sonnet", "opus", "haiku")
            model="sonnet",
            # Use Claude Code's preset system prompt (with optional append for chat context)
            system_prompt=system_prompt_config,
            # Resume from previous session if provided
            # The SDK automatically handles loading conversation history
            resume=resume_session_id,
            # Standard coding tools + our custom AskUser + Task for subagents
            allowed_tools=[
                "Bash", "Read", "Write", "Edit", "Glob", "Grep",
                "Task",  # Required for invoking subagents
                "AskUserQuestion",  # Built-in tool for clarifications
                "mcp__agent__AskUser"  # Our custom MCP tool
            ],
            # Auto-accept file edits (sandboxed environment)
            permission_mode="acceptEdits",
            # Register our MCP server with custom tools
            mcp_servers={"agent": agent_server},
            # Limit turns to prevent runaway
            max_turns=50,
            # Load project settings to discover .claude folder plugins
            # This enables filesystem-based agents and commands
            setting_sources=["project"],
            # Set working directory to /app where .claude folder is mounted in container
            cwd=CLAUDE_FOLDER_PATH,
        )

        # Log resume status and construct the actual prompt to send
        if resume_session_id:
            # Resuming: user's response continues the existing conversation
            print(f"[Agent] Resuming session: {resume_session_id}")
            actual_prompt = prompt
        else:
            # New session: invoke /plan-feature skill with user's feature description
            print("[Agent] Starting new session with /plan-feature")
            actual_prompt = f"/plan-feature {prompt}"

        # Run agent with ClaudeSDKClient
        async with ClaudeSDKClient(options=options) as client:
            # Send the prompt (either /plan-feature <desc> or user's clarification response)
            await client.query(actual_prompt)

            # Process messages
            async for message in client.receive_messages():
                # Capture session ID from init message
                # Per docs: session_id is in message.data.get('session_id') for init messages
                if isinstance(message, SystemMessage):
                    if message.subtype == "init":
                        # Extract session_id using safe dict access
                        if hasattr(message, 'data') and isinstance(message.data, dict):
                            session_id = message.data.get("session_id")
                            if session_id:
                                print(f"[Agent] Session ID obtained: {session_id}")
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
                    # Get session_id from result message
                    if hasattr(message, 'session_id') and message.session_id:
                        session_id = message.session_id

                    if message.is_error:
                        error_msg = message.result or "Unknown error"
                        print(f"[Agent] Task failed: {error_msg}")
                        await send_failed(webhook_url, task_id, error_msg)
                        return {
                            "session_id": session_id,
                            "status": "failed",
                            "error": error_msg,
                        }

                    # Success!
                    print("[Agent] Task completed successfully")
                    result = {
                        "summary": message.result or "Task completed successfully",
                        "actions_taken": actions_taken,
                        "usage": getattr(message, 'usage', None),
                        "cost_usd": getattr(message, 'total_cost_usd', None),
                    }
                    await send_completed(webhook_url, task_id, session_id, result)
                    return {
                        "session_id": session_id,
                        "status": "completed",
                        "result": result,
                    }

    except AskUserException as e:
        # Checkpoint! Send webhook and exit cleanly
        # Container will exit after this - no idle billing
        print(f"[Agent] AskUser checkpoint: {e.question}")
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
            error_msg = "AskUser called before session initialized"
            print(f"[Agent] Error: {error_msg}")
            await send_failed(webhook_url, task_id, error_msg)
            return {
                "session_id": None,
                "status": "failed",
                "error": error_msg
            }

    except Exception as e:
        error_msg = str(e)
        print(f"[Agent] Unexpected error: {error_msg}")
        import traceback
        traceback.print_exc()
        await send_failed(webhook_url, task_id, error_msg)
        return {
            "session_id": session_id,
            "status": "failed",
            "error": error_msg,
        }

    # Should not reach here
    print("[Agent] Warning: Unexpected exit from agent loop")
    return {
        "session_id": session_id,
        "status": "unknown",
        "error": "Unexpected exit from agent loop"
    }


# =============================================================================
# Web Endpoint - HTTP trigger for spawning agent containers
# =============================================================================

@app.function(**WEB_ENDPOINT_CONFIG)
@modal.fastapi_endpoint(method="POST")
async def spawn_agent(request: Request) -> JSONResponse:
    """
    HTTP endpoint to spawn an agent task.

    POST body:
    {
        "task_id": "uuid",
        "prompt": "user task description",
        "webhook_url": "https://your-app.vercel.app/api/agent/webhook",
        "resume_session_id": "optional-session-id-for-resume",
        "chat_context": [{"role": "user", "content": "..."}, ...] (optional)
    }

    Returns immediately with 202 Accepted, then runs agent asynchronously.
    """
    try:
        body = await request.json()

        task_id = body.get("task_id")
        prompt = body.get("prompt")
        webhook_url = body.get("webhook_url")
        resume_session_id = body.get("resume_session_id")
        chat_context = body.get("chat_context")  # Optional: prior chat messages

        if not task_id or not prompt or not webhook_url:
            return JSONResponse(
                {"error": "Missing required fields: task_id, prompt, webhook_url"},
                status_code=400
            )

        # Log what we're doing
        if resume_session_id:
            print(f"[Spawn] Resuming task {task_id} with session {resume_session_id}")
        else:
            context_msg = f" with {len(chat_context)} chat messages" if chat_context else ""
            print(f"[Spawn] Starting new task {task_id}{context_msg}")

        # Spawn the agent execution asynchronously (non-blocking)
        # This creates a new container that runs independently
        execute_agent.spawn(
            task_id=task_id,
            prompt=prompt,
            webhook_url=webhook_url,
            resume_session_id=resume_session_id,
            chat_context=chat_context,  # Pass chat history for new sessions
        )

        return JSONResponse(
            {"status": "accepted", "task_id": task_id},
            status_code=202
        )

    except Exception as e:
        print(f"[Spawn] Error: {str(e)}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


# Entry point for local testing
if __name__ == "__main__":
    async def test():
        result = await execute_agent.local(
            task_id="test-123",
            prompt="Create a simple hello.py file that prints 'Hello, World!'",
            webhook_url="http://localhost:3000/api/agent/webhook",
        )
        print(result)

    asyncio.run(test())
