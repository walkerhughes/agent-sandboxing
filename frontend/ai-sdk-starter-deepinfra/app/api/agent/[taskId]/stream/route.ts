/**
 * GET /api/agent/[taskId]/stream
 *
 * Server-Sent Events endpoint for real-time task updates.
 * Polls the database for task status changes (serverless-friendly).
 */

import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;
  const encoder = new TextEncoder();

  console.log(`[SSE] Starting stream for task ${taskId}`);

  const stream = new ReadableStream({
    start(controller) {
      let lastStatus = "";
      let lastUpdateCount = 0;
      let isAborted = false;
      let isClosed = false;
      let pollCount = 0;

      const safeClose = () => {
        if (!isClosed && !isAborted) {
          isClosed = true;
          try {
            controller.close();
          } catch {
            // Controller already closed, ignore
          }
        }
      };

      // Send initial connection message
      controller.enqueue(
        encoder.encode(`data: ${JSON.stringify({ type: "connected", taskId })}\n\n`)
      );

      // Poll database for updates
      const poll = async () => {
        if (isAborted) {
          console.log(`[SSE] Stream aborted for task ${taskId}`);
          return;
        }

        pollCount++;
        console.log(`[SSE] Poll #${pollCount} for task ${taskId}`);

        try {
          const task = await prisma.agentTask.findUnique({
            where: { id: taskId },
            select: {
              status: true,
              statusUpdates: true,
              pendingClarification: true,
              result: true,
              agentSessionId: true,
            },
          });

          if (!task) {
            console.log(`[SSE] Task ${taskId} not found`);
            controller.enqueue(
              encoder.encode(`data: ${JSON.stringify({ type: "error", error: "Task not found" })}\n\n`)
            );
            safeClose();
            return;
          }

          console.log(`[SSE] Task ${taskId} status: ${task.status}, lastStatus: ${lastStatus}`);

          // Send status change
          if (task.status !== lastStatus) {
            lastStatus = task.status;
            console.log(`[SSE] Status changed to ${task.status}`);

            // Send running status
            if (task.status === "running") {
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify({
                  type: "status_update",
                  taskId,
                  message: "Agent is working...",
                })}\n\n`)
              );
            } else if (task.status === "awaiting_input" && task.pendingClarification) {
              const clarification = task.pendingClarification as {
                question: string;
                context: string;
                options?: string[];
              };
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify({
                  type: "clarification_needed",
                  taskId,
                  sessionId: task.agentSessionId,
                  question: clarification.question,
                  context: clarification.context,
                  options: clarification.options || [],
                })}\n\n`)
              );
            } else if (task.status === "completed" && task.result) {
              console.log(`[SSE] Task ${taskId} completed, sending result`);
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify({
                  type: "completed",
                  taskId,
                  sessionId: task.agentSessionId,
                  result: task.result,
                })}\n\n`)
              );
              // Close stream after completed
              setTimeout(() => {
                console.log(`[SSE] Closing stream for completed task ${taskId}`);
                safeClose();
              }, 1000);
              return;
            } else if (task.status === "failed") {
              const result = task.result as { error?: string } | null;
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify({
                  type: "failed",
                  taskId,
                  error: result?.error || "Unknown error",
                })}\n\n`)
              );
              setTimeout(() => safeClose(), 1000);
              return;
            }
          }

          // Send new status updates from webhook
          const updates = task.statusUpdates as Array<{
            message: string;
            tool?: string;
            timestamp: string;
          }>;

          if (updates && updates.length > lastUpdateCount) {
            console.log(`[SSE] Found ${updates.length - lastUpdateCount} new status updates`);
            const newUpdates = updates.slice(lastUpdateCount);
            for (const update of newUpdates) {
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify({
                  type: "status_update",
                  taskId,
                  message: update.message,
                  tool: update.tool,
                })}\n\n`)
              );
            }
            lastUpdateCount = updates.length;
          }

          // Continue polling if not in terminal state
          if (!["completed", "failed", "cancelled"].includes(task.status)) {
            setTimeout(poll, 1000); // Poll every second
          } else {
            console.log(`[SSE] Task ${taskId} in terminal state, stopping poll`);
          }
        } catch (error) {
          console.error("[SSE] Poll error:", error);
          if (!isAborted) {
            setTimeout(poll, 2000); // Retry after 2s on error
          }
        }
      };

      // Start polling immediately
      poll();

      // Clean up on close
      req.signal.addEventListener("abort", () => {
        console.log(`[SSE] Client disconnected for task ${taskId}`);
        isAborted = true;
        isClosed = true;
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
