/**
 * Modal API client for spawning agent containers.
 *
 * Calls the Modal web endpoint to spawn new containers for each action request.
 * Each container has cached dependencies (Node.js, Claude Code CLI) for fast cold starts.
 */

const MODAL_ENDPOINT_URL = process.env.MODAL_ENDPOINT_URL;

interface SpawnAgentOptions {
  taskId: string;
  prompt: string;
  webhookUrl: string;
  resumeSessionId?: string;
}

interface SpawnAgentResponse {
  status: "accepted";
  task_id: string;
}

/**
 * Spawn a Modal container to execute an agent task.
 *
 * Makes HTTP POST to Modal web endpoint, which:
 * 1. Accepts the request immediately (202)
 * 2. Spawns a new container asynchronously
 * 3. Container sends webhooks back to Vercel as it progresses
 */
export async function spawnModalAgent(options: SpawnAgentOptions): Promise<SpawnAgentResponse> {
  const { taskId, prompt, webhookUrl, resumeSessionId } = options;

  if (!MODAL_ENDPOINT_URL) {
    throw new Error(
      "MODAL_ENDPOINT_URL not configured. Deploy Modal app and set the endpoint URL."
    );
  }

  console.log("[Modal] Spawning agent container:", {
    taskId,
    prompt: prompt.slice(0, 100) + (prompt.length > 100 ? "..." : ""),
    webhookUrl,
    resumeSessionId: resumeSessionId || "new session",
  });

  const response = await fetch(MODAL_ENDPOINT_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      task_id: taskId,
      prompt,
      webhook_url: webhookUrl,
      resume_session_id: resumeSessionId,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Modal spawn failed (${response.status}): ${error}`);
  }

  const result = await response.json() as SpawnAgentResponse;
  console.log("[Modal] Agent container spawned:", result);

  return result;
}

/**
 * Cancel a running Modal container.
 *
 * Note: Modal doesn't have a direct cancel API for spawned functions.
 * The agent should check for cancellation via webhook or database flag.
 */
export async function cancelModalAgent(taskId: string): Promise<void> {
  console.log("[Modal] Cancel requested for task:", taskId);

  // Modal spawned functions can't be directly cancelled.
  // Instead, we update the task status in the database to "cancelled"
  // and the agent checks this status periodically or via webhook.
  // The actual cancellation is handled by the webhook/database layer.
}
