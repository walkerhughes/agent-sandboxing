"""Modal app configuration for the agent executor."""

import modal

# Create Modal app
app = modal.App("human-in-the-loop-agent")

# Container image with dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "claude-agent-sdk",
        "httpx",
    )
)

# Function configuration
FUNCTION_CONFIG = {
    "image": image,
    "secrets": [modal.Secret.from_name("anthropic-api-key")],
    "timeout": 600,  # 10 min max per execution segment
    "retries": 0,    # Don't retry - let Vercel handle
}
