# E-139-01: Remove Backfill Script and CLI Command

## Epic
[E-139: Remove Backfill Script](epic.md)

## Status
`DONE`

## Description
After this story is complete, the one-time backfill script, its CLI registration, its tests, and the related remediation log will be removed from the codebase. The full test suite will pass without regressions.

## Context
E-132 added a `bb data backfill-team-names` command to retroactively fix 155 opponent rows that had UUIDs as names. The backfill ran once and succeeded. The loaders now handle name resolution at insert time with self-healing on reload, so the backfill code is dead weight.

## Acceptance Criteria
- [ ] **AC-1**: `src/gamechanger/loaders/backfill.py` is deleted
- [ ] **AC-2**: The `backfill-team-names` command and its import block are removed from `src/cli/data.py` (no other commands in that file are affected)
- [ ] **AC-3**: `tests/test_backfill.py` is deleted
- [ ] **AC-4**: `.project/research/codex-review-2026-03-19-remediation.md` is deleted
- [ ] **AC-5**: `bb data --help` does not list `backfill-team-names`
- [ ] **AC-6**: Full test suite passes (`pytest`) with no regressions

## Technical Approach
Four files to delete and one file to edit. The CLI registration in `src/cli/data.py` includes the command function and its imports from backfill -- remove the entire command block without affecting adjacent commands.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/backfill.py` (delete)
- `src/cli/data.py` (edit -- remove `backfill-team-names` command and imports)
- `tests/test_backfill.py` (delete)
- `.project/research/codex-review-2026-03-19-remediation.md` (delete)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
