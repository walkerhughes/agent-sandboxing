"use client";

import { useEffect, useState, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CheckCircle, Clock, AlertCircle, MessageCircle, SparklesIcon } from "lucide-react";

export interface TaskResult {
  summary: string;
  actions_taken?: string[];
}

export interface StatusUpdate {
  type: string;
  message?: string;
  tool?: string;
  question?: string;
  context?: string;
  options?: string[];
  result?: TaskResult;
  error?: string;
}

interface InlineAgentStatusProps {
  taskId: string;
  messageId: string;
  onClarificationResponse: (response: string) => void;
  onComplete: (result: TaskResult) => void;
  onFail: (error: string) => void;
}

type TaskStatus = "pending" | "running" | "awaiting_input" | "completed" | "failed" | "cancelled";

export function InlineAgentStatus({
  taskId,
  messageId,
  onClarificationResponse,
  onComplete,
  onFail,
}: InlineAgentStatusProps) {
  const [status, setStatus] = useState<TaskStatus>("pending");
  const [updates, setUpdates] = useState<StatusUpdate[]>([]);
  const [clarification, setClarification] = useState<{
    question: string;
    context: string;
    options: string[];
  } | null>(null);
  const [clarificationInput, setClarificationInput] = useState("");

  // Use refs to avoid stale closures in SSE callback
  const onCompleteRef = useRef(onComplete);
  const onFailRef = useRef(onFail);
  onCompleteRef.current = onComplete;
  onFailRef.current = onFail;

  useEffect(() => {
    // Connect to SSE stream for real-time updates
    const eventSource = new EventSource(`/api/agent/${taskId}/stream`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "connected":
          setStatus("running");
          break;

        case "status_update":
          setUpdates((prev) => [...prev, data]);
          break;

        case "clarification_needed":
          setStatus("awaiting_input");
          setClarification({
            question: data.question,
            context: data.context,
            options: data.options || [],
          });
          break;

        case "completed":
          setStatus("completed");
          setUpdates((prev) => [...prev, data]);
          // Notify parent after brief delay to show completion state
          setTimeout(() => {
            if (data.result) {
              onCompleteRef.current(data.result);
            } else {
              onCompleteRef.current({ summary: "Task completed successfully" });
            }
          }, 500);
          break;

        case "failed":
          setStatus("failed");
          setUpdates((prev) => [...prev, data]);
          onFailRef.current(data.error || "Task failed");
          break;
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => eventSource.close();
  }, [taskId]);

  const handleSubmitClarification = () => {
    if (clarificationInput.trim()) {
      onClarificationResponse(clarificationInput);
      setClarification(null);
      setClarificationInput("");
      setStatus("running");
    }
  };

  const handleOptionClick = (option: string) => {
    onClarificationResponse(option);
    setClarification(null);
    setStatus("running");
  };

  const getStatusIcon = () => {
    switch (status) {
      case "pending":
      case "running":
        return <Clock className="h-4 w-4 text-blue-500 animate-pulse" />;
      case "awaiting_input":
        return <MessageCircle className="h-4 w-4 text-yellow-500" />;
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
      case "cancelled":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case "pending":
        return "Starting agent...";
      case "running":
        return "Agent is working...";
      case "awaiting_input":
        return "Waiting for your input";
      case "completed":
        return "Task completed!";
      case "failed":
        return "Task failed";
      case "cancelled":
        return "Task cancelled";
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        className="px-4 mx-auto w-full group/message"
        initial={{ y: 5, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        key={`agent-status-${messageId}`}
        data-role="assistant"
      >
        <div className="flex gap-4 w-full">
          {/* Assistant icon */}
          <div className="flex justify-center items-center rounded-full ring-1 size-8 shrink-0 ring-border bg-background">
            <SparklesIcon size={14} />
          </div>

          <div className="flex flex-col space-y-3 w-full pb-4">
            {/* Status Header */}
            <div className="flex items-center gap-2">
              {getStatusIcon()}
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                {getStatusText()}
              </span>
            </div>

            {/* Status Updates (while running) */}
            {(status === "running" || status === "pending") && updates.length > 0 && (
              <div className="space-y-1 pl-2 border-l-2 border-zinc-200 dark:border-zinc-700">
                {updates.slice(-5).map((update, i) => (
                  <div key={i} className="text-xs text-zinc-500 dark:text-zinc-400 flex items-center gap-1">
                    {update.tool && (
                      <span className="inline-block bg-zinc-100 dark:bg-zinc-800 rounded px-1.5 py-0.5 font-mono">
                        {update.tool}
                      </span>
                    )}
                    <span>{update.message}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Completed Result */}
            {status === "completed" && (
              <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
                <p className="text-sm text-green-800 dark:text-green-200">
                  {updates.find((u) => u.type === "completed")?.result?.summary ||
                    "Task completed successfully"}
                </p>
              </div>
            )}

            {/* Failed Result */}
            {status === "failed" && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                <p className="text-sm text-red-800 dark:text-red-200">
                  {updates.find((u) => u.error)?.error || "Task failed"}
                </p>
              </div>
            )}

            {/* Clarification Input */}
            {clarification && (
              <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
                <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200 mb-1">
                  {clarification.question}
                </p>
                {clarification.context && (
                  <p className="text-xs text-yellow-600 dark:text-yellow-400 mb-3">
                    {clarification.context}
                  </p>
                )}

                {/* Quick Options */}
                {clarification.options.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {clarification.options.map((option, i) => (
                      <button
                        key={i}
                        onClick={() => handleOptionClick(option)}
                        className="px-3 py-1 text-xs bg-yellow-100 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-200 rounded-full hover:bg-yellow-200 dark:hover:bg-yellow-700 transition-colors"
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                )}

                {/* Free-form Input */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={clarificationInput}
                    onChange={(e) => setClarificationInput(e.target.value)}
                    placeholder="Type your response..."
                    className="flex-1 px-3 py-2 text-sm rounded-lg border border-yellow-300 dark:border-yellow-700 bg-white dark:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-yellow-500"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSubmitClarification();
                    }}
                  />
                  <button
                    onClick={handleSubmitClarification}
                    disabled={!clarificationInput.trim()}
                    className="px-4 py-2 text-sm font-medium bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Send
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
