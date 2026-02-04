# Human-in-the-Loop Agent System

A bifurcated agent architecture that separates conversational AI (lightweight, low-latency) from task execution (heavyweight, sandboxed), with the agent able to request clarification mid-task.

## Key Innovation

**Event-driven checkpoint/resume pattern** using Claude Agent SDK sessions, eliminating expensive idle compute while waiting for human input.

```
Container runs → AskUser tool called → Webhook sent → Container EXITS
                                                            ↓
User responds → New container spawns with resume=sessionId → Agent continues
```

## Features

- **Unified Chat Interface**: Single chat with inline Action toggle—no mode switching
- **Inline Agent Status**: Tool usage, progress, and clarifications render directly in the message stream
- **Multi-Turn Context**: Session management preserves conversation history across tasks
- **Checkpoint/Resume**: Containers exit when waiting for input, eliminating idle compute costs
- **Real-Time Updates**: SSE streaming for live status updates

## UI Preview

```
┌────────────────────────────────────────────────────────────┐
│  User: Build a todo app with React                         │
│                                                            │
│  Assistant: [Inline Status]                                │
│    ● Agent is working...                                   │
│    └─ Using Bash: npm create vite                          │
│    └─ Using Write: creating App.tsx...                     │
│                                                            │
│  [or when awaiting input:]                                 │
│  Assistant: [Inline Clarification]                         │
│    ? Which styling approach do you prefer?                 │
│    [Tailwind] [CSS Modules] [Styled Components]            │
│    [________________] [Send]                               │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  [textarea input                                         ] │
│  [Model ▼] [⚡ Action]                          [Submit ●] │
└────────────────────────────────────────────────────────────┘
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Browser     │     │     Vercel      │     │      Modal      │
│   (React/Next)  │────▶│  (Serverless)   │────▶│   (Sandboxed)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        │                       ▼                       │
        │               ┌───────────────┐               │
        │               │   Postgres    │               │
        │               │  (Supabase)   │◀──────────────┤
        │               └───────────────┘  session_id   │
        │                       │                       │
        │                       ▼                       │
        │               ┌───────────────┐               │
        └───────────────│     Redis     │◀──────────────┘
            SSE         │   (Upstash)   │   webhook/pub
                        └───────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15 (App Router), React 18+, Tailwind CSS |
| Chat SDK | Vercel AI SDK |
| Backend | Vercel Serverless Functions |
| Database | Supabase (Postgres) + Prisma ORM |
| Pub/Sub | Upstash Redis |
| Agent Runtime | Modal (sandboxed containers) |
| Agent SDK | Claude Agent SDK (Python) |
| LLM | Claude Sonnet 4.5 |

## Key Design Decisions

### 1. Checkpoint/Resume Pattern

When the agent needs user input:
1. `AskUser` tool sends webhook with question
2. Raises `AskUserException` to exit cleanly
3. Container exits (no idle compute billing)
4. User responds via `/api/agent/respond`
5. NEW container spawns with `resume=session_id`
6. Claude SDK loads full conversation context automatically

### 2. Multi-Turn Session Management

```python
# Session ID stored at ChatSession level for cross-task resume
# Claude SDK handles all conversation state internally

options = ClaudeAgentOptions(
    resume=session_id,  # None for new, session_id for resume
    allowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep",
                   "mcp__agent__AskUser"],
    permission_mode="acceptEdits"
)
```

Each new task in a chat session:
1. Fetches recent conversation history from database
2. Builds contextual prompt with history
3. Passes previous `agentSessionId` for Claude SDK resume
4. Agent continues with full awareness of prior work

### 3. Real-Time Updates

```
Modal webhook → Vercel /api/agent/webhook → Redis PUBLISH
                                                   ↓
Browser ←─────── SSE ←─────── Vercel /api/agent/{taskId}/stream
```

## Task State Machine

```
PENDING → RUNNING → COMPLETED
              ↓         ↑
        AWAITING_INPUT ─┘
              ↓
           FAILED / CANCELLED
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Standard chat completion (streaming) |
| `/api/agent/start` | POST | Create task, spawn Modal container |
| `/api/agent/respond` | POST | Submit clarification, resume agent |
| `/api/agent/cancel` | POST | Cancel running/waiting task |
| `/api/agent/[taskId]/stream` | GET | SSE for real-time updates |
| `/api/agent/webhook` | POST | Receive events from Modal |

## Project Structure

```
agent-sandboxing/
├── frontend/ai-sdk-starter-deepinfra/   # Next.js frontend
│   ├── app/
│   │   ├── api/
│   │   │   ├── chat/                    # Vercel AI SDK chat
│   │   │   └── agent/                   # Agent task endpoints
│   │   │       ├── start/
│   │   │       ├── respond/
│   │   │       ├── webhook/
│   │   │       └── [taskId]/stream/
│   │   └── page.tsx
│   ├── components/
│   │   ├── chat.tsx                     # Main chat component
│   │   ├── inline-agent-status.tsx      # Inline status/clarification
│   │   ├── textarea.tsx                 # Input with Action toggle
│   │   └── ...
│   ├── lib/
│   │   ├── db.ts                        # Prisma client
│   │   ├── modal.ts                     # Modal API client
│   │   └── redis.ts                     # Upstash Redis client
│   └── prisma/
│       └── schema.prisma
├── modal_agent/                         # Modal Python package
│   ├── config.py                        # Modal app config
│   ├── executor.py                      # Agent execution loop
│   ├── tools.py                         # AskUser tool definition
│   └── webhook.py                       # Webhook helpers
└── tests/                               # Python tests
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- Modal account
- Supabase database
- Upstash Redis
- Anthropic API key

### 1. Clone and Install

```bash
git clone https://github.com/walkerhughes/agent-sandboxing.git
cd agent-sandboxing

# Frontend
cd frontend/ai-sdk-starter-deepinfra
npm install

# Python (Modal agent)
cd ../..
uv sync  # or pip install -e .
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:
```bash
# Database (Supabase)
DATABASE_URL=postgresql://...

# Redis (Upstash)
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Modal
MODAL_TOKEN_ID=ak-...
MODAL_TOKEN_SECRET=as-...

# Webhook security
WEBHOOK_SECRET=your-secret-here
```

### 3. Setup Database

```bash
cd frontend/ai-sdk-starter-deepinfra
npx prisma db push
```

### 4. Deploy Modal Agent

```bash
# Authenticate with Modal
modal token new

# Deploy the agent
modal deploy -m modal_agent.executor

# Note the endpoint URL and add to .env:
# MODAL_ENDPOINT_URL=https://your-workspace--human-in-the-loop-agent-spawn-agent.modal.run
```

### 5. Run Frontend

```bash
cd frontend/ai-sdk-starter-deepinfra
npm run dev
```

For local development with webhooks, use a tunnel:
```bash
# In another terminal
cloudflared tunnel --url http://localhost:3000
# Add the tunnel URL to .env as PUBLIC_URL
```

## Development

See [CLAUDE.md](./CLAUDE.md) for development guidelines and git worktree workflow.

## License

MIT
