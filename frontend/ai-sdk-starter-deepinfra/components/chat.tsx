"use client";

import { defaultModel, type modelID } from "@/ai/providers";
import { useChat } from "@ai-sdk/react";
import { useState, useCallback, useMemo, useRef } from "react";
import { Textarea } from "./textarea";
import { ProjectOverview } from "./project-overview";
import { Messages, type ExtendedMessage } from "./messages";
import { Header } from "./header";
import { toast } from "sonner";
import type { TaskResult } from "./inline-agent-status";

export default function Chat() {
  const [selectedModel, setSelectedModel] = useState<modelID>(defaultModel);
  const [actionEnabled, setActionEnabled] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [pendingMessages, setPendingMessages] = useState<ExtendedMessage[]>([]);

  // Chat session ID for grouping agent tasks and enabling conversation resume
  // Using ref for immediate access in handlers without re-renders
  const chatSessionIdRef = useRef<string | null>(null);

  const { messages: chatMessages, input, setInput, handleSubmit, isLoading, stop } = useChat({
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

  // Unified message list combining chat messages and pending action messages
  const allMessages = useMemo(() => {
    const chatExtended: ExtendedMessage[] = chatMessages.map(m => ({
      ...m,
      isAgentPending: false,
      agentTaskId: undefined,
    }));
    return [...chatExtended, ...pendingMessages].sort(
      (a, b) => new Date(a.createdAt!).getTime() - new Date(b.createdAt!).getTime()
    );
  }, [chatMessages, pendingMessages]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Detect /plan-feature command - auto-route to Action Mode
    const isPlanFeatureCommand = input.trim().toLowerCase().startsWith("/plan-feature");
    const shouldUseAction = actionEnabled || isPlanFeatureCommand;

    // Strip /plan-feature prefix if present (Modal will add it back)
    const cleanedInput = isPlanFeatureCommand
      ? input.trim().replace(/^\/plan-feature\s*/i, "")
      : input;

    if (!shouldUseAction) {
      // Standard chat mode - use Vercel AI SDK
      handleSubmit(e);
    } else {
      // Action mode - start agent task
      const userMessage = cleanedInput || input; // Use cleaned input, fallback to original if empty
      const userMsgId = crypto.randomUUID();
      const pendingMsgId = crypto.randomUUID();

      try {
        // Add user message and pending assistant message immediately
        setPendingMessages((prev) => [
          ...prev,
          {
            id: userMsgId,
            role: "user",
            content: userMessage,
            createdAt: new Date(),
          },
          {
            id: pendingMsgId,
            role: "assistant",
            content: "",
            isAgentPending: true,
            createdAt: new Date(),
          },
        ]);

        setInput("");

        // Build chat context from current conversation to pass to Modal agent
        // This gives the agent context from Chat Mode when entering Action Mode
        const chatContext = chatMessages.map(m => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        }));

        // Start agent task with chat session ID and conversation context
        const response = await fetch("/api/agent/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task: userMessage,
            chatSessionId: chatSessionIdRef.current, // Pass existing session if we have one
            chatContext, // Pass Chat Mode conversation for context
          }),
        });
        const data = await response.json();

        if (data.taskId) {
          // Store the chat session ID for future tasks
          if (data.chatSessionId) {
            chatSessionIdRef.current = data.chatSessionId;
          }

          // Update pending message with taskId to start SSE connection
          setPendingMessages((prev) =>
            prev.map((m) =>
              m.id === pendingMsgId ? { ...m, agentTaskId: data.taskId } : m
            )
          );
          setActiveTaskId(data.taskId);
        } else {
          throw new Error(data.error || "No taskId returned");
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to start agent task";
        toast.error(message, { position: "top-center" });
        // Remove the pending messages on error
        setPendingMessages((prev) =>
          prev.filter((m) => m.id !== userMsgId && m.id !== pendingMsgId)
        );
      }
    }
  };

  const handleClarificationResponse = useCallback(async (response: string) => {
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
  }, [activeTaskId]);

  const handleAgentComplete = useCallback((result: TaskResult) => {
    // Transform pending message to final assistant message
    setPendingMessages((prev) =>
      prev.map((m) =>
        m.agentTaskId === activeTaskId
          ? {
              ...m,
              content: result.summary,
              isAgentPending: false,
              agentTaskId: undefined,
            }
          : m
      )
    );
    setActiveTaskId(null);
  }, [activeTaskId]);

  const handleAgentFail = useCallback((error: string) => {
    // Transform pending message to show error
    setPendingMessages((prev) =>
      prev.map((m) =>
        m.agentTaskId === activeTaskId
          ? {
              ...m,
              content: `Task failed: ${error}`,
              isAgentPending: false,
              agentTaskId: undefined,
            }
          : m
      )
    );
    setActiveTaskId(null);
    toast.error(error, { position: "top-center" });
  }, [activeTaskId]);

  // Derive status for backwards compatibility with Textarea component
  const status = isLoading || activeTaskId ? "streaming" : "ready";

  return (
    <div className="flex flex-col justify-center w-full h-dvh stretch">
      <Header />

      {allMessages.length === 0 ? (
        <div className="mx-auto w-full max-w-xl">
          <ProjectOverview />
        </div>
      ) : (
        <Messages
          messages={allMessages}
          isLoading={isLoading || !!activeTaskId}
          status={status}
          onClarificationResponse={handleClarificationResponse}
          onAgentComplete={handleAgentComplete}
          onAgentFail={handleAgentFail}
        />
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
          isLoading={isLoading || !!activeTaskId}
          status={status}
          stop={stop}
          actionEnabled={actionEnabled}
          onActionToggle={setActionEnabled}
          disableToggle={!!activeTaskId}
        />
      </form>
    </div>
  );
}
