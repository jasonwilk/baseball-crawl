# E-113-01: Boundary Reminder and Anti-Pattern Consolidation

## Epic
[E-113: Dispatch Boundary Enforcement](epic.md)

## Status
`DONE`

## Description
After this story is complete, the implement skill's Phase 3 Step 5 begins with an inline boundary reminder that names the "quick check" temptation before any procedural content, and the Anti-Patterns section consolidates five scattered boundary-violation items into a single prominent "quick check trap" pattern.

## Context
The main session's boundary violations happen at a specific moment: after receiving a completion report, before acting on it. Phase 3 Step 5 is already a sound numbered sequence (E-108, E-124 established this) -- it does not need rewriting. What is missing is a pattern interrupt at the top of Step 5 that catches the main session before it starts improvising. Additionally, anti-pattern items 1, 3, 9, 12, 13 are all boundary-violation variants with different framings; consolidating them into one named pattern makes the core message unmissable.

## Acceptance Criteria
- [ ] **AC-1**: Phase 3 Step 5 begins with an inline boundary reminder before the existing numbered steps (before current step 1 "Check context-layer-only skip condition"). The reminder names the specific temptation ("if you are about to read source files, run git log, grep, or inspect the implementation -- stop, that is domain work") and redirects to the routing sequence. It is brief (2-3 sentences), direct, not hedging.
- [ ] **AC-2**: The existing numbered steps in Step 5 (1 through 6, plus circuit breaker, gate interaction, and Step 5a merge-back) are preserved intact. No procedural content is removed, reordered, or rewritten. The boundary reminder is added as a preamble, not a replacement.
- [ ] **AC-3**: Anti-pattern items 1, 3, 9, 12, 13 are consolidated into a single anti-pattern item with the "quick check trap" framing. The consolidated item names the rationalization pattern ("too small to route," "I'll just verify this one thing," "quick check"), explains why it fails (quick checks are domain work regardless of size), lists the specific prohibited actions from the original items (creating/modifying/deleting files, verifying ACs, bypassing code-reviewer, absorbing crashed agent work, applying fixes), and states the rule (when something feels too small to route, route it anyway).
- [ ] **AC-4**: The remaining anti-pattern items (currently 2, 4, 5, 6, 7, 8, 10, 11) are preserved with their original content and renumbered sequentially.
- [ ] **AC-5**: The boundary reminder includes a brief cross-reference to the domain-work definition in dispatch-pattern.md (e.g., "see Domain Work During Dispatch in dispatch-pattern.md"). This creates a link between the in-the-moment reminder and the standing definition, without duplicating content.

## Technical Approach
Read the implement skill's Phase 3 Step 5 and Anti-Patterns section. Add a preamble to Step 5. Consolidate anti-pattern items. Preserve all existing procedural content.

Context files to read:
- `/.claude/skills/implement/SKILL.md` (Phase 3 Step 5 starting at "### Step 5: Monitor, review, and verify" and the Anti-Patterns section)
- `/.claude/rules/dispatch-pattern.md` (for the domain-work definition cross-reference target)

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (modified -- Step 5 preamble and Anti-Patterns section)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- The goal is a pattern interrupt, not a rewrite. Step 5 is already sound -- this adds a preamble and consolidates anti-patterns.
- Keep the boundary reminder brief -- 2-3 sentences, not a paragraph. It is a pattern interrupt, not an essay.
- The consolidated anti-pattern should be item 1 (most prominent position) in the renumbered list.
