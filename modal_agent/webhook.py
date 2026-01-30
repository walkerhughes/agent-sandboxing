"""Webhook helpers for sending events to Vercel."""

import httpx
from typing import Any


async def send_webhook(url: str, payload: dict[str, Any]) -> None:
    """Send a webhook event to the Vercel endpoint."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            print(f"Webhook sent: {payload['type']} -> {response.status_code}")
        except Exception as e:
            print(f"Webhook failed: {payload['type']} -> {e}")
            raise


async def send_session_started(webhook_url: str, task_id: str, session_id: str) -> None:
    """Send session_started event."""
    await send_webhook(webhook_url, {
        "type": "session_started",
        "taskId": task_id,
        "sessionId": session_id
    })


async def send_status_update(webhook_url: str, task_id: str, message: str, tool: str | None = None) -> None:
    """Send status_update event."""
    payload = {
        "type": "status_update",
        "taskId": task_id,
        "message": message
    }
    if tool:
        payload["tool"] = tool
    await send_webhook(webhook_url, payload)


async def send_clarification_needed(
    webhook_url: str,
    task_id: str,
    session_id: str,
    question: str,
    context: str,
    options: list[str] | None = None
) -> None:
    """Send clarification_needed event."""
    await send_webhook(webhook_url, {
        "type": "clarification_needed",
        "taskId": task_id,
        "sessionId": session_id,
        "question": question,
        "context": context,
        "options": options or []
    })


async def send_completed(
    webhook_url: str,
    task_id: str,
    session_id: str,
    summary: str,
    actions_taken: list[str] | None = None
) -> None:
    """Send completed event."""
    await send_webhook(webhook_url, {
        "type": "completed",
        "taskId": task_id,
        "sessionId": session_id,
        "result": {
            "summary": summary,
            "actions_taken": actions_taken or []
        }
    })


async def send_failed(webhook_url: str, task_id: str, error: str) -> None:
    """Send failed event."""
    await send_webhook(webhook_url, {
        "type": "failed",
        "taskId": task_id,
        "error": error
    })
