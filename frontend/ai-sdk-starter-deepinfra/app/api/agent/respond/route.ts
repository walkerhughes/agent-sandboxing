/**
 * POST /api/agent/respond
 *
 * Submit a clarification response and resume the agent.
 * This triggers the checkpoint/resume pattern:
 * 1. Update task status to "running"
 * 2. Spawn NEW Modal container with resume=sessionId
 */

import { NextResponse } from "next/server";

// TODO: Import prisma client and Modal spawn function
// import { prisma } from "@/lib/db";
// import { spawnModalAgent } from "@/lib/modal";

export async function POST(req: Request) {
  try {
    const { taskId, response } = await req.json();

    if (!taskId || !response) {
      return NextResponse.json(
        { error: "Missing taskId or response" },
        { status: 400 }
      );
    }

    // TODO: Fetch task and validate it's awaiting input
    // const task = await prisma.agentTask.findUnique({
    //   where: { id: taskId },
    // });
    //
    // if (!task || task.status !== "awaiting_input") {
    //   return NextResponse.json(
    //     { error: "Task not found or not awaiting input" },
    //     { status: 400 }
    //   );
    // }

    // TODO: Update task status
    // await prisma.agentTask.update({
    //   where: { id: taskId },
    //   data: {
    //     status: "running",
    //     pendingClarification: null,
    //   },
    // });

    // TODO: Spawn NEW Modal container with resume
    // const webhookUrl = `${process.env.VERCEL_URL}/api/agent/webhook`;
    // await spawnModalAgent(taskId, response, webhookUrl, task.agentSessionId);

    console.log(`[Agent Respond] Resuming task ${taskId} with response`);

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[Agent Respond] Error:", error);
    return NextResponse.json(
      { error: "Failed to submit response" },
      { status: 500 }
    );
  }
}
