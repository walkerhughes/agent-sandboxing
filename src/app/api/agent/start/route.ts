import { db } from "@/lib/db";
import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const { sessionId, task } = await req.json();

    if (!sessionId || !task) {
      return NextResponse.json(
        { error: "Missing sessionId or task" },
        { status: 400 }
      );
    }

    // Ensure session exists (create if needed for MVP)
    let session = await db.chatSession.findUnique({
      where: { id: sessionId },
    });

    if (!session) {
      session = await db.chatSession.create({
        data: {
          id: sessionId,
          userId: "demo-user", // Placeholder for MVP
        },
      });
    }

    // Create task record
    const agentTask = await db.agentTask.create({
      data: {
        sessionId: session.id,
        taskPrompt: task,
        status: "pending",
      },
    });

    // Spawn Modal container
    // For MVP, we'll call a placeholder endpoint
    // In production, this would be a Modal web endpoint
    const webhookUrl = `${process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"}/api/agent/webhook`;

    // TODO: Replace with actual Modal spawn
    // For now, we'll simulate with a fetch to a local endpoint
    // that will be replaced with Modal's web endpoint
    try {
      const modalUrl = process.env.MODAL_AGENT_URL;
      if (modalUrl) {
        await fetch(modalUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task_id: agentTask.id,
            prompt: task,
            webhook_url: webhookUrl,
          }),
        });
      } else {
        console.log("MODAL_AGENT_URL not set - agent will not be spawned");
        console.log("Task created:", agentTask.id);
        console.log("Would spawn Modal with:", {
          task_id: agentTask.id,
          prompt: task,
          webhook_url: webhookUrl,
        });
      }
    } catch (modalError) {
      console.error("Failed to spawn Modal agent:", modalError);
      // Don't fail the request - the task is created, Modal might be down
    }

    return NextResponse.json({ taskId: agentTask.id });
  } catch (error) {
    console.error("Error starting agent:", error);
    return NextResponse.json(
      { error: "Failed to start agent" },
      { status: 500 }
    );
  }
}
