/**
 * POST /api/agent/respond
 *
 * Submit a clarification response and resume the agent.
 * This triggers the checkpoint/resume pattern:
 * 1. Update task status to "running"
 * 2. Spawn NEW Modal container with resume=sessionId
 */

import { NextResponse } from "next/server";
import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { spawnModalAgent } from "@/lib/modal";

export async function POST(req: Request) {
  try {
    const { taskId, response } = await req.json();

    if (!taskId || !response) {
      return NextResponse.json(
        { error: "Missing taskId or response" },
        { status: 400 }
      );
    }

    // Fetch task and validate it's awaiting input
    const task = await prisma.agentTask.findUnique({
      where: { id: taskId },
    });

    if (!task) {
      return NextResponse.json(
        { error: "Task not found" },
        { status: 404 }
      );
    }

    if (task.status !== "awaiting_input") {
      return NextResponse.json(
        { error: `Task is not awaiting input (status: ${task.status})` },
        { status: 400 }
      );
    }

    if (!task.agentSessionId) {
      return NextResponse.json(
        { error: "Task has no agent session to resume" },
        { status: 400 }
      );
    }

    // Update task status to running
    await prisma.agentTask.update({
      where: { id: taskId },
      data: {
        status: "running",
        pendingClarification: Prisma.DbNull,
      },
    });

    // Build webhook URL
    // Use PUBLIC_URL for tunneled local dev (ngrok/cloudflared), VERCEL_URL for prod
    const baseUrl = process.env.PUBLIC_URL || process.env.VERCEL_URL || "http://localhost:3000";
    const webhookUrl = `${baseUrl}/api/agent/webhook`;

    // Spawn NEW Modal container with resume session ID
    // The response becomes the new prompt, and the session ID allows
    // Claude SDK to load the full conversation context
    await spawnModalAgent({
      taskId,
      prompt: response,
      webhookUrl,
      resumeSessionId: task.agentSessionId,
    });

    console.log(`[Agent Respond] Resuming task ${taskId} with session ${task.agentSessionId}`);

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[Agent Respond] Error:", error);
    return NextResponse.json(
      { error: "Failed to submit response" },
      { status: 500 }
    );
  }
}
