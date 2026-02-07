/**
 * POST /api/agent/webhook
 *
 * Receive events from Modal agent containers.
 * Events update the database; the SSE endpoint polls the database for changes.
 *
 * Key feature: Stores agentSessionId at BOTH task and session level
 * for multi-turn conversation resume capability.
 */

import { NextResponse } from "next/server";
import crypto from "crypto";
import { prisma } from "@/lib/db";

// Webhook event types from Modal
type WebhookEvent =
  | { type: "session_started"; taskId: string; sessionId: string }
  | { type: "status_update"; taskId: string; message: string; tool?: string }
  | {
      type: "clarification_needed";
      taskId: string;
      sessionId: string;
      question: string;
      context: string;
      options?: string[];
    }
  | {
      type: "completed";
      taskId: string;
      sessionId: string;
      result: {
        summary: string;
        actions_taken: string[];
        files_created?: string[];
      };
    }
  | { type: "failed"; taskId: string; error: string };

export async function POST(req: Request) {
  try {
    // Verify webhook signature
    const signature = req.headers.get("x-webhook-signature");
    const body = await req.text();

    const expectedSignature = crypto
      .createHmac("sha256", process.env.WEBHOOK_SECRET || "")
      .update(body)
      .digest("hex");

    if (signature !== expectedSignature) {
      console.warn("[Webhook] Invalid signature");
      return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
    }

    const event: WebhookEvent = JSON.parse(body);
    console.log(`[Webhook] Received ${event.type} for task ${event.taskId}`);

    // Handle different event types
    switch (event.type) {
      case "session_started": {
        // Store the Claude SDK session ID for resume capability
        // Update BOTH the task AND the parent chat session
        const task = await prisma.agentTask.update({
          where: { id: event.taskId },
          data: {
            agentSessionId: event.sessionId,
            status: "running",
          },
          select: { sessionId: true },
        });

        // Also update the ChatSession's agentSessionId for cross-task resume
        if (task.sessionId) {
          await prisma.chatSession.update({
            where: { id: task.sessionId },
            data: { agentSessionId: event.sessionId },
          });
          console.log(`[Webhook] Updated ChatSession ${task.sessionId} with agentSessionId ${event.sessionId}`);
        }
        break;
      }

      case "status_update":
        // Append to status updates (SSE endpoint polls DB for changes)
        await prisma.agentTask.update({
          where: { id: event.taskId },
          data: {
            statusUpdates: {
              push: {
                message: event.message,
                tool: event.tool,
                timestamp: new Date().toISOString(),
              },
            },
          },
        });

        break;

      case "clarification_needed": {
        // Container is exiting - store session ID for resume
        const task = await prisma.agentTask.update({
          where: { id: event.taskId },
          data: {
            status: "awaiting_input",
            agentSessionId: event.sessionId,
            pendingClarification: {
              question: event.question,
              context: event.context,
              options: event.options || [],
            },
          },
          select: { sessionId: true },
        });

        // Also update ChatSession for cross-task resume
        if (task.sessionId) {
          await prisma.chatSession.update({
            where: { id: task.sessionId },
            data: { agentSessionId: event.sessionId },
          });
        }
        break;
      }

      case "completed": {
        const task = await prisma.agentTask.update({
          where: { id: event.taskId },
          data: {
            status: "completed",
            agentSessionId: event.sessionId,
            result: event.result,
            completedAt: new Date(),
          },
          select: { sessionId: true },
        });

        // Update ChatSession with latest session ID for future tasks
        if (task.sessionId) {
          await prisma.chatSession.update({
            where: { id: task.sessionId },
            data: { agentSessionId: event.sessionId },
          });
          console.log(`[Webhook] Task completed, ChatSession ${task.sessionId} agentSessionId updated`);
        }
        break;
      }

      case "failed":
        console.error(`[Webhook] Task ${event.taskId} failed with error: ${event.error}`);
        await prisma.agentTask.update({
          where: { id: event.taskId },
          data: {
            status: "failed",
            result: { error: event.error },
          },
        });

        break;
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[Webhook] Error:", error);
    return NextResponse.json(
      { error: "Failed to process webhook" },
      { status: 500 }
    );
  }
}
