import { getModel, type modelID } from "@/ai/providers";
import { streamText, type CoreMessage } from "ai";

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

export async function POST(req: Request) {
  const {
    messages,
    selectedModel,
  }: { messages: CoreMessage[]; selectedModel: modelID } = await req.json();

  const result = streamText({
    model: getModel(selectedModel),
    system: "You are a helpful assistant.",
    messages,
    maxSteps: 5,
  });

  return result.toDataStreamResponse();
}
