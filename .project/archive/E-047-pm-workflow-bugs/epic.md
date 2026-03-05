# E-047: PM Workflow Bugs

## Status
`COMPLETED`

## Overview
Fix three PM workflow bugs: (1) PM ignores user-directed collaboration requests during epic formation, (2) PM auto-dispatches stories immediately after marking an epic READY without waiting for user authorization, and (3) the spec-review skill's Phase 1 orchestration instructions are missing timeout, foreground, and duration guidance, causing the team lead to run codex in ways that lose output or hang indefinitely.

## Background & Context
Three bugs were observed during real sessions:

**Bug 1: PM ignores user's explicit collaboration directive.** When a user says "start a team with PM to define the epic and work with engineering," the PM should consult SE (or whichever agent the user names) during formation. Instead, PM skipped the consultation entirely and wrote stories alone. Root cause: the Consultation Triggers table in `product-manager.md` only lists domain experts by epic domain. There is no rule stating that user-directed collaboration requests override the table. The PM followed its table, found "Pure process/workflow -- None required," and proceeded without consultation.

**Bug 2: PM auto-dispatches without user confirmation.** When a user asks PM to "define an epic," PM marks it READY and immediately starts dispatching without returning to the user. Root cause: there is no explicit gate separating "plan" mode (define the epic) from "dispatch" mode (execute the epic). The PM's task types include both but nothing prevents PM from chaining them automatically. The Dispatch Flow in `dispatch-pattern.md` assumes step 1 is "User requests dispatch," but PM collapses "define" and "dispatch" into one action.

**Bug 3: Spec-review skill orchestration failures.** When the user said "spec review epic 45," the skill triggered but the team lead ran codex as a background task, losing its output. First run produced no output and timed out at 10 minutes. A second manual run with `timeout 300` worked in 1m 24s. Root cause: the spec-review skill's Phase 1 instructions say "run the script via Bash" but provide no guidance on timeout, foreground vs background execution, or expected duration. The team lead made reasonable but wrong choices because the skill was ambiguous.

Expert consultation: claude-architect reviewed all three stories and target files. CA confirmed insertion points, found no contradictions, and provided three refinements incorporated below.

## Goals
- User-directed collaboration requests during epic formation are always honored
- Defining an epic and dispatching it are explicitly separate actions requiring separate user authorization
- The spec-review skill's Phase 1 reliably produces codex output without team lead guesswork about timeout, execution mode, or duration
- All rules are clear, concise, and located where the agent will encounter them at decision time

## Non-Goals
- Changing how the Consultation Triggers table works for domain-based consultations (those remain as-is)
- Adding new task types or modes to the PM
- Changing the dispatch flow mechanics (team creation, story execution, closure sequence)
- Adding rules for agents other than the PM
- Modifying the spec-review script itself (`scripts/codex-spec-review.sh`) -- only the skill's orchestration instructions change

## Success Criteria
- The PM agent definition contains a rule that user-directed collaboration requests override the Consultation Triggers table
- The PM agent definition, dispatch-pattern.md, and workflow-discipline.md contain rules that require explicit user authorization before dispatching after epic formation
- The spec-review skill Phase 1 includes timeout, foreground, expected-duration, and timeout-handling guidance
- Rules are positioned where the agent encounters them at the relevant decision point (not buried in unrelated sections)
- No contradictions introduced with existing rules

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-047-01 | User-directed consultation override | DONE | None | claude-architect |
| E-047-02 | Dispatch authorization gate | DONE | E-047-01 | claude-architect |
| E-047-03 | Fix spec-review skill orchestration | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Bug 1 Fix -- User-Directed Consultation Override (Story 01)

**File**: `.claude/agents/product-manager.md`
**Section**: Consultation Triggers (lines 63-75)

Add a new rule immediately above the Consultation Triggers table. The rule should state:

> If the user explicitly requests collaboration with a specific agent during epic formation (e.g., "work with engineering to define this," "consult SE on the stories"), the PM MUST consult that agent before finalizing stories -- regardless of what the Consultation Triggers table recommends. The request must be an explicit directive to collaborate (e.g., imperative verb + agent name), not a passing reference or speculation about what an agent might think. User-directed collaboration requests always take precedence over the table.

This preserves the table as the default guidance while adding a clear override mechanism. The signal-word filter (imperative verb + agent name) prevents over-consultation from casual agent mentions. (CA refinement.)

### Bug 2 Fix -- Dispatch Authorization Gate (Story 02)

Three files need coordinated changes:

**File 1**: `.claude/agents/product-manager.md`

Two insertion points:

(a) **Task Types table** (line 43): Update the "plan" row's Output column to explicitly state that the PM presents the epic to the user and waits for dispatch authorization. Current text: `epic.md + story files in /epics/E-NNN-slug/. Epic status set to READY when complete.` Add: `PM presents the finished epic to the user. Dispatch requires separate user authorization.`

(b) **How Work Flows** (lines 103-109): Insert a new step between Refinement (step 3) and Execution (step 4):
> **User Authorization**: PM presents the READY epic to the user. Execution begins only when the user explicitly requests dispatch.

**File 2**: `.claude/rules/dispatch-pattern.md`

**The Dispatch Flow** step 1 (line 64): Strengthen to read:
> User requests dispatch ("start epic X", "execute story X", "dispatch stories"). Dispatch MUST be initiated by an explicit user request. The PM MUST NOT self-initiate dispatch after completing epic formation -- "define the epic" and "execute the epic" are separate user actions. Exception: compound requests that explicitly include dispatch language (e.g., "define and execute," "plan and dispatch") authorize both planning and dispatch in sequence.

**File 3**: `.claude/rules/workflow-discipline.md`

Add a new section "Dispatch Authorization Gate" after the "Epic READY Gate" section (after line 5):
> Marking an epic READY and dispatching it are separate actions. After the PM sets an epic to READY, the PM MUST present the epic to the user and wait for explicit dispatch authorization. The PM MUST NOT chain plan mode into dispatch mode automatically. Phrases like "define the epic," "create the epic," "plan the epic," and "write stories for X" are plan-mode requests -- they do NOT authorize dispatch. Compound requests that explicitly include dispatch language (e.g., "define and execute," "plan and dispatch," "create the epic and start it") authorize both planning and dispatch in sequence.

The compound-request clause is critical -- without it the PM would force a round-trip confirmation even when the user clearly authorized dispatch up front. (CA refinement.)

The compound-request clause should also appear in `dispatch-pattern.md` step 1 for consistency.

### Bug 3 Fix -- Spec-Review Skill Orchestration (Story 03)

**File**: `.claude/skills/spec-review/SKILL.md`
**Section**: Phase 1 (lines 41-64)

Four changes to Phase 1:

(a) **Step 1 command template**: Wrap with `timeout 300`:
```
timeout 300 ./scripts/codex-spec-review.sh <epic-dir>
```
Add explicit instruction: "Run this command in the foreground (not as a background task) so output is captured directly."

(b) **Step 2 `--note` command template**: Same `timeout 300` prefix for consistency.

(c) **Expected duration note** (new, after Step 1 command): "Codex typically takes 1-2 minutes for a standard epic (3-7 story files). Larger epics may take up to 3 minutes."

(d) **Timeout handling** (integrate into Step 4 or add sub-step): "If the command exits with code 124, codex timed out -- report the timeout to the user and ask how to proceed. Do not retry automatically. Other non-zero exit codes indicate script errors (codex not installed, invalid directory, missing rubric) -- report the specific error message."

This story has no file overlap with stories 01 or 02. It can be dispatched in parallel with story 01.

### Shared File Coordination

Stories 01 and 02 both modify `.claude/agents/product-manager.md` but in non-overlapping sections:
- Story 01: Consultation Triggers section only (lines 63-75)
- Story 02: Task Types table (line 43) and How Work Flows (lines 103-109)

Despite non-overlapping sections, stories 01 and 02 are sequenced (02 depends on 01) to avoid any risk of concurrent edits to the same file. Story 03 touches a different file entirely and can run in parallel with story 01.

## Open Questions
- None. All three bugs have clear root causes and straightforward fixes.

## History
- 2026-03-05: Created with 2 stories (bugs 1 and 2). PM identified insertion points and rule phrasing from file analysis.
- 2026-03-05: Added story 03 (bug 3: spec-review skill orchestration).
- 2026-03-05: CA consultation complete. Three refinements incorporated: (1) signal-word filter on consultation override to prevent over-consultation, (2) compound-request clause on dispatch gate to avoid forcing round-trips when user explicitly authorizes both plan and dispatch, (3) exit code 124 distinction in spec-review timeout handling. CA confirmed all insertion points correct, no contradictions, no unintended side effects.
- 2026-03-05: All 3 stories dispatched to claude-architect and verified DONE. Stories 01+03 ran in parallel, story 02 sequenced after 01 (shared file dependency). All acceptance criteria verified by PM. No documentation impact (all changes are context-layer files, not user-facing docs). Epic COMPLETED.
