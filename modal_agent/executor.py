"""
Modal agent executor — single container per conversation.

Architecture change from checkpoint/resume:
- OLD: Container exits on AskUser, new container spawns with resume=session_id
- NEW: Single container stays alive for the entire conversation. AskUser blocks
       on a modal.Queue waiting for the user's response (5-min idle timeout).

Benefits:
- Simpler architecture (no checkpoint/resume)
- Filesystem persists across turns (enables Modal Volumes later)
- Lower cold-start overhead (one container boot per conversation)

Communication pattern:
- New conversation: spawn_agent creates Queue, spawns execute_agent
- User responds: spawn_agent puts response on the existing Queue
- AskUser tool: blocks on Queue.get(timeout=300), returns response to agent
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
from .tools import (
    AskUserException,
    IdleTimeoutError,
    IDLE_TIMEOUT_SECONDS,
    create_ask_user_tool,
)
from .webhook import (
    send_session_started,
    send_status_update,
    send_clarification_needed,
    send_completed,
    send_failed,
)


def _queue_name(task_id: str) -> str:
    """Generate a deterministic queue name for a conversation."""
    return f"agent-conv-{task_id}"


@app.function(**FUNCTION_CONFIG)
async def execute_agent(
    task_id: str,
    prompt: str,
    webhook_url: str,
    chat_context: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Execute the agent loop for a full conversation in a single container.

    The container stays alive until the conversation completes, fails,
    or times out waiting for user input (5-min idle timeout per AskUser call).

    Args:
        task_id: Unique task identifier (also used as queue name suffix)
        prompt: User's initial task description
        webhook_url: Vercel webhook endpoint for events
        chat_context: Previous chat messages for context
                      Format: [{"role": "user"|"assistant", "content": "..."}]

    Returns:
        Final result dict with session_id, status, and result/error
    """
    session_id: str | None = None
    actions_taken: list[str] = []

    # Get the conversation queue for receiving user responses
    response_queue = modal.Queue.from_name(
        _queue_name(task_id), create_if_missing=True
    )

    try:
        # Define the AskUser callback that blocks on the queue
        async def on_ask_user(
            question: str, context: str, options: list[str]
        ) -> str:
            nonlocal session_id

            if not session_id:
                raise AskUserException(
                    question=question, context=context, options=options
                )

            # 1. Notify Vercel that we need user input
            await send_clarification_needed(
                webhook_url, task_id, session_id,
                question, context, options
            )
            print(f"[Agent] Waiting for user response (timeout={IDLE_TIMEOUT_SECONDS}s)")

            # 2. Block waiting for user response on the queue
            try:
                response = await asyncio.to_thread(
                    response_queue.get, timeout=IDLE_TIMEOUT_SECONDS
                )
            except Exception as e:
                print(f"[Agent] Queue.get raised: {type(e).__name__}: {e}")
                raise IdleTimeoutError(IDLE_TIMEOUT_SECONDS) from e

            if response is None:
                raise IdleTimeoutError(IDLE_TIMEOUT_SECONDS)

            print(f"[Agent] Received user response: {str(response)[:100]}")

            # 3. Notify Vercel that we're running again
            await send_status_update(
                webhook_url, task_id, "Resuming with user response..."
            )

            return str(response)

        # Create AskUser tool with the blocking callback
        ask_user_tool = create_ask_user_tool(on_ask_user)

        # Create MCP server with our custom tools
        agent_server = create_sdk_mcp_server(
            name="agent",
            version="1.0.0",
            tools=[ask_user_tool]
        )

        # Build system prompt with optional chat context appended
        system_prompt_config: dict = {"type": "preset", "preset": "claude_code"}

        if chat_context:
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

        # Configure agent options — no resume needed, single container
        options = ClaudeAgentOptions(
            model="sonnet",
            system_prompt=system_prompt_config,
            allowed_tools=[
                "Bash", "Read", "Write", "Edit", "Glob", "Grep",
                "Task",
                "AskUserQuestion",
                "mcp__agent__AskUser"
            ],
            permission_mode="acceptEdits",
            mcp_servers={"agent": agent_server},
            max_turns=50,
            setting_sources=["project"],
            cwd=CLAUDE_FOLDER_PATH,
        )

        print("[Agent] Starting new session with /plan-feature")
        actual_prompt = f"/plan-feature {prompt}"

        # Run agent — the AskUser tool blocks on queue, so the agent
        # loop runs continuously in this single container
        async with ClaudeSDKClient(options=options) as client:
            await client.query(actual_prompt)

            async for message in client.receive_messages():
                # Capture session ID from init message
                if isinstance(message, SystemMessage):
                    if message.subtype == "init":
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
                            if block.text:
                                await send_status_update(
                                    webhook_url,
                                    task_id,
                                    block.text[:200]
                                )

                # Handle final result
                elif isinstance(message, ResultMessage):
                    if hasattr(message, 'session_id') and message.session_id:
                        session_id = message.session_id

                    if message.is_error:
                        error_msg = message.result or "Unknown error"
                        print(f"[Agent] Task failed with error: {error_msg}")
                        print(f"[Agent] ResultMessage details - result: {message.result}, "
                              f"session_id: {getattr(message, 'session_id', 'N/A')}, "
                              f"subtype: {getattr(message, 'subtype', 'N/A')}")

                        for attr in ['error', 'error_code', 'error_details', 'data']:
                            if hasattr(message, attr):
                                val = getattr(message, attr)
                                if val:
                                    print(f"[Agent] Additional error info - {attr}: {val}")
                                    if error_msg == "Unknown error" and isinstance(val, str):
                                        error_msg = val

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
        # AskUser called before session initialized — shouldn't happen in normal flow
        error_msg = f"AskUser called before session initialized: {e.question}"
        print(f"[Agent] Error: {error_msg}")
        await send_failed(webhook_url, task_id, error_msg)
        return {
            "session_id": None,
            "status": "failed",
            "error": error_msg,
        }

    except IdleTimeoutError as e:
        # Container timed out waiting for user response
        print(f"[Agent] Idle timeout after {e.timeout_seconds}s")
        error_msg = f"Conversation timed out: no response within {e.timeout_seconds} seconds"
        await send_failed(webhook_url, task_id, error_msg)
        return {
            "session_id": session_id,
            "status": "failed",
            "error": error_msg,
        }

    except Exception as e:
        import traceback

        error_msg = str(e)
        full_traceback = traceback.format_exc()

        print(f"[Agent] Unexpected error: {error_msg}")
        print(f"[Agent] Exception type: {type(e).__name__}")
        print(f"[Agent] Full traceback:\n{full_traceback}")

        detailed_error = f"{type(e).__name__}: {error_msg}"
        await send_failed(webhook_url, task_id, detailed_error)
        return {
            "session_id": session_id,
            "status": "failed",
            "error": detailed_error,
        }

    finally:
        # Clean up the queue when conversation ends
        try:
            queue_name = _queue_name(task_id)
            print(f"[Agent] Cleaning up queue: {queue_name}")
            # Modal queues created with from_name are persistent;
            # we attempt deletion but don't fail if it errors
            modal.Queue.delete(queue_name)
        except Exception as cleanup_err:
            print(f"[Agent] Queue cleanup warning: {cleanup_err}")

    # Should not reach here
    print("[Agent] Warning: Unexpected exit from agent loop")
    return {
        "session_id": session_id,
        "status": "unknown",
        "error": "Unexpected exit from agent loop"
    }


# =============================================================================
# Web Endpoint — HTTP trigger for starting conversations and sending responses
# =============================================================================

@app.function(**WEB_ENDPOINT_CONFIG)
@modal.fastapi_endpoint(method="POST")
async def spawn_agent(request: Request) -> JSONResponse:
    """
    HTTP endpoint to start a conversation or send a user response.

    For NEW conversations (no resume_session_id):
        - Creates a modal.Queue for the conversation
        - Spawns execute_agent as a background function
        - Returns 202 Accepted

    For RESPONSES to clarifications (has resume_session_id):
        - Puts the user's response on the existing Queue
        - The blocked execute_agent picks it up and continues
        - Returns 202 Accepted

    POST body:
    {
        "task_id": "uuid",
        "prompt": "user task description or clarification response",
        "webhook_url": "https://your-app.vercel.app/api/agent/webhook",
        "resume_session_id": "optional — presence indicates a response, not a new task",
        "chat_context": [{"role": "user", "content": "..."}, ...] (optional, new only)
    }
    """
    try:
        body = await request.json()

        task_id = body.get("task_id")
        prompt = body.get("prompt")
        webhook_url = body.get("webhook_url")
        resume_session_id = body.get("resume_session_id")
        chat_context = body.get("chat_context")

        if not task_id or not prompt or not webhook_url:
            return JSONResponse(
                {"error": "Missing required fields: task_id, prompt, webhook_url"},
                status_code=400
            )

        if resume_session_id:
            # RESPOND: Put the user's response on the existing container's queue
            print(f"[Spawn] Routing response to existing container for task {task_id}")
            response_queue = modal.Queue.from_name(_queue_name(task_id))
            response_queue.put(prompt)

            return JSONResponse(
                {"status": "accepted", "task_id": task_id, "action": "response_queued"},
                status_code=202
            )
        else:
            # NEW CONVERSATION: Create queue and spawn container
            context_msg = f" with {len(chat_context)} chat messages" if chat_context else ""
            print(f"[Spawn] Starting new conversation for task {task_id}{context_msg}")

            # Pre-create the queue so it's ready when execute_agent starts
            modal.Queue.from_name(_queue_name(task_id), create_if_missing=True)

            # Spawn the agent in a new container (non-blocking)
            execute_agent.spawn(
                task_id=task_id,
                prompt=prompt,
                webhook_url=webhook_url,
                chat_context=chat_context,
            )

            return JSONResponse(
                {"status": "accepted", "task_id": task_id, "action": "container_spawned"},
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
