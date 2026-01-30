import { anthropic } from "@ai-sdk/anthropic";
import { streamText } from "ai";

export const maxDuration = 30;

export async function POST(req: Request) {
  const { messages } = await req.json();

  const result = streamText({
    model: anthropic("claude-sonnet-4-5-20250514"),
    messages,
    system: "You are a helpful assistant. Be concise and friendly.",
  });

  return result.toDataStreamResponse();
}
