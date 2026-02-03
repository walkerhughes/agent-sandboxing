/**
 * POST /api/agent/start
 *
 * Create a new agent task and spawn a Modal container.
 * This is the entry point for "Action Mode".
 */

import { NextResponse } from "next/server";

// TODO: Import prisma client and Modal spawn function
// import { prisma } from "@/lib/db";
// import { spawnModalAgent } from "@/lib/modal";

export async function POST(req: Request) {
  try {
    const { sessionId, task } = await req.json();

    if (!sessionId || !task) {
      return NextResponse.json(
        { error: "Missing sessionId or task" },
        { status: 400 }
      );
    }

    // TODO: Create task record in database
    const taskId = crypto.randomUUID();

    // Stub: In production, this creates a Prisma record
    // const agentTask = await prisma.agentTask.create({
    //   data: {
    //     id: taskId,
    //     sessionId,
    //     taskPrompt: task,
    //     status: "pending",
    //   },
    // });

    // TODO: Spawn Modal container
    // const webhookUrl = `${process.env.VERCEL_URL}/api/agent/webhook`;
    // await spawnModalAgent(taskId, task, webhookUrl);

    console.log(`[Agent Start] Created task ${taskId} for session ${sessionId}`);

    return NextResponse.json({ taskId });
  } catch (error) {
    console.error("[Agent Start] Error:", error);
    return NextResponse.json(
      { error: "Failed to start agent task" },
      { status: 500 }
    );
  }
}
