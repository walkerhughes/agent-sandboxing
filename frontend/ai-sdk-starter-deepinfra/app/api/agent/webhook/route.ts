/**
 * POST /api/agent/webhook
 *
 * Receive events from Modal agent containers.
 * Events are published to Redis for real-time SSE delivery.
 */

import { NextResponse } from "next/server";
import crypto from "crypto";

// TODO: Import prisma client and redis
// import { prisma } from "@/lib/db";
// import { redis } from "@/lib/redis";

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
      case "session_started":
        // TODO: Update task with session ID
        // await prisma.agentTask.update({
        //   where: { id: event.taskId },
        //   data: {
        //     agentSessionId: event.sessionId,
        //     status: "running",
        //   },
        // });
        break;

      case "status_update":
        // TODO: Append to status updates and publish to Redis
        // await prisma.agentTask.update({
        //   where: { id: event.taskId },
        //   data: {
        //     statusUpdates: {
        //       push: {
        //         message: event.message,
        //         tool: event.tool,
        //         timestamp: new Date().toISOString(),
        //       },
        //     },
        //   },
        // });
        // await redis.publish(`task:${event.taskId}`, JSON.stringify(event));
        break;

      case "clarification_needed":
        // TODO: Update task to awaiting_input
        // await prisma.agentTask.update({
        //   where: { id: event.taskId },
        //   data: {
        //     status: "awaiting_input",
        //     agentSessionId: event.sessionId,
        //     pendingClarification: {
        //       question: event.question,
        //       context: event.context,
        //       options: event.options || [],
        //     },
        //   },
        // });
        // await redis.publish(`task:${event.taskId}`, JSON.stringify(event));
        break;

      case "completed":
        // TODO: Update task to completed
        // await prisma.agentTask.update({
        //   where: { id: event.taskId },
        //   data: {
        //     status: "completed",
        //     result: event.result,
        //     completedAt: new Date(),
        //   },
        // });
        // await redis.publish(`task:${event.taskId}`, JSON.stringify(event));
        break;

      case "failed":
        // TODO: Update task to failed
        // await prisma.agentTask.update({
        //   where: { id: event.taskId },
        //   data: {
        //     status: "failed",
        //     result: { error: event.error },
        //   },
        // });
        // await redis.publish(`task:${event.taskId}`, JSON.stringify(event));
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
