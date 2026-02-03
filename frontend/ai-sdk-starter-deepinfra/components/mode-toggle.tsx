"use client";

import { type AppMode } from "./chat";
import { MessageSquare, Zap } from "lucide-react";

interface ModeToggleProps {
  mode: AppMode;
  onModeChange: (mode: AppMode) => void;
  disabled?: boolean;
}

export function ModeToggle({ mode, onModeChange, disabled }: ModeToggleProps) {
  return (
    <div className="flex items-center justify-center gap-2 py-4">
      <button
        type="button"
        onClick={() => onModeChange("chat")}
        disabled={disabled}
        className={`
          flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
          ${
            mode === "chat"
              ? "bg-black text-white dark:bg-white dark:text-black"
              : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
          }
          ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        `}
      >
        <MessageSquare className="h-4 w-4" />
        Chat
      </button>

      <button
        type="button"
        onClick={() => onModeChange("action")}
        disabled={disabled}
        className={`
          flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
          ${
            mode === "action"
              ? "bg-blue-600 text-white"
              : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
          }
          ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        `}
      >
        <Zap className="h-4 w-4" />
        Action
      </button>
    </div>
  );
}
