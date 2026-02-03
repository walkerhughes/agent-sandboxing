"""Webhook helpers for sending events to Vercel."""

import hashlib
import hmac
import os
from typing import Any, Literal
import httpx


WebhookEventType = Literal[
    "session_started",
    "status_update",
    "tool_use",
    "clarification_needed",
    "completed",
    "failed"
]


async def send_webhook(
    webhook_url: str,
    event_type: WebhookEventType,
    task_id: str,
    payload: dict[str, Any],
) -> bool:
    """
    Send a webhook event to Vercel.

    Args:
        webhook_url: The Vercel webhook endpoint URL
        event_type: Type of event being sent
        task_id: The agent task ID
        payload: Event-specific payload data

    Returns:
        True if webhook was sent successfully
    """
    webhook_secret = os.environ.get("WEBHOOK_SECRET", "")

    event = {
        "type": event_type,
        "taskId": task_id,
        **payload
    }

    # Create HMAC signature
    body = str(event).encode()
    signature = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            webhook_url,
            json=event,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
            },
            timeout=30.0,
        )
        return response.status_code == 200


async def send_session_started(
    webhook_url: str,
    task_id: str,
    session_id: str,
) -> bool:
    """Send session_started event when agent begins."""
    return await send_webhook(
        webhook_url,
        "session_started",
        task_id,
        {"sessionId": session_id}
    )


async def send_status_update(
    webhook_url: str,
    task_id: str,
    message: str,
    tool: str | None = None,
) -> bool:
    """Send status_update event during execution."""
    payload: dict[str, Any] = {"message": message}
    if tool:
        payload["tool"] = tool
    return await send_webhook(webhook_url, "status_update", task_id, payload)


async def send_clarification_needed(
    webhook_url: str,
    task_id: str,
    session_id: str,
    question: str,
    context: str,
    options: list[str] | None = None,
) -> bool:
    """Send clarification_needed event when AskUser is called."""
    return await send_webhook(
        webhook_url,
        "clarification_needed",
        task_id,
        {
            "sessionId": session_id,
            "question": question,
            "context": context,
            "options": options or [],
        }
    )


async def send_completed(
    webhook_url: str,
    task_id: str,
    session_id: str,
    result: dict[str, Any],
) -> bool:
    """Send completed event when task finishes successfully."""
    return await send_webhook(
        webhook_url,
        "completed",
        task_id,
        {"sessionId": session_id, "result": result}
    )


async def send_failed(
    webhook_url: str,
    task_id: str,
    error: str,
) -> bool:
    """Send failed event when task encounters an error."""
    return await send_webhook(webhook_url, "failed", task_id, {"error": error})
