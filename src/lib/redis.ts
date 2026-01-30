import { Redis } from "@upstash/redis";

// Upstash Redis client for pub/sub
export const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

// Helper to publish task events
export async function publishTaskEvent(
  taskId: string,
  event: {
    type: string;
    taskId: string;
    payload: Record<string, unknown>;
  }
) {
  await redis.publish(
    `task:${taskId}`,
    JSON.stringify({
      ...event,
      timestamp: new Date().toISOString(),
    })
  );
}
