/**
 * POST /api/agent/cancel
 *
 * Cancel a running or waiting agent task.
 */

import { NextResponse } from "next/server";

// TODO: Import prisma client
// import { prisma } from "@/lib/db";

export async function POST(req: Request) {
  try {
    const { taskId } = await req.json();

    if (!taskId) {
      return NextResponse.json(
        { error: "Missing taskId" },
        { status: 400 }
      );
    }

    // TODO: Update task status to cancelled
    // const task = await prisma.agentTask.update({
    //   where: { id: taskId },
    //   data: { status: "cancelled" },
    // });

    console.log(`[Agent Cancel] Cancelled task ${taskId}`);

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[Agent Cancel] Error:", error);
    return NextResponse.json(
      { error: "Failed to cancel task" },
      { status: 500 }
    );
  }
}
