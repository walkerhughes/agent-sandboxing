/**
 * POST /api/agent/respond
 *
 * Submit a clarification response to the running agent container.
 *
 * Single-container architecture:
 * Instead of spawning a NEW container with resume=sessionId,
 * we send the response to the EXISTING container via the Modal endpoint.
 * The container's AskUser tool is blocked on a modal.Queue — putting the
 * response on the queue unblocks it and the agent continues.
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
    const baseUrl = process.env.PUBLIC_URL || process.env.VERCEL_URL || "http://localhost:3000";
    const webhookUrl = `${baseUrl}/api/agent/webhook`;

    // Send response to the EXISTING container via the Modal endpoint.
    // The spawn endpoint detects resume_session_id and routes the message
    // to the container's queue instead of spawning a new container.
    await spawnModalAgent({
      taskId,
      prompt: response,
      webhookUrl,
      resumeSessionId: task.agentSessionId,
    });

    console.log(`[Agent Respond] Sent response to container for task ${taskId}`);

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[Agent Respond] Error:", error);
    return NextResponse.json(
      { error: "Failed to submit response" },
      { status: 500 }
    );
  }
}
