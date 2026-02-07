# Product Requirements Document: Human-in-the-Loop Agent System

**Version:** 1.0  
**Date:** January 29, 2026  
**Author:** Walker (AI/ML Engineer)  
**Status:** Draft

---

## 1. Executive Summary

This document specifies a bifurcated agent architecture that separates conversational AI (lightweight, low-latency) from task execution (heavyweight, sandboxed). The system enables users to seamlessly transition from chat to autonomous task execution, with the agent able to request clarification mid-task and surface real-time status updates.

**Key Innovation:** Event-driven checkpoint/resume pattern using Claude Agent SDK sessions, eliminating expensive idle compute while waiting for human input.

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER BROWSER                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         React Chat Interface                           │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────┐  │ │
│  │  │  Chat Mode   │  │ Action Mode  │  │     Status Panel            │  │ │
│  │  │   Toggle     │  │   Toggle     │  │  • Running/Waiting/Done     │  │ │
│  │  └──────────────┘  └──────────────┘  │  • Live status updates      │  │ │
│  │                                       │  • Clarification prompts    │  │ │
│  │  ┌─────────────────────────────────┐ └─────────────────────────────┘  │ │
│  │  │       Message Thread            │                                   │ │
│  │  │  • User messages                │                                   │ │
│  │  │  • Assistant responses          │                                   │ │
│  │  │  • Clarification Q&A            │                                   │ │
│  │  │  • Task completion summaries    │                                   │ │
│  │  └─────────────────────────────────┘                                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
          │                    │                         ▲
          │ HTTP POST          │ HTTP POST               │ SSE (Server-Sent Events)
          │ /api/chat          │ /api/agent/*            │ /api/agent/[taskId]/stream
          ▼                    ▼                         │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            VERCEL (Edge/Serverless)                          │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   /api/chat     │  │  /api/agent/*   │  │  /api/agent/[id]/stream    │  │
│  │                 │  │                 │  │                             │  │
│  │  Vercel AI SDK  │  │  • POST /start  │  │  SSE endpoint               │  │
│  │  streaming chat │  │  • POST /respond│  │  Polls Postgres for changes │  │
│  │                 │  │  • POST /cancel │  │  Pushes events to browser   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│           │                   │                         ▲                    │
│           │                   │                         │                    │
│           ▼                   ▼                         │                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Shared Infrastructure                          │ │
│  │  ┌──────────────────────────────────────────────────────────────┐   │ │
│  │  │                    Postgres (Supabase)                      │   │ │
│  │  │                                                            │   │ │
│  │  │  • Chat sessions          • Status updates (append-only)   │   │ │
│  │  │  • Agent tasks            • Task results                   │   │ │
│  │  │  • SDK session IDs        • SSE polls DB for changes       │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP Webhooks (Modal → Vercel)
                                    │ HTTP Spawn (Vercel → Modal)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MODAL (Sandboxed Compute)                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     Agent Executor Container                           │ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                   Claude Agent SDK                               │ │ │
│  │  │                                                                  │ │ │
│  │  │  • Session management (resume: sessionId)                        │ │ │
│  │  │  • Tool execution (Bash, Read, Write, Edit, AskUser)            │ │ │
│  │  │  • Streaming responses                                          │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                              │                                        │ │
│  │                              ▼                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                    Execution Loop                                │ │ │
│  │  │                                                                  │ │ │
│  │  │  1. Receive task (new or resumed)                               │ │ │
│  │  │  2. Run agent loop until:                                       │ │ │
│  │  │     • Task completes → webhook "completed" → exit               │ │ │
│  │  │     • AskUser tool called → webhook "clarification" → exit      │ │ │
│  │  │     • Error/timeout → webhook "failed" → exit                   │ │ │
│  │  │  3. Container exits (no idle waiting)                           │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                              │                                        │ │
│  │                              │ Webhooks                               │ │
│  │                              ▼                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │  Event Types:                                                    │ │ │
│  │  │  • session_started    {taskId, sessionId}                       │ │ │
│  │  │  • status_update      {taskId, message, timestamp}              │ │ │
│  │  │  • tool_use           {taskId, tool, input}                     │ │ │
│  │  │  • clarification      {taskId, sessionId, question, context}    │ │ │
│  │  │  • completed          {taskId, sessionId, result}               │ │ │
│  │  │  • failed             {taskId, error}                           │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Container Lifecycle:                                                        │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐                  │
│  │  Cold   │───▶│ Running │───▶│ Waiting │───▶│  Exit   │                  │
│  │  Start  │    │  Agent  │    │  NEVER  │    │  Always │                  │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘                  │
│                                     ✗              ✓                        │
│  (Containers NEVER wait for human input - they checkpoint and exit)         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HAPPY PATH: Task with Clarification                  │
└─────────────────────────────────────────────────────────────────────────────┘

 Browser                 Vercel                              Modal
    │                       │                                     │
    │  1. Toggle "Action"   │                                     │
    │  2. Submit task       │                                     │
    │ ─────────────────────▶│                                     │
    │                       │  3. Create task record (pending)    │
    │                       │  4. Spawn container ───────────────▶│
    │                       │                                     │
    │  5. Connect SSE       │                                     │
    │ ─────────────────────▶│  6. Start DB polling                │
    │                       │                                     │
    │                       │                  7. Agent starts    │
    │                       │                     Claude SDK      │
    │                       │                  8. session_started │
    │                       │◀────────────────────────────────────│
    │                       │  9. Update DB (sessionId)           │
    │                       │                                     │
    │                       │                  10. Agent works... │
    │                       │                  11. status_update  │
    │                       │◀────────────────────────────────────│
    │                       │  12. Update DB                      │
    │  13. SSE event        │                                     │
    │◀──────────────────────│  (DB poll detects change)           │
    │                       │                                     │
    │                       │                  14. AskUser tool   │
    │                       │                  15. clarification  │
    │                       │◀────────────────────────────────────│
    │                       │  16. Update DB (awaiting_input)     │
    │  17. SSE clarification│                  18. Container EXITS│
    │◀──────────────────────│                      (no idle $)    │
    │                       │                                     │
    │  [User sees question] │                                     │
    │  19. User responds    │                                     │
    │ ─────────────────────▶│  20. Update DB (running)            │
    │                       │  21. Spawn NEW container ──────────▶│
    │                       │      (resume: sessionId)            │
    │                       │                  22. SDK resumes    │
    │                       │                  23. Agent continues│
    │                       │                  24. completed      │
    │                       │◀────────────────────────────────────│
    │                       │  25. Update DB (completed)          │
    │  26. SSE completed    │                  27. Container exits│
    │◀──────────────────────│                                     │
    │  [User sees summary]  │                                     │
```

---

## 3. Functional Requirements

### 3.1 User Interface

| ID | Requirement | Priority |
|----|-------------|----------|
| UI-1 | Toggle between "Chat" and "Action" modes | P0 |
| UI-2 | Display real-time status updates while agent executes | P0 |
| UI-3 | Surface clarification questions inline in chat thread | P0 |
| UI-4 | Display task completion summary with actions taken | P0 |
| UI-5 | Show visual indicator when agent is running vs. waiting | P1 |
| UI-6 | Allow cancellation of in-progress tasks | P1 |
| UI-7 | Persist chat history across page refreshes | P2 |

### 3.2 Agent Execution

| ID | Requirement | Priority |
|----|-------------|----------|
| AE-1 | Execute tasks in isolated Modal sandbox | P0 |
| AE-2 | Support clarification requests via AskUser tool | P0 |
| AE-3 | Resume from checkpoint after user responds | P0 |
| AE-4 | Stream status updates during execution | P0 |
| AE-5 | Generate structured completion summary | P0 |
| AE-6 | Timeout handling (max 10 min per execution segment) | P1 |
| AE-7 | Graceful error recovery with user-friendly messages | P1 |

### 3.3 Session Management

| ID | Requirement | Priority |
|----|-------------|----------|
| SM-1 | Store Claude Agent SDK session ID in database | P0 |
| SM-2 | Resume sessions using SDK `resume` parameter | P0 |
| SM-3 | Clean up sessions after task completion/abandonment | P1 |
| SM-4 | Handle session expiration gracefully | P2 |

---

## 4. Technical Specifications

### 4.1 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Frontend | Next.js 14+ (App Router) | SSR, API routes, excellent DX |
| UI Framework | React 18+ | Component model, hooks for state |
| Styling | Tailwind CSS | Rapid iteration, consistent design |
| Chat SDK | Vercel AI SDK | Built-in streaming, useChat hook |
| Backend | Vercel Serverless Functions | Co-located with frontend, auto-scaling |
| Database | Neon (Postgres) | Serverless Postgres, Vercel integration |
| ORM | Prisma | Type-safe queries, migrations |
| Agent Runtime | Modal | Sandboxed containers, pay-per-second |
| Agent SDK | Claude Agent SDK (TypeScript) | Session management, tool execution |
| LLM | Claude Sonnet 4.5 | Balance of capability and speed |

### 4.2 Database Schema

```sql
-- Chat sessions (user's conversation thread)
CREATE TABLE chat_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat messages (regular chat, not agent tasks)
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent tasks (action mode executions)
CREATE TABLE agent_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
  
  -- Task state
  status TEXT NOT NULL DEFAULT 'pending' 
    CHECK (status IN ('pending', 'running', 'awaiting_input', 'completed', 'failed', 'cancelled')),
  
  -- Claude Agent SDK session (this is ALL we need for resume!)
  agent_session_id TEXT,
  
  -- Original task
  task_prompt TEXT NOT NULL,
  
  -- Clarification state
  pending_clarification JSONB,
  -- Schema: { question: string, context: string, options?: string[] }
  
  -- Status updates (append-only log)
  status_updates JSONB[] DEFAULT '{}',
  -- Schema: { message: string, timestamp: string, tool?: string }
  
  -- Final result
  result JSONB,
  -- Schema: { summary: string, actions_taken: string[], files_created?: string[] }
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- Index for active task lookup
CREATE INDEX idx_agent_tasks_session_status ON agent_tasks(session_id, status);
```

### 4.3 API Endpoints

#### 4.3.1 Chat Endpoints (Vercel AI SDK)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Standard chat completion (streaming) |

#### 4.3.2 Agent Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agent/start` | POST | Create task, spawn Modal container |
| `/api/agent/respond` | POST | Submit clarification response, resume agent |
| `/api/agent/cancel` | POST | Cancel running/waiting task |
| `/api/agent/[taskId]/stream` | GET | SSE endpoint for real-time updates |
| `/api/agent/webhook` | POST | Receive events from Modal (internal) |

#### 4.3.3 API Request/Response Schemas

**POST /api/agent/start**
```typescript
// Request
{
  sessionId: string;      // Chat session ID
  task: string;           // Task description from user
}

// Response
{
  taskId: string;         // New agent task ID
}
```

**POST /api/agent/respond**
```typescript
// Request
{
  taskId: string;
  response: string;       // User's answer to clarification
}

// Response
{
  ok: boolean;
}
```

**POST /api/agent/webhook** (Modal → Vercel)
```typescript
// Request (discriminated union)
type WebhookEvent = 
  | { type: 'session_started'; taskId: string; sessionId: string }
  | { type: 'status_update'; taskId: string; message: string; tool?: string }
  | { type: 'clarification_needed'; taskId: string; sessionId: string; question: string; context: string }
  | { type: 'completed'; taskId: string; sessionId: string; result: TaskResult }
  | { type: 'failed'; taskId: string; error: string }

// Response
{ ok: boolean }
```

### 4.4 Real-Time Updates

Real-time updates use database polling via the SSE endpoint. The webhook handler writes events to Postgres, and the SSE endpoint (`/api/agent/[taskId]/stream`) polls the database every second for changes.

### 4.5 Modal Agent Configuration

```python
# modal_agent/config.py
import modal

app = modal.App("agent-executor")

# Container image with dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "anthropic",
    "httpx",
)

# Function configuration
FUNCTION_CONFIG = {
    "image": image,
    "secrets": [modal.Secret.from_name("anthropic-api-key")],
    "timeout": 600,       # 10 min max per execution segment
    "retries": 0,         # Don't retry - let Vercel handle
    "memory": 512,        # MB
}
```

### 4.6 AskUser Tool Definition

```typescript
const ASK_USER_TOOL = {
  name: "AskUser",
  description: `Ask the user for clarification when you need more information to proceed.
Use this when:
- The task is ambiguous and could be interpreted multiple ways
- You need to confirm a destructive or irreversible action
- You need specific information the user hasn't provided
- You want to present options for the user to choose from

Do NOT use this for:
- Routine progress updates (use status messages instead)
- Rhetorical questions
- Asking permission for every small step`,
  
  input_schema: {
    type: "object",
    properties: {
      question: {
        type: "string",
        description: "The specific question to ask the user. Be concise and clear."
      },
      context: {
        type: "string",
        description: "Brief context explaining why you need this information and how it affects the task."
      },
      options: {
        type: "array",
        items: { type: "string" },
        description: "Optional list of suggested answers or choices."
      }
    },
    required: ["question", "context"]
  }
};
```

---

## 5. State Machine

```
                              ┌─────────────────┐
                              │                 │
                              │     PENDING     │
                              │                 │
                              └────────┬────────┘
                                       │
                          Modal container spawned
                                       │
                                       ▼
                              ┌─────────────────┐
                              │                 │
              ┌───────────────│     RUNNING     │───────────────┐
              │               │                 │               │
              │               └────────┬────────┘               │
              │                        │                        │
        AskUser tool              Task completes           Error/Timeout
           called                      │                        │
              │                        │                        │
              ▼                        ▼                        ▼
     ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
     │                 │      │                 │      │                 │
     │ AWAITING_INPUT  │      │    COMPLETED    │      │     FAILED      │
     │                 │      │                 │      │                 │
     └────────┬────────┘      └─────────────────┘      └─────────────────┘
              │                       ▲
              │                       │
        User responds                 │
              │                       │
              └───────────────────────┘
                    (back to RUNNING)


     ┌─────────────────┐
     │                 │
     │    CANCELLED    │  ◄── User cancels from any active state
     │                 │
     └─────────────────┘
```

---

## 6. Error Handling

### 6.1 Error Categories

| Category | Examples | Handling Strategy |
|----------|----------|-------------------|
| **Transient** | Network timeout, DB connection drop | Retry with backoff |
| **User Error** | Invalid task, malformed input | Surface to user, allow retry |
| **Agent Error** | Tool execution failure, Claude refusal | Log, surface summary, allow retry |
| **System Error** | Modal crash, DB unavailable | Alert, graceful degradation |

### 6.2 Timeout Strategy

| Timeout | Value | Action |
|---------|-------|--------|
| Modal execution segment | 10 min | Exit with checkpoint if possible |
| Clarification wait | 24 hours | Auto-cancel task, clean up |
| SSE connection | 30 min | Client reconnects, replays from DB |
| Webhook delivery | 30 sec | Modal retries 3x |

### 6.3 SSE Reconnection

```typescript
// Client-side reconnection with replay
const connectSSE = (taskId: string, lastEventId?: string) => {
  const url = new URL(`/api/agent/${taskId}/stream`, window.location.origin);
  if (lastEventId) {
    url.searchParams.set('lastEventId', lastEventId);
  }
  
  const eventSource = new EventSource(url);
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Process event...
  };
  
  eventSource.onerror = () => {
    eventSource.close();
    // Exponential backoff reconnection
    setTimeout(() => connectSSE(taskId, lastEventId), backoffMs);
  };
};
```

---

## 7. Security Considerations

### 7.1 Webhook Authentication

```typescript
// Vercel webhook handler
export async function POST(req: Request) {
  const signature = req.headers.get('x-webhook-signature');
  const body = await req.text();
  
  const expected = crypto
    .createHmac('sha256', process.env.WEBHOOK_SECRET!)
    .update(body)
    .digest('hex');
  
  if (signature !== expected) {
    return Response.json({ error: 'Invalid signature' }, { status: 401 });
  }
  
  // Process webhook...
}
```

### 7.2 Task Authorization

- Users can only access their own tasks (enforced via session ownership)
- SSE endpoint validates task ownership before streaming
- Cancel endpoint validates ownership before cancellation

### 7.3 Sandbox Isolation

- Modal containers run in isolated environments
- No network access except to Anthropic API and Vercel webhook
- Filesystem is ephemeral (wiped on container exit)
- Resource limits prevent runaway compute

---

## 8. Observability & OpenTelemetry

### 8.1 OTel Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OpenTelemetry Data Flow                               │
└─────────────────────────────────────────────────────────────────────────────┘

 Browser                 Vercel                  Modal                 Collector
    │                       │                      │                       │
    │  ┌─────────────┐      │  ┌─────────────┐     │  ┌─────────────┐      │
    │  │ Browser SDK │      │  │  @vercel/   │     │  │ opentel-    │      │
    │  │ (optional)  │      │  │  otel       │     │  │ emetry-sdk  │      │
    │  └──────┬──────┘      │  └──────┬──────┘     │  └──────┬──────┘      │
    │         │             │         │            │         │             │
    │         │ traces      │         │ traces     │         │ traces      │
    │         │ spans       │         │ spans      │         │ spans       │
    │         │             │         │ metrics    │         │ metrics     │
    │         │             │         │            │         │             │
    │         └─────────────┼─────────┴────────────┼─────────┴─────────────▶
    │                       │                      │                       │
    │                       │                      │              ┌────────┴────────┐
    │                       │                      │              │   OTel          │
    │                       │                      │              │   Collector     │
    │                       │                      │              │                 │
    │                       │                      │              │  • Receives     │
    │                       │                      │              │  • Processes    │
    │                       │                      │              │  • Exports      │
    │                       │                      │              └────────┬────────┘
    │                       │                      │                       │
    │                       │                      │              ┌────────┴────────┐
    │                       │                      │              │                 │
    │                       │                      │              ▼                 ▼
    │                       │                      │        ┌──────────┐    ┌──────────┐
    │                       │                      │        │Honeycomb │    │ Jaeger/  │
    │                       │                      │        │/Datadog  │    │ Tempo    │
    │                       │                      │        └──────────┘    └──────────┘
```

### 8.2 Trace Context Propagation

The key challenge: **traces must survive the checkpoint/resume boundary**. When a Modal container exits for clarification and a new one resumes, they must be part of the same trace.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Trace Spanning Checkpoint/Resume                          │
└─────────────────────────────────────────────────────────────────────────────┘

Trace: task_abc123
│
├─► Span: vercel.agent.start (100ms)
│   │
│   └─► Span: modal.agent.execute_segment_1 (45s)
│       │
│       ├─► Span: claude.completion (2s)
│       ├─► Span: tool.bash (500ms)
│       ├─► Span: claude.completion (1.5s)
│       └─► Span: tool.ask_user (10ms)  ◄── Container exits here
│           │
│           │  [====== 3 minutes pass (human thinking) ======]
│           │
│           └─► Event: clarification_sent
│
├─► Span: vercel.agent.respond (50ms)
│   │
│   └─► Span: modal.agent.execute_segment_2 (30s)  ◄── New container, SAME TRACE
│       │
│       ├─► Span: claude.completion (1s)
│       ├─► Span: tool.write (200ms)
│       └─► Span: claude.completion (500ms)
│           │
│           └─► Event: task_completed
│
└─► Span: vercel.webhook.completed (20ms)
```

### 8.3 Trace Context Schema

```typescript
// Trace context propagated through all system boundaries
interface OTelContext {
  // W3C Trace Context (standard)
  traceparent: string;   // e.g., "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
  tracestate?: string;   // Optional vendor-specific data
  
  // Custom attributes for agent-specific correlation
  'agent.task_id': string;
  'agent.session_id': string;        // Chat session
  'agent.sdk_session_id'?: string;   // Claude Agent SDK session
  'agent.execution_segment': number; // 1, 2, 3... (increments on resume)
}
```

### 8.4 Instrumentation by Layer

#### 8.4.1 Vercel (Next.js)

```typescript
// instrumentation.ts (Next.js 13+ instrumentation hook)
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

export function register() {
  const sdk = new NodeSDK({
    resource: new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: 'agent-frontend',
      [SemanticResourceAttributes.SERVICE_VERSION]: process.env.VERCEL_GIT_COMMIT_SHA,
      [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.VERCEL_ENV,
    }),
    traceExporter: new OTLPTraceExporter({
      url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT + '/v1/traces',
      headers: { 'x-honeycomb-team': process.env.HONEYCOMB_API_KEY },
    }),
    metricExporter: new OTLPMetricExporter({
      url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT + '/v1/metrics',
    }),
  });
  
  sdk.start();
}
```

```typescript
// lib/tracing.ts - Helper for manual instrumentation
import { trace, context, SpanStatusCode, Span } from '@opentelemetry/api';

const tracer = trace.getTracer('agent-frontend');

export function startTaskSpan(taskId: string, sessionId: string): Span {
  return tracer.startSpan('agent.task', {
    attributes: {
      'agent.task_id': taskId,
      'agent.session_id': sessionId,
    },
  });
}

export function extractTraceContext(): string {
  // Extract W3C traceparent for propagation to Modal
  const carrier: Record<string, string> = {};
  propagation.inject(context.active(), carrier);
  return carrier['traceparent'] || '';
}

export function injectTraceContext(traceparent: string): void {
  // Restore context from traceparent (in webhook handler)
  const carrier = { traceparent };
  const ctx = propagation.extract(context.active(), carrier);
  context.with(ctx, () => { /* ... */ });
}
```

#### 8.4.2 Modal (Python)

```python
# modal_agent/tracing.py
from opentelemetry import trace, context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
import os

def init_tracing():
    """Initialize OTel tracing for Modal container."""
    resource = Resource.create({
        SERVICE_NAME: "agent-executor",
        "agent.execution_segment": os.environ.get("EXECUTION_SEGMENT", "1"),
    })
    
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] + "/v1/traces",
            headers={"x-honeycomb-team": os.environ["HONEYCOMB_API_KEY"]},
        )
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    
    # Auto-instrument HTTP calls (webhooks, Anthropic API)
    HTTPXClientInstrumentor().instrument()
    
    return trace.get_tracer("agent-executor")


def restore_trace_context(traceparent: str):
    """Restore trace context from W3C traceparent header."""
    propagator = TraceContextTextMapPropagator()
    carrier = {"traceparent": traceparent}
    return propagator.extract(carrier)


# Usage in executor
tracer = init_tracing()

@app.function(...)
async def execute_agent(
    task_id: str,
    traceparent: str,  # Passed from Vercel
    execution_segment: int,
    ...
):
    # Restore trace context so this segment joins the parent trace
    parent_ctx = restore_trace_context(traceparent)
    
    with tracer.start_as_current_span(
        "modal.agent.execute_segment",
        context=parent_ctx,
        attributes={
            "agent.task_id": task_id,
            "agent.execution_segment": execution_segment,
        },
    ) as span:
        try:
            # Agent execution loop...
            with tracer.start_as_current_span("claude.completion") as llm_span:
                response = await client.messages.create(...)
                llm_span.set_attribute("llm.model", "claude-sonnet-4-5")
                llm_span.set_attribute("llm.tokens.input", response.usage.input_tokens)
                llm_span.set_attribute("llm.tokens.output", response.usage.output_tokens)
            
            # Tool execution
            with tracer.start_as_current_span("tool.bash") as tool_span:
                tool_span.set_attribute("tool.name", "bash")
                tool_span.set_attribute("tool.input", command[:100])  # Truncate
                result = execute_bash(command)
                tool_span.set_attribute("tool.success", result.success)
                
        except Exception as e:
            span.set_status(SpanStatusCode.ERROR, str(e))
            span.record_exception(e)
            raise
```

### 8.5 Semantic Conventions (Custom Attributes)

Following OTel semantic conventions with agent-specific extensions:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `agent.task_id` | string | Unique task identifier | `task_abc123` |
| `agent.session_id` | string | Chat session ID | `sess_xyz789` |
| `agent.sdk_session_id` | string | Claude Agent SDK session | `sdk_sess_456` |
| `agent.execution_segment` | int | Segment number (1 = initial, 2+ = resumed) | `2` |
| `agent.status` | string | Task status at span end | `completed` |
| `llm.model` | string | Model identifier | `claude-sonnet-4-5` |
| `llm.tokens.input` | int | Input token count | `1500` |
| `llm.tokens.output` | int | Output token count | `800` |
| `llm.tokens.total` | int | Total tokens | `2300` |
| `llm.stop_reason` | string | Why completion stopped | `tool_use` |
| `tool.name` | string | Tool being executed | `bash` |
| `tool.input` | string | Tool input (truncated) | `ls -la` |
| `tool.success` | bool | Whether tool succeeded | `true` |
| `tool.duration_ms` | int | Tool execution time | `150` |
| `clarification.question` | string | Question asked (truncated) | `Which database?` |
| `clarification.wait_ms` | int | Time waiting for response | `180000` |

### 8.6 Metrics

```typescript
// Vercel metrics
const meter = metrics.getMeter('agent-frontend');

// Counters
const tasksStarted = meter.createCounter('agent.tasks.started');
const tasksCompleted = meter.createCounter('agent.tasks.completed');
const tasksFailed = meter.createCounter('agent.tasks.failed');
const clarificationsRequested = meter.createCounter('agent.clarifications.requested');

// Histograms
const taskDuration = meter.createHistogram('agent.task.duration_ms', {
  description: 'Task duration from start to completion',
  unit: 'ms',
});
const clarificationWaitTime = meter.createHistogram('agent.clarification.wait_ms', {
  description: 'Time spent waiting for user clarification',
  unit: 'ms',
});
const llmLatency = meter.createHistogram('agent.llm.latency_ms', {
  description: 'Claude API call latency',
  unit: 'ms',
});
const tokenUsage = meter.createHistogram('agent.llm.tokens', {
  description: 'Tokens used per LLM call',
});

// Gauges (via observable)
meter.createObservableGauge('agent.tasks.active', {
  description: 'Currently running or waiting tasks',
}, async (result) => {
  const count = await db.agentTask.count({
    where: { status: { in: ['running', 'awaiting_input'] } }
  });
  result.observe(count);
});
```

### 8.7 Logging Integration

Correlate logs with traces using trace context:

```typescript
// Structured logging with trace correlation
import pino from 'pino';
import { context, trace } from '@opentelemetry/api';

const logger = pino({
  mixin() {
    const span = trace.getSpan(context.active());
    if (span) {
      const ctx = span.spanContext();
      return {
        trace_id: ctx.traceId,
        span_id: ctx.spanId,
        trace_flags: ctx.traceFlags,
      };
    }
    return {};
  },
});

// Usage
logger.info({ taskId, event: 'clarification_sent' }, 'Agent requested clarification');

// Output (JSON):
// {
//   "level": 30,
//   "time": 1706518800000,
//   "trace_id": "0af7651916cd43dd8448eb211c80319c",
//   "span_id": "b7ad6b7169203331",
//   "taskId": "task_abc123",
//   "event": "clarification_sent",
//   "msg": "Agent requested clarification"
// }
```

### 8.8 Backend Options

| Backend | Pros | Cons | Cost |
|---------|------|------|------|
| **Honeycomb** | Excellent for high-cardinality, great UI for traces | Learning curve | Free tier: 20M events/mo |
| **Grafana Cloud** | Full stack (Tempo, Loki, Prometheus), familiar | Complex setup | Free tier: 50GB traces/mo |
| **Jaeger** | Self-hosted, no cost | Operational burden | Free (self-hosted) |
| **Datadog** | All-in-one, great APM | Expensive at scale | $$$$ |
| **Axiom** | Developer-friendly, generous free tier | Newer product | Free tier: 500GB/mo |

**Recommendation for learning:** Start with **Honeycomb** (excellent trace visualization for debugging agent flows) or **Grafana Cloud** (if you want the full Grafana ecosystem).

### 8.9 Trace Context in Webhook Payloads

```typescript
// Modal → Vercel webhook payload
interface WebhookEvent {
  type: 'status_update' | 'clarification_needed' | 'completed' | 'failed';
  taskId: string;
  
  // OTel trace context for correlation
  traceContext: {
    traceparent: string;
    tracestate?: string;
  };
  
  // Event-specific payload
  payload: any;
}

// Vercel webhook handler
export async function POST(req: Request) {
  const event: WebhookEvent = await req.json();
  
  // Restore trace context
  const ctx = propagation.extract(context.active(), event.traceContext);
  
  return context.with(ctx, async () => {
    const span = tracer.startSpan('webhook.handle', {
      attributes: { 
        'webhook.type': event.type,
        'agent.task_id': event.taskId,
      },
    });
    
    try {
      // Handle webhook...
      await handleWebhookEvent(event);
      span.setStatus({ code: SpanStatusCode.OK });
    } finally {
      span.end();
    }
  });
}
```

### 8.10 Debugging Workflows

Common debugging scenarios and how to find them:

| Scenario | Query Strategy |
|----------|----------------|
| "Why did this task take so long?" | Filter by `agent.task_id`, look at span durations |
| "Where did clarification go wrong?" | Filter by `clarification.*` attributes |
| "What tools did the agent use?" | Filter by `tool.name`, group by task |
| "Token usage by task" | Aggregate `llm.tokens.total` by `agent.task_id` |
| "Failed tasks this hour" | Filter `agent.status = failed`, time range |
| "Slow LLM calls" | Histogram of `agent.llm.latency_ms`, p99 |

### 8.11 Alert Conditions

```yaml
# Example alert definitions (Honeycomb/Grafana format)
alerts:
  - name: high_task_failure_rate
    query: |
      count() where agent.status = "failed" 
      / count() where agent.status in ("completed", "failed")
    threshold: "> 0.1"  # >10% failure rate
    window: 15m
    
  - name: slow_llm_latency
    query: |
      p99(agent.llm.latency_ms)
    threshold: "> 10000"  # p99 > 10s
    window: 5m
    
  - name: stuck_tasks
    query: |
      count() where agent.status = "awaiting_input" 
      and duration_ms > 3600000  # > 1 hour
    threshold: "> 5"
    window: 1h
    
  - name: high_token_usage
    query: |
      sum(llm.tokens.total) by agent.task_id
    threshold: "> 100000"  # > 100k tokens per task
    window: 1h
```

---

## 9. Future Considerations

### 9.1 Not in Scope (V1)

- Multi-user collaboration on tasks
- Persistent file storage across tasks
- Custom tool definitions by users
- Task templates/presets
- Billing/usage limits

### 9.2 Potential V2 Features

- **File persistence**: Modal Volumes or S3 for cross-session file access
- **Task forking**: Branch from clarification point to explore alternatives (SDK supports `forkSession`)
- **Streaming tool output**: Real-time terminal output for long-running commands
- **Agent memory**: Cross-task context via Claude's memory or vector store

---

## 10. Implementation Milestones

| Phase | Scope | Duration |
|-------|-------|----------|
| **Phase 1: Foundation** | DB schema, basic API routes, Modal skeleton | 1 week |
| **Phase 2: Core Loop** | Agent execution, webhook handling, status updates | 1 week |
| **Phase 3: Clarifications** | AskUser tool, checkpoint/resume, SSE streaming | 1 week |
| **Phase 4: UI Polish** | Chat integration, status panel, error states | 1 week |
| **Phase 5: Hardening** | Auth, security, observability, testing | 1 week |

---

---

## Appendix B: Claude Agent SDK Session Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Session Lifecycle                                     │
└─────────────────────────────────────────────────────────────────────────────┘

1. NEW SESSION
   ┌─────────────────────────────────────────┐
   │ const response = query({                │
   │   prompt: "Build a REST API",           │
   │   options: { model: "claude-sonnet-4-5" }│
   │ });                                     │
   └─────────────────────────────────────────┘
              │
              ▼
   ┌─────────────────────────────────────────┐
   │ System init message:                    │
   │ { type: 'system', subtype: 'init',     │
   │   session_id: 'sess_abc123' }          │  ◄── SAVE THIS!
   └─────────────────────────────────────────┘

2. RESUME SESSION (after clarification)
   ┌─────────────────────────────────────────┐
   │ const response = query({                │
   │   prompt: userClarificationResponse,    │  ◄── User's answer
   │   options: {                            │
   │     resume: 'sess_abc123',              │  ◄── Saved session ID
   │     model: "claude-sonnet-4-5"          │
   │   }                                     │
   │ });                                     │
   └─────────────────────────────────────────┘
              │
              ▼
   ┌─────────────────────────────────────────┐
   │ SDK automatically loads:                │
   │ • Full conversation history             │
   │ • All tool call results                 │
   │ • Agent's plan and context              │
   │                                         │
   │ Agent continues seamlessly!             │
   └─────────────────────────────────────────┘

3. WHAT YOU DON'T NEED TO STORE
   ✗ Conversation messages
   ✗ Tool results
   ✗ "Resume point" markers
   ✗ Agent's internal state
   
   ✓ Just the session_id string!
```

---

*End of Document*