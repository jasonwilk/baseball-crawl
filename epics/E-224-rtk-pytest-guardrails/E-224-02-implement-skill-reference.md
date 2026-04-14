# E-224-02: Add `-x` Prohibition Reference to Implement Skill

## Epic
[E-224: RTK/Pytest Interaction Guardrails](epic.md)

## Status
`TODO`

## Description
After this story is complete, the Epic Worktree Constraints section in `.claude/skills/implement/SKILL.md` will include a one-liner referencing the `-x`/`--exitfirst` prohibition. This ensures implementers spawned during dispatch see the constraint in their spawn prompt without duplicating the full rule content.

## Context
The implement skill's worktree constraints section (around line 201-216) already has a "Pytest limitation" note about worktree test behavior. CA recommended adding a reference-only one-liner here rather than duplicating rule content — the rule file (`.claude/rules/pytest-verbose.md`) is the single source of truth, and the skill just needs to surface the prohibition at spawn time.

## Acceptance Criteria
- [ ] **AC-1**: The Epic Worktree Constraints "Prohibited" list in `.claude/skills/implement/SKILL.md` includes a bullet prohibiting `-x`/`--exitfirst` with pytest, with a brief reason (RTK compression hides suite truncation)
- [ ] **AC-2**: The addition is a single bullet point (one or two lines), not a full explanation — the rule file is the authoritative source
- [ ] **AC-3**: The existing Pytest limitation note and all other worktree constraints are preserved unchanged

## Technical Approach
Add one bullet to the "Prohibited" list in the Epic Worktree Constraints section of the implement skill. Keep it brief — the rule file has the full explanation. Place it near the existing Pytest limitation note for proximity.

## Dependencies
- **Blocked by**: E-224-01 (the rule must contain the prohibition before the skill references it)
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Implement skill structure is preserved
- [ ] No regressions to existing worktree constraints
