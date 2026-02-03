"use client";

import { useEffect, useState } from "react";
import { CheckCircle, Clock, AlertCircle, MessageCircle, X } from "lucide-react";

interface StatusPanelProps {
  taskId: string;
  onClarificationResponse: (response: string) => void;
  onTaskComplete: () => void;
}

type TaskStatus = "pending" | "running" | "awaiting_input" | "completed" | "failed" | "cancelled";

interface StatusUpdate {
  type: string;
  message?: string;
  tool?: string;
  question?: string;
  context?: string;
  options?: string[];
  result?: {
    summary: string;
    actions_taken: string[];
  };
  error?: string;
}

export function StatusPanel({ taskId, onClarificationResponse, onTaskComplete }: StatusPanelProps) {
  const [status, setStatus] = useState<TaskStatus>("pending");
  const [updates, setUpdates] = useState<StatusUpdate[]>([]);
  const [clarification, setClarification] = useState<{
    question: string;
    context: string;
    options: string[];
  } | null>(null);
  const [clarificationInput, setClarificationInput] = useState("");

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
          setTimeout(onTaskComplete, 3000); // Auto-close after 3s
          break;

        case "failed":
          setStatus("failed");
          setUpdates((prev) => [...prev, data]);
          break;
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => eventSource.close();
  }, [taskId, onTaskComplete]);

  const handleSubmitClarification = () => {
    if (clarificationInput.trim()) {
      onClarificationResponse(clarificationInput);
      setClarification(null);
      setClarificationInput("");
      setStatus("running");
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case "pending":
      case "running":
        return <Clock className="h-5 w-5 text-blue-500 animate-pulse" />;
      case "awaiting_input":
        return <MessageCircle className="h-5 w-5 text-yellow-500" />;
      case "completed":
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case "failed":
      case "cancelled":
        return <AlertCircle className="h-5 w-5 text-red-500" />;
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
    <div className="bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 mb-4">
      {/* Status Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <span className="text-sm font-medium">{getStatusText()}</span>
        </div>
        <button
          onClick={onTaskComplete}
          className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Status Updates */}
      {updates.length > 0 && (
        <div className="space-y-2 mb-3 max-h-40 overflow-y-auto">
          {updates.slice(-5).map((update, i) => (
            <div key={i} className="text-xs text-zinc-500 dark:text-zinc-400">
              {update.tool && (
                <span className="inline-block bg-zinc-200 dark:bg-zinc-700 rounded px-1 mr-1">
                  {update.tool}
                </span>
              )}
              {update.message || update.result?.summary || update.error}
            </div>
          ))}
        </div>
      )}

      {/* Clarification Input */}
      {clarification && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3 mt-3">
          <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200 mb-1">
            {clarification.question}
          </p>
          <p className="text-xs text-yellow-600 dark:text-yellow-400 mb-3">
            {clarification.context}
          </p>

          {/* Quick Options */}
          {clarification.options.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {clarification.options.map((option, i) => (
                <button
                  key={i}
                  onClick={() => {
                    onClarificationResponse(option);
                    setClarification(null);
                    setStatus("running");
                  }}
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
  );
}
