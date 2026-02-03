import NextLink from "next/link";
import { MessageSquare, Zap, Bot, GitBranch } from "lucide-react";
import { type AppMode } from "./chat";

interface ProjectOverviewProps {
  mode?: AppMode;
}

export const ProjectOverview = ({ mode = "chat" }: ProjectOverviewProps) => {
  if (mode === "action") {
    return (
      <div className="flex flex-col items-center justify-end px-4">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="h-8 w-8 text-blue-500" />
          <h1 className="text-3xl font-semibold">Action Mode</h1>
        </div>
        <p className="text-center text-zinc-600 dark:text-zinc-400 mb-6 max-w-md">
          Describe a task and the agent will work on it autonomously.
          It can read files, write code, run commands, and ask for clarification when needed.
        </p>
        <div className="grid grid-cols-2 gap-4 w-full max-w-md">
          <FeatureCard
            icon={<Bot className="h-5 w-5" />}
            title="Autonomous Agent"
            description="Powered by Claude with coding tools"
          />
          <FeatureCard
            icon={<GitBranch className="h-5 w-5" />}
            title="Human-in-the-Loop"
            description="Agent asks questions when uncertain"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-end px-4">
      <div className="flex items-center gap-2 mb-4">
        <MessageSquare className="h-8 w-8 text-zinc-600 dark:text-zinc-400" />
        <h1 className="text-3xl font-semibold">Chat Mode</h1>
      </div>
      <p className="text-center text-zinc-600 dark:text-zinc-400">
        Chat with{" "}
        <Link href="https://openai.com">OpenAI</Link> models via the{" "}
        <Link href="https://sdk.vercel.ai/docs">AI SDK</Link>.
        Switch to <span className="text-blue-500 font-medium">Action Mode</span> to run autonomous tasks.
      </p>
    </div>
  );
};

const Link = ({
  children,
  href,
}: {
  children: React.ReactNode;
  href: string;
}) => {
  return (
    <NextLink
      target="_blank"
      className="text-blue-500 hover:text-blue-600 transition-colors duration-75"
      href={href}
    >
      {children}
    </NextLink>
  );
};

const FeatureCard = ({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) => {
  return (
    <div className="bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2 text-blue-500">
        {icon}
        <span className="font-medium text-sm">{title}</span>
      </div>
      <p className="text-xs text-zinc-500 dark:text-zinc-400">{description}</p>
    </div>
  );
};
