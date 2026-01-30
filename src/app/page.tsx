"use client";

import { useState, useRef, useEffect } from "react";
import { useChat } from "ai/react";

type Mode = "chat" | "action";
type TaskStatus = "idle" | "pending" | "running" | "awaiting_input" | "completed" | "failed";

interface Clarification {
  question: string;
  context: string;
  options?: string[];
}

export default function Home() {
  const [mode, setMode] = useState<Mode>("chat");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatus>("idle");
  const [clarification, setClarification] = useState<Clarification | null>(null);
  const [clarificationResponse, setClarificationResponse] = useState("");
  const [taskResult, setTaskResult] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Chat mode using Vercel AI SDK
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: "/api/chat",
  });

  // Action mode input
  const [actionInput, setActionInput] = useState("");

  // Connect to SSE when task is active
  useEffect(() => {
    if (taskId && (taskStatus === "pending" || taskStatus === "running" || taskStatus === "awaiting_input")) {
      const eventSource = new EventSource(`/api/agent/${taskId}/stream`);
      eventSourceRef.current = eventSource;

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("SSE event:", data);

        switch (data.type) {
          case "status_update":
            setTaskStatus("running");
            break;
          case "clarification_needed":
            setTaskStatus("awaiting_input");
            setClarification({
              question: data.payload.question,
              context: data.payload.context,
              options: data.payload.options,
            });
            break;
          case "completed":
            setTaskStatus("completed");
            setTaskResult(data.payload.result?.summary || "Task completed");
            eventSource.close();
            break;
          case "failed":
            setTaskStatus("failed");
            setTaskResult(data.payload.error || "Task failed");
            eventSource.close();
            break;
        }
      };

      eventSource.onerror = () => {
        console.error("SSE connection error");
        eventSource.close();
      };

      return () => {
        eventSource.close();
      };
    }
  }, [taskId, taskStatus]);

  // Start action task
  const handleStartTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actionInput.trim()) return;

    setTaskStatus("pending");
    setClarification(null);
    setTaskResult(null);

    try {
      const response = await fetch("/api/agent/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: "demo-session", // Placeholder for MVP
          task: actionInput,
        }),
      });

      const data = await response.json();
      if (data.taskId) {
        setTaskId(data.taskId);
        setActionInput("");
      }
    } catch (error) {
      console.error("Failed to start task:", error);
      setTaskStatus("failed");
    }
  };

  // Submit clarification response
  const handleClarificationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clarificationResponse.trim() || !taskId) return;

    setTaskStatus("running");
    setClarification(null);

    try {
      await fetch("/api/agent/respond", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          taskId,
          response: clarificationResponse,
        }),
      });
      setClarificationResponse("");
    } catch (error) {
      console.error("Failed to submit response:", error);
      setTaskStatus("failed");
    }
  };

  // Select clarification option
  const handleOptionSelect = async (option: string) => {
    if (!taskId) return;

    setTaskStatus("running");
    setClarification(null);

    try {
      await fetch("/api/agent/respond", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          taskId,
          response: option,
        }),
      });
    } catch (error) {
      console.error("Failed to submit response:", error);
      setTaskStatus("failed");
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center p-4 bg-gray-50">
      <div className="w-full max-w-2xl">
        <h1 className="text-2xl font-bold text-center mb-4">Agent Sandbox</h1>

        {/* Mode Toggle */}
        <div className="flex justify-center mb-4">
          <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1">
            <button
              onClick={() => setMode("chat")}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === "chat"
                  ? "bg-blue-500 text-white"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              Chat
            </button>
            <button
              onClick={() => setMode("action")}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === "action"
                  ? "bg-blue-500 text-white"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              Action
            </button>
          </div>
        </div>

        {/* Chat Mode */}
        {mode === "chat" && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="h-96 overflow-y-auto mb-4 space-y-4">
              {messages.length === 0 && (
                <p className="text-gray-400 text-center mt-8">
                  Start a conversation...
                </p>
              )}
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`p-3 rounded-lg ${
                    m.role === "user"
                      ? "bg-blue-100 ml-8"
                      : "bg-gray-100 mr-8"
                  }`}
                >
                  <p className="text-sm font-medium text-gray-500 mb-1">
                    {m.role === "user" ? "You" : "Assistant"}
                  </p>
                  <p className="text-gray-800 whitespace-pre-wrap">{m.content}</p>
                </div>
              ))}
            </div>
            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                value={input}
                onChange={handleInputChange}
                placeholder="Type a message..."
                className="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading}
                className="bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 disabled:opacity-50"
              >
                Send
              </button>
            </form>
          </div>
        )}

        {/* Action Mode */}
        {mode === "action" && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            {/* Status Display */}
            {taskStatus !== "idle" && (
              <div className="mb-4 p-3 rounded-lg bg-gray-50">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-medium">Status:</span>
                  <span
                    className={`px-2 py-1 rounded text-sm ${
                      taskStatus === "completed"
                        ? "bg-green-100 text-green-800"
                        : taskStatus === "failed"
                        ? "bg-red-100 text-red-800"
                        : taskStatus === "awaiting_input"
                        ? "bg-yellow-100 text-yellow-800"
                        : "bg-blue-100 text-blue-800"
                    }`}
                  >
                    {taskStatus}
                  </span>
                </div>
                {taskResult && (
                  <p className="text-gray-700 text-sm">{taskResult}</p>
                )}
              </div>
            )}

            {/* Clarification UI */}
            {clarification && (
              <div className="mb-4 p-4 rounded-lg border-2 border-yellow-400 bg-yellow-50">
                <p className="font-medium text-gray-800 mb-2">
                  {clarification.question}
                </p>
                <p className="text-sm text-gray-600 mb-4">{clarification.context}</p>

                {clarification.options && clarification.options.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-4">
                    {clarification.options.map((option) => (
                      <button
                        key={option}
                        onClick={() => handleOptionSelect(option)}
                        className="px-3 py-1 rounded border border-gray-300 bg-white hover:bg-gray-50 text-sm"
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                )}

                <form onSubmit={handleClarificationSubmit} className="flex gap-2">
                  <input
                    value={clarificationResponse}
                    onChange={(e) => setClarificationResponse(e.target.value)}
                    placeholder="Or type a custom response..."
                    className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500"
                  />
                  <button
                    type="submit"
                    className="bg-yellow-500 text-white px-3 py-2 rounded text-sm hover:bg-yellow-600"
                  >
                    Submit
                  </button>
                </form>
              </div>
            )}

            {/* Task Input */}
            {taskStatus === "idle" || taskStatus === "completed" || taskStatus === "failed" ? (
              <form onSubmit={handleStartTask} className="flex gap-2">
                <input
                  value={actionInput}
                  onChange={(e) => setActionInput(e.target.value)}
                  placeholder="Describe the task you want the agent to perform..."
                  className="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="submit"
                  className="bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600"
                >
                  Run
                </button>
              </form>
            ) : (
              <div className="flex items-center justify-center py-4 text-gray-500">
                {taskStatus === "awaiting_input" ? (
                  <span>Waiting for your response above...</span>
                ) : (
                  <>
                    <svg
                      className="animate-spin h-5 w-5 mr-2"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    <span>Agent is working...</span>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
