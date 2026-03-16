# E-116-01: Fix YAML Load Path TeamRef(id=0) Regression

## Epic
[E-116: E-100 Codex Review Bug Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb data load --source yaml` will correctly resolve each team's `internal_id` from the database before constructing `TeamRef`, eliminating the FK violation that currently causes all own-team player stat INSERTs to fail.

## Context
E-100-03 AC-4 specified that `load_config()` (YAML path) populates `internal_id` via a DB lookup. The `load_config()` function itself does this when given a `db_path` — but the call site in `src/pipeline/load.py` omits `db_path` when `--source yaml`, so `internal_id` stays `None` and `TeamRef(id=0)` is constructed downstream.

## Acceptance Criteria
- [ ] **AC-1**: `_run_game_loader()` in `src/pipeline/load.py` passes `db_path` to `load_config()` so that `TeamEntry.internal_id` is resolved from the database even when `--source yaml`.
- [ ] **AC-2**: When `internal_id` cannot be resolved (team not in DB), the code raises a clear error rather than defaulting to `id=0`. The error message should identify which team (by name or gc_uuid) could not be found.
- [ ] **AC-3**: A test verifies that `_run_game_loader()` with YAML-sourced config produces a `TeamRef` with a valid (non-zero) `id` that corresponds to a `teams.id` row.
- [ ] **AC-4**: A test verifies that when a YAML-configured team is not found in the database, an appropriate error is raised (not a silent `id=0`).
- [ ] **AC-5**: All existing tests pass.

## Technical Approach
The root cause and fix are described in the epic Technical Notes "YAML Load Path Bug" section. The call site in `src/pipeline/load.py` needs to pass `db_path` to `load_config()`. Additionally, the `TeamRef(id=team.internal_id or 0, ...)` fallback should be replaced with an explicit error when `internal_id` is `None`.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/pipeline/load.py`
- `tests/test_scripts/test_load_orchestrator.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- SE investigation confirmed: `load_config()` already supports `db_path` parameter — it's just not being passed at the call site.
- The `or 0` fallback is a silent failure pattern that should be replaced with an explicit error.
