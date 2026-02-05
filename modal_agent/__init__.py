# Modal Agent Executor
# Single container per conversation with modal.Queue communication

from .config import app

# Lazy imports: executor requires claude_agent_sdk which is only
# available inside Modal containers, not in the local test environment.


def __getattr__(name: str):
    if name == "execute_agent":
        from .executor import execute_agent
        return execute_agent
    if name == "spawn_agent":
        from .executor import spawn_agent
        return spawn_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["app", "execute_agent", "spawn_agent"]
