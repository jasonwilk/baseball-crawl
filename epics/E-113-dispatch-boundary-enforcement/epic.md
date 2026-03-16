# E-113: Dispatch Boundary Enforcement -- Stop Main Session Domain Work

## Status
`READY`

## Overview
The main session repeatedly crosses its orchestration boundary during dispatch by performing domain work: running `git log`, `grep`, reading source code, and inspecting implementation details to verify claims instead of routing to the appropriate agent (code-reviewer or PM). This is a recurring systemic failure despite six prior fix attempts and extensive rules. The problem is not knowledge of the rules -- it is compliance under pressure. When something feels quick ("just a check"), the main session skips routing and does it directly. This epic restructures the implement skill's completion-report handling to eliminate the decision gap where violations occur, rather than adding another prohibition the main session already knows.

## Background & Context

**The failure pattern**: When something feels quick or "just a check," the main session skips routing and does it directly. The rationalization is "this is too small to spawn an agent for" or "I'll just verify this one thing." But quick checks are still domain work.

**Why prior fixes failed**: Every prior attempt (E-015, E-021, E-047, E-056, E-059, E-065, E-108) added rules telling the main session what NOT to do. The main session knows all these rules and breaks them anyway. Adding another rule that says "don't do this" is the definition of repeating the same failed approach. The problem is not knowledge -- it is behavior under pressure.

**What changes behavior**: Structural elimination of the decision gap. The main session violates the boundary at a specific moment: after receiving a completion report, before routing it. At that moment, the main session has a choice: route to agents (correct) or inspect the work itself (violation). The current skill describes what to do but leaves enough ambiguity that the main session fills the gap with ad-hoc verification. The fix is to rewrite the completion-report protocol as a tight, unambiguous sequence that leaves no room for "I'll just check one thing."

**The structural insight**: The problem isn't that the main session doesn't have enough rules. It's that the correct action path has too much friction (verbose templates, multiple steps to assemble review requests) while the violation path has zero friction (just read the file). Reducing routing friction while tightening the protocol eliminates the incentive to shortcut.

No expert consultation required -- this is PM-domain (work definition) with CA as implementer for context-layer files. The problem is well-characterized from repeated incidents across multiple epics.

## Goals
- The implement skill's completion-report handling is rewritten as a tight, unambiguous protocol that leaves no decision gap for ad-hoc verification
- The "quick check" rationalization is explicitly named and addressed at the point of temptation (inline in the protocol, not in a separate anti-patterns section)
- Routing friction is reduced by simplifying the completion-report-to-review-request packaging

## Non-Goals
- **Adding a new standalone rule file restating existing prohibitions.** That approach has failed repeatedly. The fix goes into the implement skill itself, at the decision point.
- **Rewriting the entire implement skill.** Only Phase 3 Step 5 (completion-report handling) and the Anti-Patterns section are modified.
- **Changing the dispatch architecture.** The three-role model (main session, PM, code-reviewer) is sound.
- **Adding hooks or automated enforcement.** This is a context-layer fix, not a tooling fix.
- **Addressing non-dispatch boundary violations.** Scope is the dispatch coordination loop (Phase 3).

## Success Criteria
- Phase 3 Step 5 of the implement skill contains a rewritten completion-report protocol that is a strict sequence: receive report -> extract data -> route to CR and PM -> wait -> triage. No other actions described. No ambiguity about what to do next.
- The protocol includes an inline boundary reminder at the exact decision point (after receiving report, before routing), naming the specific "quick check" temptation and redirecting to the routing sequence
- The dispatch-pattern.md rule includes an explicit "domain work" definition that covers: reading source/test files, running git log/diff/show for inspection (vs. merge-back), running grep to verify claims, running pytest -- with a one-line test: "If you are inspecting what was built or assessing quality, you are doing domain work. Route it."
- The anti-patterns section is updated to consolidate boundary-violation items (currently scattered across items 1, 3, 9, 12, 13) into a single, prominent item with the "quick check" framing

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-113-01 | Rewrite completion-report protocol in implement skill | TODO | None | - |
| E-113-02 | Add domain-work definition to dispatch-pattern.md | TODO | None | - |

## Dispatch Team
- claude-architect (E-113-01, E-113-02)

## Technical Notes

### The Decision Gap
The main session's boundary violations happen at a specific moment in the dispatch loop:

```
Implementer reports completion
    |
    v
[DECISION GAP] <-- violations happen here
    |
    v
Route to CR and PM
```

At the decision gap, the main session has tools (Read, Grep, Bash) and a completion report with file paths. The temptation is to "just check" one thing before routing. Every violation starts with "I'll just..." and ends with the main session having done the code-reviewer's or PM's job.

The fix eliminates the gap by making the protocol a direct pipeline: completion report arrives -> extract Files Changed and Test Results -> immediately route to CR (with review template) and PM (with AC verification request) -> wait. No intermediate steps. No "first let me verify..." No "I'll just confirm..."

### Story 01: Implement Skill Rewrite (Phase 3 Step 5)
Rewrite the completion-report handling to:

1. **Tighten the protocol.** Replace the current narrative description with a strict numbered sequence. Each step specifies exactly one action. There is no step that says "review the work" or "confirm the changes."

2. **Inline boundary reminder.** At the top of Step 5, before any action, insert a brief, direct reminder: "You have received a completion report. Your only job is to route it. If you are about to read source files, run git log, grep, or inspect the implementation in any way -- stop. That is domain work. Route to CR and PM." This is not a separate rule file; it's at the exact point of temptation.

3. **Consolidate anti-patterns.** Merge items 1, 3, 9, 12, 13 (all boundary-violation variants) into a single prominent anti-pattern with the "quick check" framing. Current framing is abstract ("do not implement stories yourself"). New framing is concrete and names the rationalization ("the 'quick check' trap: when something feels too small to route, route it anyway").

### Story 02: Domain-Work Definition in dispatch-pattern.md
Add a concise "Domain Work" definition section to dispatch-pattern.md that provides a simple litmus test the main session can apply:

**"If you are inspecting what was built or assessing quality, you are doing domain work. Route it."**

This covers: reading source/test files to verify claims, running git log/diff/show for implementation inspection (not merge-back mechanics), running grep to confirm patterns were changed, running pytest. The definition complements but doesn't duplicate the implement skill's inline reminder -- it's the standing reference, while the skill has the in-the-moment prompt.

### Why This Approach Is Different From Prior Fixes
Prior fixes added new rules in new locations. This fix modifies the existing decision point:
- Story 01 changes the implement skill itself -- the authoritative dispatch procedure -- not a satellite rule
- The boundary reminder is inline at the moment of temptation, not in a separate file
- The anti-patterns are consolidated from scattered items into one named pattern ("quick check trap")
- Story 02 adds a definition (what IS domain work?) rather than a prohibition (don't do X) -- giving the main session a cognitive tool to classify its own impulses

### Parallel Execution
Stories 01 and 02 modify different files with no overlap:
- E-113-01: `.claude/skills/implement/SKILL.md`
- E-113-02: `.claude/rules/dispatch-pattern.md`

They can execute in parallel.

## Open Questions
- None. The problem is well-characterized from repeated incidents and the main session's own failure analysis.

## History
- 2026-03-16: Created during E-100 dispatch. Main session crossed boundary again by running git log, grep, and code reads during Phase 1 validation instead of routing to CR or SE.
- 2026-03-16: Revised after main session's own failure analysis. Original approach (new standalone rule file) was the same "add another rule" pattern that failed six times. Restructured to modify the decision point in the implement skill itself and add a domain-work definition rather than another prohibition.
- 2026-03-16: Refinement pass with PM + CA. Codex spec review returned 4 findings. Accepted 2: (F1) revised E-113-01 AC-2 to include context-layer-only skip branch — resolves contradiction with AC-4's preservation requirement; (F3) rewrote E-113-02 AC-5 to be self-contained — evaluable against current skill content, not Story 01's output. Dismissed 2: (F2) missing consultation — advisory gate, CA already on refinement team; (F4) surface area — rubric heuristic doesn't fit when the deliverable is a structured list.
