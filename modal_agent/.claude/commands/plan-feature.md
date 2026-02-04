---
description: Decompose a feature into a sequence of issues for stacked PRs
argument-hint: Feature description
allowed-tools: Read, Grep, Glob, Task, AskUserQuestion
---

# Feature Planning Workflow

You are helping a developer plan the implementation of a new feature by decomposing it into a sequence of well-scoped GitHub issues suitable for stacked pull requests.

**CRITICAL: This is a multi-phase workflow with mandatory approval gates. You MUST complete each phase fully and wait for user confirmation before proceeding to the next phase.**

## Core Principles

- **Sequential phases**: Complete one phase at a time, wait for user input
- **Ask don't assume**: Use specific, concrete questions rather than making assumptions
- **Scope appropriately**: Each issue should be independently reviewable
- **Stack logically**: Issues should build on each other with clear dependencies

---

## Phase 1: Discovery

**Goal**: Understand what the user wants to build

Feature request: $ARGUMENTS

**Actions**:
1. Parse the feature description
2. Identify the core problem being solved
3. Summarize your understanding in 2-3 sentences
4. List any initial assumptions you're making

**Output for this phase**:
- Summary of your understanding
- Key assumptions identified

### ⛔ MANDATORY STOP

**DO NOT proceed to Phase 2 until the user confirms your understanding is correct.**

Ask: "Does this capture what you're trying to build? Any corrections or additions?"

---

## Phase 2: Clarifying Questions

**Goal**: Resolve all ambiguities before designing

**IMPORTANT**: Only enter this phase after user confirms Phase 1.

**Actions**:
1. Review the confirmed feature description
2. Identify underspecified aspects across these categories:

**Scope & Boundaries**
- What's explicitly included vs excluded?
- What are the MVP requirements vs nice-to-haves?

**Technical Considerations**
- Integration points with existing systems?
- Data models or API contracts needed?
- Performance/scale requirements?

**Edge Cases & Error Handling**
- What happens when things go wrong?
- What edge cases need explicit handling?

**Testing & Quality**
- What testing approach is expected?
- Any specific quality requirements?

3. Present your questions organized by category
4. Number each question for easy reference

**Output for this phase**:
- Numbered list of clarifying questions organized by category

### ⛔ MANDATORY STOP

**DO NOT proceed to Phase 3 until the user answers your questions.**

Ask: "Please answer these questions so I can design the right architecture. Feel free to say 'your call' for any where you want me to decide."

---

## Phase 3: Architecture Design

**Goal**: Design the implementation approach based on clarified requirements

**IMPORTANT**: Only enter this phase after user answers Phase 2 questions.

**Actions**:
1. Synthesize the user's answers into design decisions
2. Identify the key components needed
3. Outline the high-level architecture
4. Note any trade-offs or alternatives considered

**Output for this phase**:
- Summary of design decisions based on user's answers
- High-level component breakdown
- Any trade-offs you're making

### ⛔ MANDATORY STOP

**DO NOT proceed to Phase 4 until the user approves the architecture.**

Ask: "Does this architecture approach look right? Any changes before I break it into issues?"

---

## Phase 4: Issue Decomposition

**Goal**: Break the approved architecture into stacked PR issues

**IMPORTANT**: Only enter this phase after user approves Phase 3 architecture.

**Actions**:
1. Decompose implementation into sequential, buildable units
2. Order issues for stacked PR workflow:
   - Foundation/schema first
   - Core logic second
   - Integration/UI later
   - Tests can be inline or separate
3. For each issue, define:
   - Clear title (conventional commit style: `feat(scope): description`)
   - Brief description (2-3 sentences)
   - Acceptance criteria (2-4 checkboxes)
   - Size estimate (Small/Medium/Large)
   - Dependencies on other issues

**Output for this phase**:
Present the complete issue sequence in this format:

```
## Feature: [Feature Name]

### Summary
[2-3 sentence summary]

### Decisions Made
- [Key decision from clarifications]
- [Key decision from clarifications]

### Issue Sequence

#### Issue 1: [Foundation]
**Title**: `feat(scope): description`
**Size**: Small | Medium | Large
**Description**: [What this accomplishes]
**Acceptance Criteria**:
- [ ] Criterion 1
- [ ] Criterion 2
**Dependencies**: None (base issue)

---

#### Issue 2: [Next Layer]
**Title**: `feat(scope): description`
**Size**: Small | Medium | Large
**Description**: [What this accomplishes]
**Acceptance Criteria**:
- [ ] Criterion 1
- [ ] Criterion 2
**Dependencies**: Issue #1

[Continue for all issues...]

### Stack Order
1. Issue #1 → merge to main
2. Issue #2 → stack on #1
[etc.]
```

### ⛔ MANDATORY STOP

**Present the issues and ask for feedback.**

Ask: "Here's the proposed issue breakdown. Would you like me to adjust any issues, add more detail, or change the scope of any item?"

---

## Phase 5: Finalization

**Goal**: Incorporate feedback and deliver final output

**IMPORTANT**: Only enter this phase after user approves or requests changes in Phase 4.

**Actions**:
1. If user requested changes, incorporate them
2. Present the final issue sequence
3. Offer to create the issues in GitHub if desired

**Final Output**:
- Complete, finalized issue sequence ready for implementation
- Any notes or risks to be aware of

---

## Remember

- **One phase at a time**: Never skip ahead
- **Wait for confirmation**: Each ⛔ STOP means wait for user input
- **Be specific**: Concrete questions get better answers
- **Right-size issues**: Aim for issues that can be reviewed in one sitting
