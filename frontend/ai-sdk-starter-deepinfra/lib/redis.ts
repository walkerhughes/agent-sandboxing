/**
 * Upstash Redis client.
 *
 * Used for caching and optional pub/sub notifications.
 * Note: For real-time SSE updates, we use database polling
 * since Upstash REST doesn't support blocking subscriptions.
 */

import { Redis } from "@upstash/redis";

// Initialize Redis client from environment variables
// Requires: UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN
const redis = process.env.UPSTASH_REDIS_REST_URL
  ? Redis.fromEnv()
  : null;

/**
 * Publish a message to a channel.
 * Falls back to console.log if Redis is not configured.
 */
export async function publish(channel: string, message: string): Promise<number> {
  if (redis) {
    return await redis.publish(channel, message);
  }
  console.log(`[Redis] Publishing to ${channel}:`, message.slice(0, 100) + "...");
  return 1;
}

/**
 * Get a value from Redis.
 */
export async function get<T>(key: string): Promise<T | null> {
  if (redis) {
    return await redis.get<T>(key);
  }
  return null;
}

/**
 * Set a value in Redis with optional TTL.
 */
export async function set(key: string, value: unknown, ttlSeconds?: number): Promise<void> {
  if (redis) {
    if (ttlSeconds) {
      await redis.set(key, value, { ex: ttlSeconds });
    } else {
      await redis.set(key, value);
    }
  }
}

// Export for backwards compatibility
export { redis };
