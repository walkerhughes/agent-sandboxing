import { modelID } from "@/ai/providers";
import { Textarea as ShadcnTextarea } from "@/components/ui/textarea";
import { ArrowUp, Zap } from "lucide-react";
import { ModelPicker } from "./model-picker";

interface InputProps {
  input: string;
  handleInputChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  isLoading: boolean;
  status: string;
  stop: () => void;
  selectedModel: modelID;
  setSelectedModel: (model: modelID) => void;
  actionEnabled: boolean;
  onActionToggle: (enabled: boolean) => void;
  disableToggle?: boolean;
}

export const Textarea = ({
  input,
  handleInputChange,
  isLoading,
  status,
  stop,
  selectedModel,
  setSelectedModel,
  actionEnabled,
  onActionToggle,
  disableToggle = false,
}: InputProps) => {
  const placeholder = actionEnabled
    ? "Describe a task for the agent..."
    : "Say something...";

  return (
    <div className="relative w-full pt-4">
      <ShadcnTextarea
        className="resize-none bg-secondary w-full rounded-2xl pr-12 pt-4 pb-14"
        value={input}
        autoFocus
        placeholder={placeholder}
        // @ts-expect-error err
        onChange={handleInputChange}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (input.trim() && !isLoading) {
              // @ts-expect-error err
              const form = e.target.closest("form");
              if (form) form.requestSubmit();
            }
          }
        }}
      />

      {/* Bottom bar: Model picker + Action toggle on left, Submit on right */}
      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
        {/* Left: Model picker and Action toggle side by side */}
        <div className="flex items-center gap-2">
          <ModelPicker
            setSelectedModel={setSelectedModel}
            selectedModel={selectedModel}
          />
          <button
            type="button"
            onClick={() => onActionToggle(!actionEnabled)}
            disabled={disableToggle}
            className={`flex items-center gap-1 px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${
              actionEnabled
                ? "bg-blue-600 text-white"
                : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700"
            } ${disableToggle ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
          >
            <Zap className="h-3 w-3" />
            <span>Action</span>
          </button>
        </div>

        {/* Right: Submit/Stop button */}
        {status === "streaming" || status === "submitted" ? (
          <button
            type="button"
            onClick={stop}
            className="cursor-pointer rounded-full p-2 bg-black hover:bg-zinc-800 disabled:bg-zinc-300 disabled:cursor-not-allowed transition-colors"
          >
            <div className="animate-spin h-4 w-4">
              <svg className="h-4 w-4 text-white" viewBox="0 0 24 24">
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
            </div>
          </button>
        ) : (
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className={`rounded-full p-2 transition-colors disabled:bg-zinc-300 disabled:dark:bg-zinc-700 dark:disabled:opacity-80 disabled:cursor-not-allowed ${
              actionEnabled
                ? "bg-blue-600 hover:bg-blue-700"
                : "bg-black hover:bg-zinc-800"
            }`}
          >
            {actionEnabled ? (
              <Zap className="h-4 w-4 text-white" />
            ) : (
              <ArrowUp className="h-4 w-4 text-white" />
            )}
          </button>
        )}
      </div>
    </div>
  );
};
