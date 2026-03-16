# E-113-01: Rewrite Completion-Report Protocol in Implement Skill

## Epic
[E-113: Dispatch Boundary Enforcement](epic.md)

## Status
`TODO`

## Description
After this story is complete, the implement skill's Phase 3 Step 5 is rewritten as a tight, unambiguous completion-report routing protocol with an inline boundary reminder at the decision point, and the Anti-Patterns section consolidates scattered boundary-violation items into a single prominent "quick check trap" pattern.

## Context
The main session's boundary violations happen at a specific moment: after receiving a completion report, before routing it. The current Step 5 describes what to do but leaves a decision gap where the main session fills time with ad-hoc verification ("I'll just check one thing"). This story eliminates the gap by rewriting the protocol as a direct pipeline and inserting a boundary reminder at the exact point of temptation. It also consolidates five scattered anti-pattern items (1, 3, 9, 12, 13) into one named pattern that addresses the root cause: the rationalization that "this is too small to route."

## Acceptance Criteria
- [ ] **AC-1**: Phase 3 Step 5 begins with an inline boundary reminder before any procedural content. The reminder names the specific temptation ("if you are about to read source files, run git log, grep, or inspect the implementation -- stop, that is domain work, route to CR and PM") and is direct, not hedging.
- [ ] **AC-2**: The completion-report protocol is a strict numbered sequence where each step specifies exactly one action. The sequence is: (1) receive completion report, (2) check context-layer-only skip condition, (3) extract Files Changed and Test Results from the report, (4) route to code-reviewer with review template, (5) route to PM for AC verification, (6) wait for both verdicts, (7) triage findings per existing rules. No intermediate steps exist that involve reading, inspecting, or verifying the implementation.
- [ ] **AC-3**: Anti-pattern items 1, 3, 9, 12, 13 are consolidated into a single anti-pattern item with the "quick check trap" framing. The consolidated item names the rationalization pattern ("too small to route," "I'll just verify this one thing," "quick check"), explains why it fails (quick checks are domain work regardless of size), and states the rule (when something feels too small to route, route it anyway). The remaining anti-pattern items are renumbered.
- [ ] **AC-4**: No existing procedural content is lost. The review template, circuit breaker, gate interaction, PM-reviewer disagreement resolution, and merge-back sequence remain intact. Only the framing and sequencing of Step 5 changes.
- [ ] **AC-5**: The existing narrative description of completion-report handling is replaced by the new protocol, not appended alongside it. There is one path through Step 5, not two descriptions of the same process.

## Technical Approach
Read the implement skill's Phase 3 Step 5 and Anti-Patterns section. Rewrite Step 5 as a strict protocol that eliminates the decision gap. Consolidate anti-pattern items. Preserve all procedural content (templates, circuit breaker, etc.) while tightening the framing.

Context files to read:
- `/.claude/skills/implement/SKILL.md` (Phase 3 Step 5 and Anti-Patterns section)
- `/.claude/rules/dispatch-pattern.md` (for the boundary language already established)

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (modified -- Phase 3 Step 5 and Anti-Patterns section)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- The goal is structural change to the decision point, not more prohibitions. The reminder is inline (at the moment of temptation), not in a separate file. The protocol is a pipeline (no gaps), not a narrative (with gaps).
- Keep the boundary reminder brief -- 2-3 sentences, not a paragraph. It's a pattern interrupt, not an essay.
