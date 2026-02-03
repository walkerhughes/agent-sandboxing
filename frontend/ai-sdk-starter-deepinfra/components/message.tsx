"use client";

import type { Message as AIMessage } from "ai";
import { AnimatePresence, motion } from "motion/react";
import { memo } from "react";
import { Streamdown } from "streamdown";
import { cn } from "@/lib/utils";
import { SparklesIcon } from "lucide-react";

const PurePreviewMessage = ({
  message,
  isLatestMessage,
  status,
}: {
  message: AIMessage;
  isLoading: boolean;
  status: string;
  isLatestMessage: boolean;
}) => {
  return (
    <AnimatePresence key={message.id}>
      <motion.div
        className="px-4 mx-auto w-full group/message"
        initial={{ y: 5, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        key={`message-${message.id}`}
        data-role={message.role}
      >
        <div
          className={cn(
            "flex gap-4 w-full group-data-[role=user]/message:ml-auto group-data-[role=user]/message:max-w-2xl",
            "group-data-[role=user]/message:w-fit"
          )}
        >
          {message.role === "assistant" && (
            <div className="flex justify-center items-center rounded-full ring-1 size-8 shrink-0 ring-border bg-background">
              <SparklesIcon size={14} />
            </div>
          )}

          <div className="flex flex-col space-y-4 w-full">
            <motion.div
              initial={{ y: 5, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="flex flex-row gap-2 items-start pb-4 w-full"
            >
              <div
                className={cn("flex flex-col gap-4", {
                  "bg-secondary text-secondary-foreground px-3 py-2 rounded-tl-xl rounded-tr-xl rounded-bl-xl":
                    message.role === "user",
                })}
              >
                <Streamdown>{message.content}</Streamdown>
              </div>
            </motion.div>

            {/* Loading indicator for latest streaming message */}
            {isLatestMessage && status === "streaming" && message.role === "assistant" && (
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <div className="animate-pulse">●</div>
                <span>Thinking...</span>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};

export const Message = memo(PurePreviewMessage, (prevProps, nextProps) => {
  if (prevProps.status !== nextProps.status) return false;
  if (prevProps.message.content !== nextProps.message.content) return false;
  return true;
});
