import type { Message as AIMessage } from "ai";
import { Message } from "./message";
import { useScrollToBottom } from "@/lib/hooks/use-scroll-to-bottom";
import type { TaskResult } from "./inline-agent-status";

// Extended message type with agent-specific fields
export interface ExtendedMessage extends AIMessage {
  isAgentPending?: boolean;
  agentTaskId?: string;
}

export interface MessagesProps {
  messages: ExtendedMessage[];
  isLoading: boolean;
  status: string;
  onClarificationResponse?: (response: string) => void;
  onAgentComplete?: (result: TaskResult) => void;
  onAgentFail?: (error: string) => void;
}

export const Messages = ({
  messages,
  isLoading,
  status,
  onClarificationResponse,
  onAgentComplete,
  onAgentFail,
}: MessagesProps) => {
  const [containerRef, endRef] = useScrollToBottom();
  return (
    <div
      className="overflow-y-auto flex-1 py-8 space-y-4 h-full"
      ref={containerRef}
    >
      <div className="pt-8 mx-auto max-w-xl">
        {messages.map((m, i) => (
          <Message
            key={m.id}
            isLatestMessage={i === messages.length - 1}
            isLoading={isLoading}
            message={m}
            status={status}
            onClarificationResponse={onClarificationResponse}
            onAgentComplete={onAgentComplete}
            onAgentFail={onAgentFail}
          />
        ))}
        <div className="h-1" ref={endRef} />
      </div>
    </div>
  );
};
