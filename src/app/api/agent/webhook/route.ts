import { db } from "@/lib/db";
import { publishTaskEvent } from "@/lib/redis";
import { NextResponse } from "next/server";
import { Prisma } from "@prisma/client";

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
      result: { summary: string; actions_taken: string[] };
    }
  | { type: "failed"; taskId: string; error: string };

export async function POST(req: Request) {
  try {
    const event = (await req.json()) as WebhookEvent;
    const { type, taskId } = event;

    console.log("Webhook received:", type, taskId);

    // Update database based on event type
    switch (type) {
      case "session_started": {
        await db.agentTask.update({
          where: { id: taskId },
          data: {
            agentSessionId: event.sessionId,
            status: "running",
          },
        });
        break;
      }

      case "status_update": {
        const task = await db.agentTask.findUnique({
          where: { id: taskId },
          select: { statusUpdates: true },
        });
        const existingUpdates = Array.isArray(task?.statusUpdates)
          ? task.statusUpdates
          : [];
        const newUpdate = {
          message: event.message,
          tool: event.tool,
          timestamp: new Date().toISOString(),
        };
        await db.agentTask.update({
          where: { id: taskId },
          data: {
            statusUpdates: [...existingUpdates, newUpdate] as Prisma.InputJsonValue[],
          },
        });
        break;
      }

      case "clarification_needed": {
        await db.agentTask.update({
          where: { id: taskId },
          data: {
            status: "awaiting_input",
            agentSessionId: event.sessionId,
            pendingClarification: {
              question: event.question,
              context: event.context,
              options: event.options,
            },
          },
        });
        break;
      }

      case "completed": {
        await db.agentTask.update({
          where: { id: taskId },
          data: {
            status: "completed",
            result: event.result,
            completedAt: new Date(),
          },
        });
        break;
      }

      case "failed": {
        await db.agentTask.update({
          where: { id: taskId },
          data: {
            status: "failed",
            result: { error: event.error },
          },
        });
        break;
      }
    }

    // Publish to Redis for SSE delivery
    await publishTaskEvent(taskId, {
      type: event.type,
      taskId,
      payload: event,
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("Webhook error:", error);
    return NextResponse.json(
      { error: "Webhook processing failed" },
      { status: 500 }
    );
  }
}
