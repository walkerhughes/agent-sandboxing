/**
 * Upstash Redis client for pub/sub.
 *
 * TODO: Initialize with actual Redis client once Upstash is configured
 */

// import { Redis } from "@upstash/redis";

// export const redis = Redis.fromEnv();

// Stub for wireframe MVP
export const redis = {
  publish: async (channel: string, message: string) => {
    console.log(`[Redis Stub] Publishing to ${channel}:`, message);
    return 1;
  },
  subscribe: async (channel: string) => {
    console.log(`[Redis Stub] Subscribed to ${channel}`);
    return () => {
      console.log(`[Redis Stub] Unsubscribed from ${channel}`);
    };
  },
};
