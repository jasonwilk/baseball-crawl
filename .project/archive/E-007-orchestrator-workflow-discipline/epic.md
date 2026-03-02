# E-007: Orchestrator Workflow Discipline

## Status
`COMPLETED`

## Overview
This epic hardens the project's agent workflow contract into the infrastructure -- agent prompts, CLAUDE.md, and rules files -- so that the orchestrator-PM-expert-dev pipeline is the canonical, documented, and enforced path for all work. It eliminates ambiguity about who authorizes work, who dispatches it, and what "ready for dev" means.

## Background & Context

### The Problem
The project has a multi-agent ecosystem with clear intended roles, but the workflow contract -- the sequence of who does what before implementation begins -- is not explicitly encoded in any agent prompt or shared rule. This creates two failure modes:

1. **Bypass failure**: The orchestrator routes an implementation request directly to a general-dev or data-engineer agent, skipping PM review and expert consultation. Work gets done that was never properly scoped.
2. **Authority ambiguity**: An implementing agent receives a Task prompt without a PM-approved story file, so it improvises scope, architecture, or approach. The result may contradict other active work.

### The Intended Contract
The workflow contract the user has articulated:
1. **Orchestrator is a lightweight router.** It does no work itself. For project work, it routes to PM.
2. **PM is the hub.** PM consults domain experts (baseball-coach for requirements, api-scout for API constraints, etc.) and produces stories with acceptance criteria before any implementation begins.
3. **"Ready for dev" = Status: TODO in the story file.** A story file with Status: TODO is PM's authorization signal. No story file, no dev work.
4. **"Start epic X" routes to PM.** The orchestrator routes this to PM. PM reads the epic, identifies TODO stories, and dispatches each story to the correct implementation agent via the Task tool. PM tracks completion.
5. **No exceptions.** Implementing agents do not accept work that is not backed by a story file.

### Realistic Scope of Enforcement
Prompt-level enforcement is the ceiling for routed flows. If a user explicitly invokes an implementing agent by name, they bypass the orchestrator entirely -- that is by design (the user has override authority). This epic encodes the contract for the normal routed path, not as a hard block on the user.

### What Changed
Prior to this epic, the PM prompt explicitly said "you do NOT assign work to agents unless asked." That instruction is being replaced with a two-mode model: Planning Mode (existing) and Dispatch Mode (new -- triggered when user says "start epic X" or "execute story Y").

## Goals
- Orchestrator prompt explicitly names PM as the mandatory first stop for all work-initiation requests and prohibits direct routing to implementation agents for unscoped work
- PM prompt includes a concrete Dispatch Mode section describing how to execute an epic: read story files, verify Status: TODO, dispatch each story to the correct agent with the right context
- PM prompt describes what context to include when dispatching (story file path, epic context, relevant Technical Notes)
- CLAUDE.md contains a canonical "Workflow Contract" section that all agents load and can reference
- A new rules file encodes the workflow gate so agents operating on relevant files see it automatically
- All implementing agent prompts (general-dev, data-engineer) include a "Work Authorization" section requiring a story file reference before beginning work
- The changes are testable: given a set of routing scenarios, the expected agent routing matches the actual routing (verified via human walkthrough of the prompts)

## Non-Goals
- Hard technical blocking of direct agent invocation (user retains override authority)
- Changes to how stories are written (the PM story format is not changing)
- Changes to how baseball-coach, api-scout, or other expert agents work internally
- Automated enforcement via hooks or scripts (future idea if needed)
- Changes to epic or story numbering conventions

## Success Criteria
1. The orchestrator prompt contains an explicit rule: implementation requests without a PM-approved story file are routed to PM, not to general-dev or data-engineer.
2. The PM prompt contains a "Dispatch Mode" section that describes exactly how to execute a "start epic X" directive, including: read the epic directory, find TODO stories, match each story to the right implementing agent, invoke via Task tool with story path + context.
3. The PM prompt describes the required context block for each dispatch (story file path, epic Technical Notes, dependency list).
4. CLAUDE.md has a "Workflow Contract" section (under Agent Ecosystem) with the five-step contract as the canonical reference.
5. A new `.claude/rules/workflow-discipline.md` file exists, applies to all paths, and states the gate rule in plain language.
6. The general-dev agent prompt includes a "Work Authorization" check: before beginning any task, verify a story file is referenced; if not, refuse the task and say what is missing.
7. The data-engineer agent prompt includes the same Work Authorization check.
8. A human walkthrough of five routing scenarios (documented in the story) produces the correct agent routing in every case.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|--------------|----------|
| E-007-01 | CLAUDE.md Workflow Contract section | DONE | None | PM |
| E-007-02 | Orchestrator prompt: PM-as-gatekeeper | DONE | E-007-01 | PM |
| E-007-03 | PM prompt: Dispatch Mode | DONE | E-007-01 | PM |
| E-007-04 | Workflow discipline rules file | DONE | E-007-01 | PM |
| E-007-05 | Implementing agent Work Authorization | DONE | E-007-01 | PM |
| E-007-06 | Routing scenario walkthrough and sign-off | DONE | E-007-02, E-007-03, E-007-04, E-007-05 | PM |
| E-007-07 | PM Refinement Mode: expert consultation protocol | DONE | None | PM |
| E-007-08 | Epic dispatch gate: READY status and promotion ritual | DONE | None | PM |
| E-007-09 | PM Decision Gates: evaluation criteria and synthesis ritual | DONE | None | PM |

## Technical Notes

### The "Ready for Dev" Signal
The signal is the story file's Status field. A story with `Status: TODO` is PM-authorized for implementation. There is no additional stamp, flag file, or secondary signal. This is intentional -- keep it simple.

### What "Dispatch Mode" Means for PM
When the user says "start epic E-NNN" or "execute story E-NNN-SS", PM enters Dispatch Mode:
1. Read the epic directory: `/epics/E-NNN-*/epic.md` and all story files.
2. Identify stories with Status: TODO whose dependencies are also satisfied (i.e., all blocking stories are DONE).
3. For each eligible story, identify the correct implementing agent based on story content:
   - Python implementation -> general-dev
   - Database schema / D1 / migrations -> data-engineer
   - API exploration -> api-scout
   - Agent config / CLAUDE.md / rules -> claude-architect
4. Dispatch each story via Task tool with the following context block:
   - Story file path (absolute)
   - Story file full contents
   - Parent epic Technical Notes section
   - List of completed dependency stories (for context)
5. Update story Status to IN_PROGRESS in the story file before dispatching.
6. After each dispatched task completes, verify acceptance criteria, update story Status to DONE, and check for newly unblocked stories.

### Which Agents Get Work Authorization Checks
Only implementing agents receive work authorization language:
- `general-dev` (Python implementation)
- `data-engineer` (schema, migrations, ETL)
- `api-scout` does NOT get this check -- it has an exploratory role and is often invoked directly
- `baseball-coach` does NOT get this check -- it is a domain expert / consultant, not an implementer
- `claude-architect` does NOT get this check -- it designs the infrastructure itself

### File Map for This Epic
This epic touches agent infrastructure files, not source code:
- `/CLAUDE.md` -- Shared by all agents; canonical location for workflow contract
- `/.claude/agents/orchestrator.md` -- Routing rules
- `/.claude/agents/project-manager.md` -- PM system prompt
- `/.claude/agents/general-dev.md` -- Work authorization (may not exist yet)
- `/.claude/agents/data-engineer.md` -- Work authorization (may not exist yet)
- `/.claude/rules/workflow-discipline.md` -- New rules file (create)

Note: `general-dev.md` and `data-engineer.md` may not exist yet. E-007-05 should create them if missing, or add to them if they exist.

### Enforcement Realism
Prompt-level enforcement is not a hard block -- it is a behavioral norm encoded in language. A sufficiently explicit instruction in an agent prompt will be followed reliably by Claude. The realistic failure mode is not the model ignoring the instruction, but the user bypassing the orchestrator entirely. This is acceptable: the user has legitimate override authority.

## Open Questions
- Do `general-dev.md` and `data-engineer.md` agent files currently exist? E-007-05 must check and create them if not. (Check `/Users/jason/Documents/code/baseball-crawl/.claude/agents/` before beginning E-007-05.)
- Should the orchestrator prompt name specific "safe direct-routing" exceptions (e.g., the user can always directly say "hey api-scout, explore this endpoint")? Recommendation: yes, explicitly name the exploratory agents (api-scout, baseball-coach, claude-architect) as direct-routable.

## History
- 2026-02-28: Created. Status set to ACTIVE. CA consultation completed during formation; design decisions incorporated. Stories ready for execution.
- 2026-02-28: All six stories executed by PM in Dispatch Mode. Status set to COMPLETED. Archived.
- 2026-02-28: Reopened. Two gaps identified: (1) PM has no explicit Refinement Mode / expert consultation protocol; (2) epic status system has no explicit dispatch gate between DRAFT and dispatchable. Added E-007-07 and E-007-08.
- 2026-02-28: E-007-07 and E-007-08 executed by PM. Status set to COMPLETED again.
- 2026-02-28: Reopened a third time. Gap identified: PM has no documented pattern for decision gates -- epics that require a final synthesis/evaluation/recommendation step before closing. Added E-007-09.
- 2026-02-28: E-007-09 executed by PM. Decision Gates section added to project-manager.md. Status set to COMPLETED again.
