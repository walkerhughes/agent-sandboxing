import type { Message as AIMessage } from "ai";
import { Message } from "./message";
import { useScrollToBottom } from "@/lib/hooks/use-scroll-to-bottom";

export const Messages = ({
  messages,
  isLoading,
  status,
}: {
  messages: AIMessage[];
  isLoading: boolean;
  status: string;
}) => {
  const [containerRef, endRef] = useScrollToBottom();
  return (
    <div
      className="overflow-y-auto flex-1 py-8 space-y-4 h-full"
      ref={containerRef}
    >
      <div className="pt-8 mx-auto max-w-xl">
        {messages.map((m, i) => (
          <Message
            key={i}
            isLatestMessage={i === messages.length - 1}
            isLoading={isLoading}
            message={m}
            status={status}
          />
        ))}
        <div className="h-1" ref={endRef} />
      </div>
    </div>
  );
};
