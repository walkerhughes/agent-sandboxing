"""
Modal app configuration for the agent executor.

This creates a Modal web endpoint that can be called from Vercel
to spawn agent execution containers.
"""

import modal

# Create Modal app
app = modal.App("agent-executor")

# Define container image with dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "claude-agent-sdk",
    "httpx",
)

# Agent executor function
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-api-key")],
    timeout=600,  # 10 min max per execution segment
    memory=512,
)
async def execute_agent(
    task_id: str,
    prompt: str,
    webhook_url: str,
    resume_session_id: str | None = None,
    execution_segment: int = 1
):
    """
    Execute the agent in a Modal container.

    This function is called via Modal's web endpoint from Vercel.
    """
    from modal_agent.executor import run_agent
    await run_agent(
        task_id=task_id,
        prompt=prompt,
        webhook_url=webhook_url,
        resume_session_id=resume_session_id,
        execution_segment=execution_segment
    )


# Web endpoint to spawn agent execution
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-api-key")],
)
@modal.web_endpoint(method="POST")
async def spawn_agent(data: dict):
    """
    Web endpoint to spawn agent execution.

    This is called from Vercel when starting or resuming a task.
    The actual execution happens in execute_agent.spawn().
    """
    task_id = data.get("task_id")
    prompt = data.get("prompt")
    webhook_url = data.get("webhook_url")
    resume_session_id = data.get("resume_session_id")
    execution_segment = data.get("execution_segment", 1)

    if not all([task_id, prompt, webhook_url]):
        return {"error": "Missing required fields"}

    # Spawn the agent execution asynchronously
    # This returns immediately while the agent runs in the background
    execute_agent.spawn(
        task_id=task_id,
        prompt=prompt,
        webhook_url=webhook_url,
        resume_session_id=resume_session_id,
        execution_segment=execution_segment
    )

    return {"status": "spawned", "task_id": task_id}


# Local entrypoint for testing
@app.local_entrypoint()
def main():
    """Local test entrypoint."""
    import asyncio

    async def test():
        # Test the executor locally
        from modal_agent.executor import run_agent
        await run_agent(
            task_id="test-task",
            prompt="Create a simple hello.py file that prints 'Hello, World!'",
            webhook_url="http://localhost:3000/api/agent/webhook"
        )

    asyncio.run(test())
