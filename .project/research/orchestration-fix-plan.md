# Orchestration Layer Fix Plan

## Problem Statement

Agent Teams is enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) and has been proven to work (E-005 dispatch). But the entire orchestration layer still documents the old `CLAUDECODE=1` nesting constraint as if it were the only dispatch mechanism. This creates three problems:

1. **dispatch-pattern.md** says subagents cannot spawn sub-subagents, which is true for the Task tool but irrelevant when using Agent Teams. The file's PM Dispatch Rule forces an awkward "invoke PM directly" ceremony that is no longer necessary.
2. **orchestrator.md** has an entire Dispatch Rule section and Anti-Pattern #2 dedicated to routing around a constraint that Agent Teams bypasses.
3. **product-manager.md** has a Subagent Detection section that emits an error and refuses to work when it detects it's running as a subagent -- exactly the situation Agent Teams creates.

The fix: update all files to treat Agent Teams as the primary dispatch mechanism.

---

## File-by-File Plan

### 1. `.claude/rules/dispatch-pattern.md`

**Current content (30 lines):** Documents the `CLAUDECODE=1` nesting constraint, the PM Dispatch Rule (two modes), and the Orchestrator Routing Rule.

**Verdict: FULL REWRITE.** The entire file is about a constraint that Agent Teams bypasses. Keep the file (it's a useful place to document dispatch mechanics), but rewrite the content.

#### DELETE:
- The entire "Nesting Constraint" section about `CLAUDECODE=1`
- "Mode 2 -- Subagent Context" with the error message
- The Orchestrator Routing Rule that says "do NOT wrap PM in a Task tool call"

#### REWRITE to:
```markdown
---
paths:
  - "**"
---

# Dispatch Pattern

## How Dispatch Works

The PM dispatches implementation work using **Agent Teams**. When executing an epic:

1. PM creates a team (or operates within an existing team session).
2. PM spawns implementing agents (`general-dev`, `data-engineer`) as teammates using the Agent tool.
3. Teammates execute stories concurrently when stories are independent.
4. PM coordinates completion, verifies acceptance criteria, and marks stories DONE.

## Orchestrator Routing

The orchestrator routes dispatch requests ("start epic X", "execute story X") to the PM via normal routing. No special ceremony is required -- the PM handles team creation and agent spawning internally.

## Task Tool vs. Agent Teams

- **Task tool**: Single subagent, no further nesting. Use for simple consultations (e.g., PM consulting baseball-coach for domain input).
- **Agent Teams**: Multi-agent coordination with free spawning. Use for epic/story dispatch where the PM needs to spawn multiple implementing agents.

The PM chooses the appropriate mechanism based on the task. Consultation = Task tool. Dispatch = Agent Teams.
```

**Rationale:** The old file was 100% about a workaround. The new file documents how dispatch actually works now.

---

### 2. `.claude/agents/orchestrator.md`

**Current content (156 lines):** Routing table, file-based routing, dispatch rule, anti-patterns, available agents, skill references, response format.

#### DELETE:
- **Lines 68-71 (Dispatch Rule section):** The entire "Do NOT route these via a Task call to the PM" paragraph. This is the core workaround being eliminated.
- **Lines 80-82 (Anti-Pattern #2):** "Never route dispatch requests through a Task call to PM." This anti-pattern is now wrong -- routing dispatch requests to PM via Task/normal routing IS the correct behavior.
- **Line 100:** The routing note "Dispatch requests must NOT be wrapped in a Task call -- tell the user to invoke PM directly."
- **Line 154:** "For dispatch requests, respond with a brief instruction telling the user to invoke PM directly."

#### REWRITE:
- **Routing table, "Work initiation / dispatch" row:** Currently says target is `product-manager`. KEEP the target. But remove any footnotes about special dispatch handling.
- **Routing table, "General implementation" and "Schema / data architecture" rows:** Currently say `product-manager (first)`. KEEP as-is -- this is correct.
- **Anti-Pattern #2:** Replace with: "Never route dispatch requests directly to implementing agents. Route to product-manager, which handles team creation and agent spawning."
- **product-manager entry in Available Agents (line 100):** Replace routing note with: "All work-initiation and dispatch requests route here. PM handles team creation and agent spawning internally."

#### KEEP (unchanged):
- The frontmatter (name, description, model, color, tools)
- "Your Single Responsibility" section
- "How You Work" section (steps 1-4)
- The routing table structure and all non-dispatch rows
- Direct-Routing Exceptions section
- File-Based Routing section (all of it)
- Anti-Patterns #1, #3, #4, #5
- Available Agents registry (all entries except routing notes that reference dispatch workaround)
- Skill References section
- Response Format section (except the dispatch line being deleted)

#### ADD:
- Nothing. The orchestrator gets simpler, not more complex.

---

### 3. `.claude/agents/product-manager.md`

**Current content (263 lines):** Identity, philosophy, task types, delegation, consultation, numbering, file org, system of work, dispatch mode, decision gates, ideas workflow, skills, quality checklist, memory instructions.

#### DELETE:
- **Lines 136-142 (Subagent Detection section):** The entire section that detects subagent context and emits the error. This is the mechanism that breaks when PM is routed to via the orchestrator. With Agent Teams, the PM can spawn implementing agents regardless of how it was invoked.

#### REWRITE:
- **Lines 132-134 (Dispatch Mode intro):** Currently says "Dispatch Mode fires when the user says..." -- this is fine but needs a small tweak. The PM may now receive dispatch requests from the orchestrator (not just directly from the user). Rewrite the intro sentence to: "Dispatch Mode fires when the PM receives a dispatch directive -- whether from the user directly or routed via the orchestrator."
- **Lines 144-153 (Dispatch Procedure header):** Currently says "(Main Session Only)". Remove that qualifier. The procedure works in any context now.
- **Line 150 ("Dispatch via Task tool"):** Rewrite step 5 to:

```
5. **Dispatch via Agent Teams.** For eligible stories, spawn implementing agents as teammates. Include the full context block (see below) in the spawn prompt. When stories are independent, spawn agents concurrently. When stories have dependencies, dispatch sequentially. For single-story dispatches or simple consultations during refinement, the Task tool is also acceptable.
```

#### KEEP (unchanged):
- Identity, Core Principle, Philosophy sections
- Task Types table
- Technical Delegation Boundaries
- Consultation Triggers
- Numbering Scheme, File Organization
- System of Work (epic statuses, story statuses, how work flows, parallel execution rules)
- Atomic Status Update Protocol
- Dispatch Procedure steps 1-4 and 6-7 (the read/check/identify/update/verify/close steps)
- Agent Selection table
- Context Block Format
- Decision Gates
- Ideas Workflow
- Skills section
- Quality Checklist
- Memory Instructions

#### ADD:
- Nothing beyond the rewrites above. The PM prompt is already comprehensive and well-structured.

---

### 4. `.claude/rules/workflow-discipline.md`

**Current content (30 lines):** Epic READY Gate, Work Authorization Gate, Workflow Routing Rule, PM Task Types, Direct-Routing Exceptions.

#### DELETE:
- **In "Workflow Routing Rule" (line 18):** The phrase "via the Task tool" -- the PM dispatches via Agent Teams now, not exclusively via Task tool. The rest of the sentence is correct (PM is the only agent authorized to transition stories and dispatch work).

#### REWRITE:
- **Line 18:** Change "dispatch implementation work via the Task tool" to "dispatch implementation work (via Agent Teams for multi-story execution, or Task tool for single consultations)."

#### KEEP (unchanged):
- Epic READY Gate -- still valid, still important
- Work Authorization Gate -- still valid, still important
- PM Task Types -- still valid
- Direct-Routing Exceptions -- still valid
- The overall structure and purpose of this file

#### ADD:
- Nothing. This file is tight and correct except for the one Task-tool-specific phrase.

---

### 5. `CLAUDE.md` -- Workflow Contract section (lines 209-222)

#### DELETE:
- **Line 217, item 5:** `"Start epic X" dispatches through PM. PM must run in the main session to dispatch implementing agents (not as a subagent). See /.claude/rules/dispatch-pattern.md for the nesting constraint.`

#### REWRITE item 5 to:
```
5. **"Start epic X" dispatches through PM.** PM handles team creation and agent spawning internally. See `/.claude/rules/dispatch-pattern.md` for dispatch mechanics.
```

#### KEEP (unchanged):
- Items 1-4 and 6 of the Workflow Contract -- all still valid
- Enforcement Boundary and Direct-Routing Exceptions -- still valid
- The entire rest of CLAUDE.md (Core Principle, Project Purpose, Tech Stack, Code Style, Architecture, Security, HTTP Request Discipline, Testing, Project Management, Git Conventions, Agent Ecosystem table, How Agents Collaborate, Statusline)

#### ADD:
- Nothing. CLAUDE.md stays lean.

---

### 6. `.claude/settings.json`

**Current content:**
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "statusLine": { ... }
}
```

#### ADD:
```json
"agent": "orchestrator"
```

This makes the orchestrator the default agent for all sessions, which is the intended behavior (currently it loads the default Claude session and you have to explicitly invoke the orchestrator).

#### KEEP:
- The `env` block with Agent Teams enabled
- The `statusLine` configuration

#### DELETE:
- Nothing.

**New settings.json:**
```json
{
  "agent": "orchestrator",
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "statusLine": {
    "type": "command",
    "command": ".claude/hooks/statusline.sh",
    "padding": 1
  }
}
```

---

### 7. `.claude/skills/multi-agent-patterns/SKILL.md`

**Current content (235 lines):** Activation triggers, three coordination patterns (supervisor/peer-to-peer/hybrid), telephone game problem, verbatim relay, practical implementation with routing chain, PM checklist, orchestrator checklist, direct-routing exceptions table, when to shorten the chain, diagnosing telephone game failures, references.

#### DELETE:
- **Lines 26-66 (The Three Coordination Patterns section):** Academic taxonomy of supervisor/peer-to-peer/hybrid. This is theory that no agent actually references during dispatch. The practical sections already cover what matters.
- **Lines 112-129 (Baseball-Crawl's Routing Chain ASCII diagram):** The specific chain `orchestrator -> PM -> implementing agent` is outdated -- with Agent Teams, the PM spawns teammates directly, not through a linear chain. The diagram creates a false mental model.

#### REWRITE:
- **Lines 68-99 (Telephone Game Problem + Verbatim Relay):** KEEP the content but trim to essentials. The telephone game concept is genuinely useful. Cut the "Why it is hard to detect" and "What makes it worse" sub-bullets (theoretical). Keep the core definition, the two risk points, and the mitigation.
- **Lines 130-206 (Practical Implementation):** Rewrite the routing chain section to reflect Agent Teams. The PM checklist and orchestrator checklist are still valid -- keep them. The direct-routing exceptions table duplicates `workflow-discipline.md` -- replace with a pointer.
- **Lines 220-235 (References):** Trim. Keep the pointer to `workflow-discipline.md` and `product-manager.md`. Cut the external reference and research pointers (useful historically but not operationally).

#### KEEP:
- Activation Triggers (lines 9-18) -- still valid
- PM dispatch checklist (lines 152-161) -- still valid
- Orchestrator receive/relay checklist (lines 163-170) -- still valid
- "When to Shorten the Chain" section (lines 184-205) -- still valid and practical
- Diagnosing Telephone Game Failures (lines 207-215) -- still valid

#### Target length: ~120-140 lines (down from 235). Cut theory, keep practice.

---

## Summary of Changes

| File | Action | Key Change |
|------|--------|-----------|
| `dispatch-pattern.md` | Full rewrite | Document Agent Teams as dispatch mechanism |
| `orchestrator.md` | Targeted deletions | Remove dispatch workaround, simplify routing |
| `product-manager.md` | Targeted deletions + rewrite | Remove subagent detection, update dispatch to use Agent Teams |
| `workflow-discipline.md` | One-line edit | Replace "Task tool" with "Agent Teams" |
| `CLAUDE.md` | One-line edit | Remove "main session" constraint from Workflow Contract item 5 |
| `settings.json` | Add one key | `"agent": "orchestrator"` |
| `multi-agent-patterns/SKILL.md` | Trim ~40% | Cut theory, keep practical patterns |

## What This Does NOT Change

- Epic/story workflow (DRAFT -> READY -> ACTIVE -> COMPLETED) -- unchanged
- Work Authorization Gate (implementing agents need story references) -- unchanged
- Direct-routing exceptions (api-scout, baseball-coach, claude-architect) -- unchanged
- PM task types (discover, plan, clarify, triage, close) -- unchanged
- Verbatim relay principle -- unchanged
- Context block format for dispatch -- unchanged
- Quality checklist -- unchanged
- Ideas workflow -- unchanged

The fix is surgical: remove the nesting workaround, document Agent Teams as the dispatch mechanism, and set the orchestrator as default. Everything else stays.

## Execution Order

1. `dispatch-pattern.md` (foundation -- other files reference it)
2. `orchestrator.md` (depends on new dispatch-pattern content)
3. `product-manager.md` (depends on new dispatch model)
4. `workflow-discipline.md` (one-line fix, no dependencies)
5. `CLAUDE.md` (one-line fix, no dependencies)
6. `settings.json` (independent)
7. `multi-agent-patterns/SKILL.md` (independent, largest edit)

Steps 4-7 can be done in parallel. Steps 1-3 should be sequential.

## Memory Updates Required After Execution

- **claude-architect MEMORY.md**: Update "Agent Ecosystem" section to note Agent Teams as dispatch mechanism. Remove references to nesting constraint.
- **product-manager MEMORY.md**: No change needed (PM memory tracks epic/idea numbering, not dispatch mechanics).
- **orchestrator has no memory** (by design) -- no update needed.
