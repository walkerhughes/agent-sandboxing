"""Modal app configuration for the agent executor.

Architecture: Single container per conversation.
The container stays alive for the full conversation, using a modal.Queue
for inter-request communication. Timeout is 30 minutes (hard limit),
with a 5-minute idle timeout per AskUser call.
"""

from pathlib import Path

import modal

# Create Modal app
app = modal.App("human-in-the-loop-agent")

# Path to this directory (modal_agent/)
MODAL_AGENT_DIR = Path(__file__).parent.absolute()

# Container image with dependencies
# Agent SDK requires: Node.js 18+ and Claude Code CLI
image = (
    modal.Image.debian_slim(python_version="3.11")
    # Install Node.js 18
    .apt_install("curl", "ca-certificates")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_18.x | bash -",
        "apt-get install -y nodejs",
    )
    # Install Claude Code CLI
    .run_commands(
        "curl -fsSL https://claude.ai/install.sh | bash",
    )
    # Install Python dependencies
    .pip_install(
        "claude-agent-sdk",
        "httpx",
        "fastapi",  # Required for @modal.web_endpoint
    )
    # Add .claude folder with skills and agents (Modal 1.0+ API)
    # This makes the /plan-feature command and subagents available in the container
    .add_local_dir(
        str(MODAL_AGENT_DIR / ".claude"),
        remote_path="/app/.claude",
    )
)

# Secrets used by the agent
SECRETS = [
    modal.Secret.from_name("anthropic-api-key"),
    modal.Secret.from_name("webhook-secret"),
]

# Function configuration for agent executor
# Timeout is 30 minutes — the container handles the full conversation
FUNCTION_CONFIG = {
    "image": image,
    "secrets": SECRETS,
    "timeout": 1800,  # 30 min hard limit for entire conversation
    "retries": 0,     # Don't retry - let Vercel handle
}

# Web endpoint configuration (no retries allowed)
WEB_ENDPOINT_CONFIG = {
    "image": image,
    "secrets": SECRETS,
    "timeout": 60,  # Web endpoint just spawns or routes messages
}

# Remote path where .claude folder is mounted in the container
CLAUDE_FOLDER_PATH = "/app"
