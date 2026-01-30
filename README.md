# Human-in-the-Loop Agent System

A bifurcated agent architecture that separates conversational AI (lightweight, low-latency) from task execution (heavyweight, sandboxed), with the agent able to request clarification mid-task.

## Key Innovation

**Event-driven checkpoint/resume pattern** using Claude Agent SDK sessions, eliminating expensive idle compute while waiting for human input.

```
Container runs → AskUser tool called → Webhook sent → Container EXITS
                                                            ↓
User responds → New container spawns with resume=sessionId → Agent continues
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
        │               │    (Neon)     │◀──────────────┤
        │               └───────────────┘  session_id   │
        │                       │                       │
        │                       ▼                       │
        │               ┌───────────────┐               │
        └───────────────│     Redis     │◀──────────────┘
            SSE         │   (Upstash)   │   webhook/pub
                        └───────────────┘
```

## Sequence Diagram

```
Browser                 Vercel                    Modal
   │                       │                         │
   │ 1. POST /api/chat     │                         │
   │──────────────────────>│                         │
   │<──────────────────────│ streaming response      │
   │                       │                         │
   │ 2. Toggle Action Mode │                         │
   │ 3. POST /api/agent/start                        │
   │──────────────────────>│ create task (pending)   │
   │<──────────────────────│ { taskId }              │
   │                       │                         │
   │ 4. GET /api/agent/{taskId}/stream (SSE)         │
   │──────────────────────>│ subscribe Redis         │
   │                       │                         │
   │                       │ 5. spawn Modal ────────>│
   │                       │    (taskId, prompt,     │
   │                       │     webhookUrl)         │
   │                       │                         │
   │                       │<─────────────────────── │ 6. webhook:
   │                       │  session_started        │    session_started
   │                       │  { sessionId }          │
   │                       │                         │
   │<── SSE: status_update │<── Redis publish        │
   │                       │                         │
   │                       │                         │ 7. Agent works...
   │                       │                         │    calls AskUser
   │                       │                         │
   │                       │<─────────────────────── │ 8. webhook:
   │                       │  clarification_needed   │    clarification
   │                       │  { question, sessionId }│    → container EXITS
   │                       │                         │
   │<── SSE: clarification │<── Redis publish        │
   │    { question }       │                         │
   │                       │                         │
   │ 9. User types answer  │                         │
   │ 10. POST /api/agent/respond                     │
   │──────────────────────>│ { taskId, response }    │
   │                       │                         │
   │                       │ 11. spawn NEW Modal ───>│ (resume: sessionId)
   │                       │                         │
   │                       │                         │ 12. Agent resumes
   │                       │                         │     completes task
   │                       │                         │
   │                       │<─────────────────────── │ 13. webhook:
   │                       │  completed              │     completed
   │                       │  { result }             │     → container EXITS
   │                       │                         │
   │<── SSE: completed     │<── Redis publish        │
   │    { summary }        │                         │
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14+ (App Router), React 18+, Tailwind CSS |
| Chat SDK | Vercel AI SDK |
| Backend | Vercel Serverless Functions |
| Database | Neon (Postgres) + Prisma ORM |
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

### 2. Session Management

```python
# Only store session_id string in Postgres
# Claude SDK handles all conversation state internally

options = ClaudeAgentOptions(
    resume=session_id,  # None for new, session_id for resume
    allowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep",
                   "mcp__agent__AskUser"],
    permission_mode="acceptEdits"
)
```

### 3. AskUser Tool (Webhook + Exception Pattern)

```python
@tool("AskUser", "Ask the user for clarification", {...})
async def ask_user(args):
    raise AskUserException(
        question=args["question"],
        context=args["context"],
        options=args.get("options", [])
    )
```

### 4. Real-Time Updates

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
├── app/                      # Next.js App Router
│   ├── api/
│   │   ├── chat/             # Vercel AI SDK chat endpoint
│   │   └── agent/            # Agent task endpoints
│   │       ├── start/
│   │       ├── respond/
│   │       ├── webhook/
│   │       └── [taskId]/stream/
│   └── page.tsx              # Chat interface with mode toggle
├── components/               # React components
├── lib/
│   ├── db.ts                 # Prisma client
│   └── redis.ts              # Upstash Redis client
├── modal_agent/              # Modal Python package
│   ├── app.py                # Modal app config
│   ├── executor.py           # Agent execution loop
│   └── tools.py              # AskUser tool definition
├── prisma/
│   └── schema.prisma         # Database schema
└── spec.md                   # Full product requirements
```

## Getting Started

See the [Project Roadmap (Issue #20)](https://github.com/walkerhughes/agent-sandboxing/issues/20) for implementation phases and dependencies.

### Prerequisites

- Node.js 18+
- Python 3.11+
- Modal account (`modal token new`)
- Neon database
- Upstash Redis
- Anthropic API key

### Environment Variables

```bash
DATABASE_URL=
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
ANTHROPIC_API_KEY=
WEBHOOK_SECRET=
```

## Development Workflow

This repo uses **git worktrees** for parallel development. See `CLAUDE.md` for the full workflow.

```bash
# Create worktree for an issue
git worktree add ../agent-sandbox-issue-1 -b feat/project-setup

# Work in the worktree
cd ../agent-sandbox-issue-1

# Commit with issue reference
git commit -m "feat(#1): add project scaffolding"
```

## License

MIT
