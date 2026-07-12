# E-256-12: data-model.md dead-by-descope note

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## Description
After this story is complete, `.claude/rules/data-model.md` carries a brief dead-by-descope note recording that the write-orphaned tables `crawl_jobs` and `coaching_assignments`, and the ~100 season split/advanced columns rendered permanently unpopulatable by E-239, are retained deliberately rather than by accident.

## Context
This epic contributes **only** the `data-model.md` note. The corresponding **idea capture is E-255-06 AC-4's job** (the DE-confirmed dead-table set) — do **NOT** double-capture it here. `user_team_access` is **LIVE** (the non-admin team-access grant mechanism) and MUST NOT be swept or noted as dead. See the audit's SOUND_BUT_UNDERDOCUMENTED §3 items 4 and 5.

## Acceptance Criteria
- [ ] **AC-1**: Given `.claude/rules/data-model.md`, when this story is complete, then it contains a note marking `crawl_jobs` and `coaching_assignments` as write-orphaned/retained-by-decision (dead-by-descope), and the ~100 season split/advanced columns as permanently unpopulatable post-E-239.
- [ ] **AC-2**: Given the note, when this story is complete, then it does **not** name `user_team_access` as dead (it is LIVE), and it does **not** duplicate the idea capture that E-255-06 AC-4 owns.

## Technical Approach
A short prose addition to `data-model.md`. Keep it to a sentence or two per the audit's "one data-model.md sentence" prescription. claude-architect owns this file.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/data-model.md`

## Agent Hint
claude-architect

## Handoff Context
None.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Note is accurate (user_team_access not included)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Non-goal reminder: no idea capture here — E-255-06 AC-4 owns the retention idea.
