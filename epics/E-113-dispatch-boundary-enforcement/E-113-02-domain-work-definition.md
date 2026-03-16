# E-113-02: Add Domain-Work Definition to dispatch-pattern.md

## Epic
[E-113: Dispatch Boundary Enforcement](epic.md)

## Status
`TODO`

## Description
After this story is complete, dispatch-pattern.md contains a concise "Domain Work" definition section that gives the main session a cognitive tool to classify its own impulses during dispatch: a simple litmus test for whether an action is orchestration (permitted) or domain work (route it).

## Context
The main session knows the boundary rules but violates them because specific actions (reading a file, running grep) don't feel like "verifying ACs" or "writing code" -- they feel like normal due diligence. This story provides a definition of "domain work" that covers the grey area. Prior fixes added prohibitions ("don't do X"); this adds a classification tool ("is this domain work? here's how to tell").

## Acceptance Criteria
- [ ] **AC-1**: dispatch-pattern.md contains a new "Domain Work During Dispatch" section (or equivalent heading) positioned after the Team Roles section and before the Dispatch Procedures reference.
- [ ] **AC-2**: The section provides a one-line litmus test: "If you are inspecting what was built or assessing quality, you are doing domain work. Route it."
- [ ] **AC-3**: The section includes a brief list of concrete domain-work actions the main session must route instead of performing: (a) reading source or test files to verify implementation claims, (b) running `git log`, `git diff`, or `git show` to inspect what was committed (not merge-back mechanics), (c) running `grep` to confirm patterns were added or removed, (d) running `pytest` or any test commands, (e) assessing whether acceptance criteria are met.
- [ ] **AC-4**: The section includes a brief list of permitted orchestration actions for contrast: (a) reading epic and story files for routing decisions, (b) git commands for merge-back mechanics (git merge, git worktree, git branch -d), (c) sending messages to teammates via SendMessage, (d) team lifecycle management (spawn, shutdown).
- [ ] **AC-5**: The section does not duplicate the implement skill's Phase 3 Step 5 protocol or Anti-Patterns section. It is a standing definition (what IS domain work?) not a procedural protocol (what to DO when a completion report arrives). A brief cross-reference to the implement skill is acceptable.

## Technical Approach
Read dispatch-pattern.md and the implement skill's revised Step 5 (from E-113-01, if already complete -- otherwise work from the current version). Add a concise domain-work definition section. Keep it short -- the value is the litmus test and the concrete action list, not prose explanation.

Context files to read:
- `/.claude/rules/dispatch-pattern.md`
- `/.claude/skills/implement/SKILL.md` (for context on what the skill already covers)

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/dispatch-pattern.md` (modified)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- This is a definition, not a prohibition. The framing matters: "here's how to classify your impulse" rather than "here's another thing you must not do."
- Keep it under 30 lines. The power is in the litmus test and the concrete lists, not in length.
