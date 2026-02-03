"use client";

import { defaultModel, type modelID } from "@/ai/providers";
import { useChat } from "@ai-sdk/react";
import { useState } from "react";
import { Textarea } from "./textarea";
import { ProjectOverview } from "./project-overview";
import { Messages } from "./messages";
import { Header } from "./header";
import { toast } from "sonner";
import { ModeToggle } from "./mode-toggle";
import { StatusPanel } from "./status-panel";

export type AppMode = "chat" | "action";

export default function Chat() {
  const [selectedModel, setSelectedModel] = useState<modelID>(defaultModel);
  const [mode, setMode] = useState<AppMode>("chat");
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);

  const { messages, input, setInput, handleSubmit, isLoading, stop } = useChat({
    body: { selectedModel },
    onError: (error) => {
      toast.error(
        error.message.length > 0
          ? error.message
          : "An error occured, please try again later.",
        { position: "top-center", richColors: true }
      );
    },
  });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (mode === "chat") {
      // Standard chat mode - use Vercel AI SDK
      handleSubmit(e);
    } else {
      // Action mode - start agent task
      try {
        const sessionId = crypto.randomUUID(); // TODO: Use actual session from DB
        const response = await fetch("/api/agent/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sessionId, task: input }),
        });
        const data = await response.json();
        if (data.taskId) {
          setActiveTaskId(data.taskId);
          setInput("");
          toast.success("Agent task started!", { position: "top-center" });
        }
      } catch {
        toast.error("Failed to start agent task", { position: "top-center" });
      }
    }
  };

  const handleClarificationResponse = async (response: string) => {
    if (!activeTaskId) return;

    try {
      await fetch("/api/agent/respond", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ taskId: activeTaskId, response }),
      });
      toast.success("Response sent!", { position: "top-center" });
    } catch {
      toast.error("Failed to send response", { position: "top-center" });
    }
  };

  // Derive status for backwards compatibility with Textarea component
  const status = isLoading ? "streaming" : "ready";

  return (
    <div className="flex flex-col justify-center w-full h-dvh stretch">
      <Header />

      {/* Mode Toggle */}
      <div className="mx-auto w-full max-w-xl px-4 sm:px-0">
        <ModeToggle mode={mode} onModeChange={setMode} disabled={isLoading || !!activeTaskId} />
      </div>

      {/* Status Panel (visible in action mode when task is active) */}
      {mode === "action" && activeTaskId && (
        <div className="mx-auto w-full max-w-xl px-4 sm:px-0">
          <StatusPanel
            taskId={activeTaskId}
            onClarificationResponse={handleClarificationResponse}
            onTaskComplete={() => setActiveTaskId(null)}
          />
        </div>
      )}

      {messages.length === 0 && !activeTaskId ? (
        <div className="mx-auto w-full max-w-xl">
          <ProjectOverview mode={mode} />
        </div>
      ) : (
        <Messages messages={messages} isLoading={isLoading} status={status} />
      )}

      <form
        onSubmit={onSubmit}
        className="px-4 pb-8 mx-auto w-full max-w-xl bg-white dark:bg-black sm:px-0"
      >
        <Textarea
          selectedModel={selectedModel}
          setSelectedModel={setSelectedModel}
          handleInputChange={(e) => setInput(e.currentTarget.value)}
          input={input}
          isLoading={isLoading}
          status={status}
          stop={stop}
          mode={mode}
        />
      </form>
    </div>
  );
}
