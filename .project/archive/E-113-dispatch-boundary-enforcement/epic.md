# E-113: Dispatch Boundary Enforcement -- Inline Reminders and Anti-Pattern Consolidation

## Status
`COMPLETED`

## Overview
The main session repeatedly crosses its orchestration boundary during dispatch by performing domain work: reading source files, running git log/grep, and inspecting implementation details instead of routing to the appropriate agent. E-108 and E-124 restructured the dispatch model and tightened the Phase 3 Step 5 protocol into a sound numbered sequence. What remains is a missing pattern interrupt at the decision point and scattered anti-pattern items that dilute the core message.

This epic adds two surgical improvements: (1) an inline boundary reminder at the top of the completion-report protocol, and (2) a domain-work definition that gives the main session a classification tool rather than another prohibition.

## Background & Context

**What E-108 and E-124 already solved**: Phase 3 Step 5 is now a tight numbered sequence (check context-layer skip -> route to CR and PM -> triage findings -> merge-back). The "narrative description" that E-113 originally planned to replace no longer exists. The PM is established as AC verifier. The review workflow has structured triage tracks, circuit breaker, and gate interaction.

**What E-112 changed**: dispatch-pattern.md was slimmed to a stub referencing the implement skill as the authoritative source. It is now the right size for a concise domain-work definition section -- small enough to be read in full, positioned as a standing reference.

**What remains unimplemented**:
1. **No pattern interrupt at the decision point.** Step 5 goes straight into procedural steps. The main session knows the rules but violates them in the moment because there is no reminder at the exact point of temptation -- after receiving a completion report, before acting on it.
2. **Anti-pattern scatter.** Items 1, 3, 9, 12, 13 are all boundary-violation variants with different framings. Consolidating them into one prominent item with the "quick check trap" framing makes the core message unmissable.
3. **No domain-work definition.** The main session has prohibitions ("don't do X") but no classification tool ("is this domain work?"). A simple litmus test provides a cognitive shortcut.

No expert consultation required -- this is PM-domain work definition with CA as implementer for context-layer files. The problem is well-characterized from repeated incidents across multiple epics.

## Goals
- An inline boundary reminder exists at the top of Phase 3 Step 5, naming the specific "quick check" temptation before any procedural content
- Boundary-violation anti-patterns (items 1, 3, 9, 12, 13) are consolidated into a single prominent item with the "quick check trap" framing
- dispatch-pattern.md contains a domain-work definition with a one-line litmus test

## Non-Goals
- **Rewriting Phase 3 Step 5 protocol.** The numbered sequence is already sound (E-108, E-124). Only the boundary reminder is added at the top.
- **Adding a new standalone rule file.** That approach has failed repeatedly.
- **Changing the dispatch architecture.** The three-role model is sound.
- **Adding hooks or automated enforcement.** This is a context-layer fix, not a tooling fix.
- **Addressing non-dispatch boundary violations.** Scope is the dispatch coordination loop.

## Success Criteria
- Phase 3 Step 5 begins with an inline boundary reminder (before the numbered steps) that names the "quick check" temptation and redirects to the routing sequence
- Anti-pattern items 1, 3, 9, 12, 13 are consolidated into a single item with the "quick check trap" framing; remaining items are renumbered
- dispatch-pattern.md contains a "Domain Work During Dispatch" section with a one-line litmus test and concrete action lists (domain work vs. permitted orchestration)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-113-01 | Boundary reminder and anti-pattern consolidation | DONE | None | - |
| E-113-02 | Domain-work definition in dispatch-pattern.md | DONE | None | - |

## Dispatch Team
- claude-architect (E-113-01, E-113-02)

## Technical Notes

### Story 01: Boundary Reminder and Anti-Pattern Consolidation
Two changes to `/.claude/skills/implement/SKILL.md`:

1. **Inline boundary reminder at top of Step 5.** Add a brief (2-3 sentence) pattern interrupt before the existing numbered steps. It names the temptation ("if you are about to read source files, run git log, grep, or inspect the implementation -- stop, that is domain work") and redirects to the routing sequence. This is not a rewrite of Step 5 -- it is a preamble added before the existing step 1.

2. **Anti-pattern consolidation.** Current items 1, 3, 9, 12, 13 are all boundary-violation variants:
   - Item 1: "Do not implement stories yourself" (file creation/modification prohibition)
   - Item 3: "Do not verify ACs or update statuses yourself" (AC/status boundary)
   - Item 9: "Do not mark stories DONE without code-reviewer approval" (bypassing reviewer)
   - Item 12: "Do not absorb agent work" (taking over crashed agent's domain)
   - Item 13: "Do not apply fixes yourself" (routing fixes to implementer)

   Consolidate into one item with the "quick check trap" framing: names the rationalization pattern, explains why it fails, states the rule. The remaining items (2, 4, 5, 6, 7, 8, 10, 11) are preserved and renumbered.

### Story 02: Domain-Work Definition
Add a concise section to `/.claude/rules/dispatch-pattern.md` positioned after Team Roles and before Dispatch Procedures.

**Recommended location: dispatch-pattern.md** (not the implement skill). Rationale: dispatch-pattern.md is the standing reference for dispatch roles and boundaries -- loaded on every interaction via `paths: "**"`. The implement skill is the procedural authority (how to do dispatch). The domain-work definition is a standing classification (what IS domain work), not a procedure. It belongs with the role definitions, not the step-by-step protocol. The implement skill's inline reminder (Story 01) cross-references this definition.

Content: one-line litmus test, brief list of domain-work actions (must route), brief list of permitted orchestration actions (contrast), cross-reference to implement skill. Under 30 lines.

### Parallel Execution
Stories 01 and 02 modify different files with no overlap:
- E-113-01: `/.claude/skills/implement/SKILL.md`
- E-113-02: `/.claude/rules/dispatch-pattern.md`

They can execute in parallel.

## Open Questions
- None.

## History
- 2026-03-16: Created during E-100 dispatch. Main session crossed boundary again by running git log, grep, and code reads during Phase 1 validation instead of routing to CR or SE.
- 2026-03-16: Revised after main session's own failure analysis. Original approach (new standalone rule file) was the same "add another rule" pattern that failed six times. Restructured to modify the decision point in the implement skill itself and add a domain-work definition rather than another prohibition.
- 2026-03-16: Refinement pass with PM + CA. Codex spec review returned 4 findings. Accepted 2: (F1) revised E-113-01 AC-2 to include context-layer-only skip branch; (F3) rewrote E-113-02 AC-5 to be self-contained. Dismissed 2: (F2) missing consultation; (F4) surface area.
- 2026-03-18: Revised to reflect current codebase state after E-108 (PM Dispatch Role), E-124 (Review Workflow Improvements), and E-112 (Context Layer Optimization) shipped. Phase 3 Step 5 is already a sound numbered sequence -- no protocol rewrite needed. Scope narrowed to: (1) inline boundary reminder at top of Step 5, (2) anti-pattern consolidation (items 1/3/9/12/13 into "quick check trap"), (3) domain-work definition in dispatch-pattern.md. Story 01 retitled from "Rewrite completion-report protocol" to "Boundary reminder and anti-pattern consolidation."
- 2026-03-18: COMPLETED. Both stories delivered: (1) E-113-01 added an inline boundary reminder preamble to Phase 3 Step 5 of the implement skill and consolidated anti-pattern items 1/3/9/12/13 into a single "quick check trap" pattern (new item 1), renumbering the remaining 8 items as 2-9. (2) E-113-02 added a "Domain Work During Dispatch" section to dispatch-pattern.md with a one-line litmus test, domain-work action list (5 items), and permitted orchestration action list (6 items). No documentation impact. Context-layer assessment: this epic IS context-layer work (modifies SKILL.md and dispatch-pattern.md) -- changes are self-contained, no further codification needed.
