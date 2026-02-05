/**
 * Modal API client for agent containers.
 *
 * Single-container architecture:
 * - For NEW conversations: calls the Modal endpoint which spawns a new container.
 * - For RESPONSES: calls the same endpoint, which puts the response on a
 *   modal.Queue that the existing container is blocking on.
 *
 * The Modal endpoint distinguishes between the two cases by the presence
 * of resume_session_id in the request body.
 */

const MODAL_ENDPOINT_URL = process.env.MODAL_ENDPOINT_URL;

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface SpawnAgentOptions {
  taskId: string;
  prompt: string;
  webhookUrl: string;
  resumeSessionId?: string;
  chatContext?: ChatMessage[];
}

interface SpawnAgentResponse {
  status: "accepted";
  task_id: string;
  action: "container_spawned" | "response_queued";
}

/**
 * Spawn a Modal container or send a response to an existing one.
 *
 * When resumeSessionId is NOT set:
 *   - Creates a modal.Queue for the conversation
 *   - Spawns a new container that runs for the full conversation
 *
 * When resumeSessionId IS set:
 *   - Puts the prompt (user's response) on the existing container's Queue
 *   - The container's AskUser tool unblocks and returns the response to the agent
 */
export async function spawnModalAgent(options: SpawnAgentOptions): Promise<SpawnAgentResponse> {
  const { taskId, prompt, webhookUrl, resumeSessionId, chatContext } = options;

  if (!MODAL_ENDPOINT_URL) {
    throw new Error(
      "MODAL_ENDPOINT_URL not configured. Deploy Modal app and set the endpoint URL."
    );
  }

  const action = resumeSessionId ? "routing response to queue" : "spawning container";
  console.log(`[Modal] ${action}:`, {
    taskId,
    prompt: prompt.slice(0, 100) + (prompt.length > 100 ? "..." : ""),
    webhookUrl,
    resumeSessionId: resumeSessionId || "new session",
    chatContextLength: chatContext?.length || 0,
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
      chat_context: chatContext,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Modal request failed (${response.status}): ${error}`);
  }

  const result = await response.json() as SpawnAgentResponse;
  console.log("[Modal] Request accepted:", result);

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
}
