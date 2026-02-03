/**
 * GET /api/agent/[taskId]/stream
 *
 * Server-Sent Events endpoint for real-time task updates.
 * Subscribes to Redis pub/sub for the task channel.
 */

import { NextRequest } from "next/server";

// TODO: Import redis
// import { redis } from "@/lib/redis";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;

  // Create a readable stream for SSE
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      // Send initial connection message
      controller.enqueue(
        encoder.encode(`data: ${JSON.stringify({ type: "connected", taskId })}\n\n`)
      );

      // TODO: Subscribe to Redis channel for real-time updates
      // const subscriber = redis.duplicate();
      // await subscriber.subscribe(`task:${taskId}`);
      //
      // subscriber.on("message", (channel, message) => {
      //   controller.enqueue(encoder.encode(`data: ${message}\n\n`));
      // });

      // For MVP wireframe, just send periodic heartbeats
      const heartbeat = setInterval(() => {
        try {
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify({ type: "heartbeat" })}\n\n`)
          );
        } catch {
          clearInterval(heartbeat);
        }
      }, 30000);

      // Clean up on close
      req.signal.addEventListener("abort", () => {
        clearInterval(heartbeat);
        // subscriber.unsubscribe();
        // subscriber.quit();
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
