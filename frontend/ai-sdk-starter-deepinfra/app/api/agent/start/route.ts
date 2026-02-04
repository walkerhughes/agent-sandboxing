/**
 * POST /api/agent/start
 *
 * Create a new agent task and spawn a Modal container.
 * This is the entry point for "Action Mode".
 *
 * Key features:
 * - Associates tasks with a ChatSession for conversation continuity
 * - Fetches recent task history to inject context into the prompt
 * - Passes the session's agentSessionId for Claude SDK resume capability
 */

import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { spawnModalAgent } from "@/lib/modal";

// Number of recent tasks to include in context
const MAX_HISTORY_TASKS = 10;

interface TaskHistoryItem {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

/**
 * Build a contextual prompt that includes recent conversation history.
 * This allows the agent to understand what stage of a multi-turn task it's in.
 */
function buildContextualPrompt(
  currentTask: string,
  history: TaskHistoryItem[]
): string {
  if (history.length === 0) {
    return currentTask;
  }

  const historyText = history
    .map((item) => {
      const role = item.role === "user" ? "User" : "Assistant";
      return `${role}: ${item.content}`;
    })
    .join("\n\n");

  return `## Conversation History
The following is the recent conversation history. Use this context to understand what has been discussed and what stage of any ongoing task you're in.

${historyText}

## Current Request
${currentTask}`;
}

export async function POST(req: Request) {
  try {
    const { task, chatSessionId } = await req.json();

    if (!task) {
      return NextResponse.json(
        { error: "Missing task" },
        { status: 400 }
      );
    }

    // Get or create chat session
    let session;
    if (chatSessionId) {
      // Try to find existing session
      session = await prisma.chatSession.findUnique({
        where: { id: chatSessionId },
      });
    }

    if (!session) {
      // Create new session (using a placeholder userId for now)
      session = await prisma.chatSession.create({
        data: {
          userId: "anonymous", // TODO: Replace with actual user ID when auth is implemented
        },
      });
    }

    // Fetch recent completed tasks for this session to build context
    const recentTasks = await prisma.agentTask.findMany({
      where: {
        sessionId: session.id,
        status: { in: ["completed", "failed"] },
      },
      orderBy: { createdAt: "asc" }, // Chronological order
      take: MAX_HISTORY_TASKS,
      select: {
        taskPrompt: true,
        result: true,
        status: true,
        createdAt: true,
      },
    });

    // Build conversation history from recent tasks
    const history: TaskHistoryItem[] = [];
    for (const t of recentTasks) {
      // Add user's request
      history.push({
        role: "user",
        content: t.taskPrompt,
        timestamp: t.createdAt,
      });

      // Add assistant's response (if completed successfully)
      if (t.status === "completed" && t.result) {
        const result = t.result as { summary?: string; error?: string };
        history.push({
          role: "assistant",
          content: result.summary || "Task completed.",
          timestamp: t.createdAt,
        });
      } else if (t.status === "failed" && t.result) {
        const result = t.result as { error?: string };
        history.push({
          role: "assistant",
          content: `Task failed: ${result.error || "Unknown error"}`,
          timestamp: t.createdAt,
        });
      }
    }

    // Build the contextual prompt with history
    const contextualPrompt = buildContextualPrompt(task, history);

    // Create task record linked to the session
    const agentTask = await prisma.agentTask.create({
      data: {
        taskPrompt: task,
        status: "pending",
        sessionId: session.id,
      },
    });

    const taskId = agentTask.id;

    // Build webhook URL for Modal to call back
    const baseUrl = process.env.PUBLIC_URL || process.env.VERCEL_URL || "http://localhost:3000";
    const webhookUrl = `${baseUrl}/api/agent/webhook`;

    // Spawn Modal container with session context
    // If the session has an agentSessionId, we can resume the Claude SDK session
    await spawnModalAgent({
      taskId,
      prompt: contextualPrompt,
      webhookUrl,
      resumeSessionId: session.agentSessionId || undefined,
    });

    // Update task status to running
    await prisma.agentTask.update({
      where: { id: taskId },
      data: { status: "running" },
    });

    console.log(`[Agent Start] Created task ${taskId} for session ${session.id}`);
    if (session.agentSessionId) {
      console.log(`[Agent Start] Resuming Claude session: ${session.agentSessionId}`);
    }
    if (history.length > 0) {
      console.log(`[Agent Start] Included ${history.length} history items in context`);
    }

    return NextResponse.json({
      taskId,
      chatSessionId: session.id,
    });
  } catch (error) {
    console.error("[Agent Start] Error:", error);
    return NextResponse.json(
      { error: "Failed to start agent task" },
      { status: 500 }
    );
  }
}
