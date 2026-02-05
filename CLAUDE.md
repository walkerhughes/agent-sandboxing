# Claude Code Development Guidelines

## Project Overview

This is a **Human-in-the-Loop Agent System** with a bifurcated architecture:
- **Chat Mode**: Lightweight, low-latency conversational AI (Vercel)
- **Action Mode**: Heavyweight, sandboxed task execution (Modal)

**Key Innovation**: Event-driven checkpoint/resume pattern using Claude Agent SDK sessions, eliminating idle compute while waiting for human input.

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14+ (App Router), React 18+, Tailwind CSS |
| Chat SDK | Vercel AI SDK |
| Backend | Vercel Serverless Functions |
| Database | Neon (Postgres) + Prisma ORM |
| Agent Runtime | Modal (sandboxed containers) |
| Agent SDK | Claude Agent SDK (TypeScript) |
| LLM | Claude Sonnet 4.5 |

---

## Git Worktree Workflow (Required)

This repository uses **git worktrees** for parallel development. When working on any issue, you MUST use a dedicated worktree rather than working directly in the main repository.

### Setup for New Issues

Before starting work on any issue, create a worktree:

```bash
# 1. Fetch latest changes
git fetch origin

# 2. Create worktree with a new branch for your issue
# Pattern: git worktree add ../agent-sandbox-issue-{NUMBER} -b {BRANCH_NAME}
# Branch naming: feat|fix|chore/short-description

# Examples:
git worktree add ../agent-sandbox-issue-1 -b feat/project-setup
git worktree add ../agent-sandbox-issue-3 -b feat/database-schema
git worktree add ../agent-sandbox-issue-7 -b feat/modal-executor

# 3. Enter your worktree
cd ../agent-sandbox-issue-{NUMBER}

# 4. Verify setup
pwd      # Should be: {REPO_PARENT_DIR}/agent-sandbox-issue-{NUMBER}
git branch  # Your branch should have * next to it
```

### Working in Your Worktree

**All work happens in your worktree directory.** Never work directly in the main repo.

```bash
# Your working directory (the worktree)
../agent-sandbox-issue-{NUMBER}

# NOT this (the main repo)
./agent-sandboxing
```

#### Commit Conventions

- Commit frequently with clear messages
- Reference the issue number in commits
- Push regularly so other agents can see your work

```bash
# Commit message format
git commit -m "feat(#{ISSUE}): short description"
git commit -m "fix(#{ISSUE}): short description"
git commit -m "chore(#{ISSUE}): short description"

# Examples
git commit -m "feat(#1): add project scaffolding with Next.js and Modal"
git commit -m "feat(#3): create Prisma schema for tasks and sessions"
git commit -m "feat(#7): implement Modal agent executor with checkpoint/resume"

# Push to remote
git push -u origin {BRANCH_NAME}
```

### Viewing Other Agents' Work

To see what other agents have committed (without leaving your worktree):

```bash
# Fetch all remote branches
git fetch origin

# List all remote branches
git branch -r

# View recent commits on another branch
git log origin/{OTHER_BRANCH} --oneline -10

# View a specific file from another branch
git show origin/{OTHER_BRANCH}:path/to/file.py

# Diff your branch against another
git diff origin/{OTHER_BRANCH} -- path/to/file
```

### Incorporating Other Agents' Changes

If you depend on work from another agent's branch:

```bash
# Option 1: Merge their branch (preserves history)
git fetch origin
git merge origin/{OTHER_BRANCH}

# Option 2: Rebase onto their branch (cleaner linear history)
git fetch origin
git rebase origin/{OTHER_BRANCH}

# Option 3: Cherry-pick specific commits
git fetch origin
git cherry-pick {COMMIT_HASH}
```

### Completing Your Work

When your issue is complete:

```bash
# 1. Ensure all changes are committed and pushed
git status  # Should be clean
git push origin {BRANCH_NAME}

# 2. Create a pull request
gh pr create --base main --head {BRANCH_NAME} --title "feat(#{ISSUE}): title" --body "Closes #{ISSUE}"

# 3. Do NOT delete the worktree - leave cleanup to the repo owner
```

### Rules

1. **Always use a worktree** - Never commit directly to main or work in the main repo directory
2. **Never checkout other branches** in your worktree - Use `git show` or `git fetch` to view other work
3. **Commit and push frequently** - Other agents may depend on your work
4. **Fetch before checking for updates** - Always `git fetch origin` before looking at other branches
5. **Use conventional commits** - `feat|fix|chore(#issue): description`

### Worktree Management Reference

```bash
# List all worktrees
git worktree list

# Remove a worktree (only repo owner should do this)
git worktree remove ../agent-sandbox-issue-{NUMBER}

# Prune stale worktree references
git worktree prune
```

---

## Project Structure

```
agent-sandboxing/
├── app/                      # Next.js App Router
│   ├── api/
│   │   ├── chat/             # Vercel AI SDK chat endpoint
│   │   └── agent/            # Agent task endpoints
│   │       ├── start/        # POST - create task, spawn Modal
│   │       ├── respond/      # POST - submit clarification
│   │       ├── cancel/       # POST - cancel task
│   │       ├── webhook/      # POST - receive Modal events
│   │       └── [taskId]/
│   │           └── stream/   # GET - SSE for real-time updates
│   ├── layout.tsx
│   └── page.tsx              # Chat interface with mode toggle
├── components/
│   ├── chat/                 # Chat UI components
│   └── status/               # Status panel components
├── lib/
│   ├── db.ts                 # Prisma client
│   ├── redis.ts              # Upstash Redis client
│   └── tracing.ts            # OpenTelemetry helpers
├── modal_agent/              # Modal Python package
│   ├── __init__.py
│   ├── config.py             # Modal app config
│   ├── executor.py           # Agent execution loop
│   ├── tools.py              # Tool definitions (AskUser, etc.)
│   ├── tracing.py            # OTel instrumentation
│   └── webhook.py            # Webhook helpers
├── prisma/
│   └── schema.prisma         # Database schema
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── package.json
├── pyproject.toml            # Modal agent dependencies
└── spec.md                   # Product requirements document
```

---

## Workflow

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately – don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes – don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests – then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **Plan First:** Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan:** Check in before starting implementation
3. **Track Progress:** Mark items complete as you go
4. **Explain Changes:** High-level summary at each step
5. **Document Results:** Add review section to `tasks/todo.md`
6. **Capture Lessons:** Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First:** Make every change as simple as possible. Impact minimal code. Leverage the `/code-simplifier` subagent where necessary.
- **No Laziness:** Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact:** Changes should only touch what's necessary. Avoid introducing bugs.

## Testing

This repository follows **Test-Driven Development (TDD)**. Write tests before implementing features.

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── unit/                    # Fast, isolated unit tests
│   ├── conftest.py          # Unit-specific fixtures (optional)
│   └── ...
└── integration/             # Tests that involve external systems/dependencies
    ├── conftest.py          # Integration-specific fixtures (optional)
    └── ...
```

### TDD Workflow

1. **Red** - Write a failing test for the new functionality
2. **Green** - Write the minimum code to make the test pass
3. **Refactor** - Clean up the code while keeping tests green

### Guidelines

- Place shared fixtures in the root `tests/conftest.py`
- Unit tests should be fast and have no external dependencies
- Integration tests may use databases, APIs, or other services
- TypeScript tests: `npm test` or `npx vitest`
- Python tests (Modal agent): `pytest tests/`

---

## Architecture Reference

### Task State Machine

```
PENDING → RUNNING → COMPLETED
              ↓         ↑
        AWAITING_INPUT ─┘
              ↓
           FAILED / CANCELLED
```

### Key Patterns

1. **Checkpoint/Resume**: When `AskUser` tool is called, Modal container exits (no idle billing). User response spawns a NEW container that resumes via Claude Agent SDK `resume: sessionId`.

2. **Real-time Updates**: Modal → Vercel webhook → Redis pub/sub → SSE to browser.

3. **Session Management**: Only store `agent_session_id` string in Postgres. The Claude Agent SDK handles all conversation state internally.

---

## Issue Tracking

All work is tracked via GitHub Issues.

**Issue #20** is the project roadmap. Reference it to:
- See the full issue list and dependencies
- Understand which issues can be parallelized
- Track overall project progress

Roadmap: https://github.com/walkerhughes/agent-sandboxing/issues/20

### Before Starting Work

1. Review issue #20 to understand where your issue fits
2. Check your specific issue for requirements and acceptance criteria
3. Note any blocking dependencies on other issues
4. Create your worktree and branch
5. Reference the issue number in all commits

### Implementation Phases

| Phase | Issues | Scope |
|-------|--------|-------|
| Phase 1: Foundation | #1-4 | Project setup, Prisma schema, Modal skeleton, chat endpoint |
| Phase 2: Core Loop | #5-7 | Agent start, Modal executor, webhook handler |
| Phase 3: Clarifications | #8-11 | AskUser tool, checkpoint/resume, Redis pub/sub, SSE |
| Phase 4: UI | #12-15 | Chat interface, mode toggle, status panel, clarification UI |
| Phase 5: Hardening | #16-19 | Auth, authorization, error handling, OpenTelemetry |