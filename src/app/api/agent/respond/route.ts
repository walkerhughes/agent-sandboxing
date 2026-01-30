import { db } from "@/lib/db";
import { NextResponse } from "next/server";
import { Prisma } from "@prisma/client";

export async function POST(req: Request) {
  try {
    const { taskId, response } = await req.json();

    if (!taskId || !response) {
      return NextResponse.json(
        { error: "Missing taskId or response" },
        { status: 400 }
      );
    }

    // Get task and verify status
    const task = await db.agentTask.findUnique({
      where: { id: taskId },
    });

    if (!task) {
      return NextResponse.json({ error: "Task not found" }, { status: 404 });
    }

    if (task.status !== "awaiting_input") {
      return NextResponse.json(
        { error: "Task is not awaiting input" },
        { status: 400 }
      );
    }

    if (!task.agentSessionId) {
      return NextResponse.json(
        { error: "No agent session ID found" },
        { status: 400 }
      );
    }

    // Update task status
    await db.agentTask.update({
      where: { id: taskId },
      data: {
        status: "running",
        pendingClarification: Prisma.DbNull,
        executionSegment: task.executionSegment + 1,
      },
    });

    // Spawn NEW Modal container with resume
    const webhookUrl = `${process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"}/api/agent/webhook`;

    try {
      const modalUrl = process.env.MODAL_AGENT_URL;
      if (modalUrl) {
        await fetch(modalUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task_id: taskId,
            prompt: response, // User's answer becomes the prompt
            webhook_url: webhookUrl,
            resume_session_id: task.agentSessionId, // THE KEY: resume parameter
            execution_segment: task.executionSegment + 1,
          }),
        });
      } else {
        console.log("MODAL_AGENT_URL not set - agent will not be resumed");
        console.log("Would resume Modal with:", {
          task_id: taskId,
          prompt: response,
          webhook_url: webhookUrl,
          resume_session_id: task.agentSessionId,
          execution_segment: task.executionSegment + 1,
        });
      }
    } catch (modalError) {
      console.error("Failed to resume Modal agent:", modalError);
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("Error responding to agent:", error);
    return NextResponse.json(
      { error: "Failed to respond to agent" },
      { status: 500 }
    );
  }
}
