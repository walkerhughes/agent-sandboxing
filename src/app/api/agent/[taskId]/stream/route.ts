import { db } from "@/lib/db";
import { redis } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET(
  req: Request,
  { params }: { params: { taskId: string } }
) {
  const { taskId } = params;

  // Verify task exists
  const task = await db.agentTask.findUnique({
    where: { id: taskId },
  });

  if (!task) {
    return new Response("Task not found", { status: 404 });
  }

  // Create SSE stream
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      // Send initial status
      const initialEvent = {
        type: "status_update",
        taskId,
        timestamp: new Date().toISOString(),
        payload: { status: task.status },
      };
      controller.enqueue(
        encoder.encode(`data: ${JSON.stringify(initialEvent)}\n\n`)
      );

      // If task already has a pending clarification, send it
      if (task.status === "awaiting_input" && task.pendingClarification) {
        const clarificationEvent = {
          type: "clarification_needed",
          taskId,
          timestamp: new Date().toISOString(),
          payload: task.pendingClarification,
        };
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify(clarificationEvent)}\n\n`)
        );
      }

      // If task is already completed, send result
      if (task.status === "completed" && task.result) {
        const completedEvent = {
          type: "completed",
          taskId,
          timestamp: new Date().toISOString(),
          payload: { result: task.result },
        };
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify(completedEvent)}\n\n`)
        );
        controller.close();
        return;
      }

      // If task failed, send error
      if (task.status === "failed") {
        const failedEvent = {
          type: "failed",
          taskId,
          timestamp: new Date().toISOString(),
          payload: { error: (task.result as { error?: string })?.error || "Unknown error" },
        };
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify(failedEvent)}\n\n`)
        );
        controller.close();
        return;
      }

      // Subscribe to Redis channel for real-time updates
      // Note: Upstash REST API doesn't support true pub/sub subscriptions
      // In production, use a different approach (polling or WebSocket)
      // For MVP, we'll poll the database periodically

      const pollInterval = setInterval(async () => {
        try {
          const updatedTask = await db.agentTask.findUnique({
            where: { id: taskId },
          });

          if (!updatedTask) {
            clearInterval(pollInterval);
            controller.close();
            return;
          }

          // Check for status changes
          if (updatedTask.status === "awaiting_input" && updatedTask.pendingClarification) {
            const event = {
              type: "clarification_needed",
              taskId,
              timestamp: new Date().toISOString(),
              payload: updatedTask.pendingClarification,
            };
            controller.enqueue(
              encoder.encode(`data: ${JSON.stringify(event)}\n\n`)
            );
          }

          if (updatedTask.status === "completed") {
            const event = {
              type: "completed",
              taskId,
              timestamp: new Date().toISOString(),
              payload: { result: updatedTask.result },
            };
            controller.enqueue(
              encoder.encode(`data: ${JSON.stringify(event)}\n\n`)
            );
            clearInterval(pollInterval);
            controller.close();
          }

          if (updatedTask.status === "failed") {
            const event = {
              type: "failed",
              taskId,
              timestamp: new Date().toISOString(),
              payload: { error: (updatedTask.result as { error?: string })?.error || "Unknown error" },
            };
            controller.enqueue(
              encoder.encode(`data: ${JSON.stringify(event)}\n\n`)
            );
            clearInterval(pollInterval);
            controller.close();
          }
        } catch (error) {
          console.error("Poll error:", error);
        }
      }, 1000); // Poll every second

      // Clean up on disconnect
      req.signal.addEventListener("abort", () => {
        clearInterval(pollInterval);
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
