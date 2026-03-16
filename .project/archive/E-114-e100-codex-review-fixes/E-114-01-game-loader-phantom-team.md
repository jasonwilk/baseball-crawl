# E-114-01: Fix Game Loader Phantom Team Row on gc_uuid=None

## Epic
[E-114: E-100 Codex Review Fixes](epic.md)

## Status
`DONE`

## Description
After this story is complete, the game loader uses `self._team_ref.id` directly for the own team's INTEGER PK instead of resolving through `_ensure_team_row(gc_uuid or "")`, eliminating the phantom team row created when `gc_uuid` is None.

## Context
When the game loader processes boxscores for a tracked opponent whose bridge returned 403, `self._team_ref.gc_uuid` is None. The current code passes `gc_uuid or ""` (empty string) to `_ensure_team_row`, which creates a team row with `gc_uuid=""` and `name=""`. All boxscore stats are written against this phantom row instead of the real team. This is a P1 data corruption bug triggered by a common scouting scenario.

## Acceptance Criteria
- [ ] **AC-1**: `_resolve_team_ids()` uses `self._team_ref.id` directly for the own team's INTEGER PK. It does NOT call `_ensure_team_row` for the own team. `_ensure_team_row` is still used for the opponent team (which may need row creation).
- [ ] **AC-2**: The boxscore key identification logic (the `gc_uuid or ""` usage for matching own team's key in the boxscore response) handles `gc_uuid=None` without creating phantom data or failing silently. The implementer determines the right approach based on how boxscore keys work.
- [ ] **AC-3**: A test exists that constructs a `GameLoader` with `TeamRef(id=N, gc_uuid=None, public_id="some-slug")` (the scouting path), processes a boxscore, and verifies: (a) no phantom team row with `gc_uuid=""` is created, (b) stats are written against the correct team ID, (c) the opponent team row is created normally via `_ensure_team_row`.
- [ ] **AC-3b**: A test exercises `_detect_team_keys` with a two-UUID-key boxscore (no slug key) when `gc_uuid` is None, verifying it does not match on empty string or create phantom data. This covers the secondary bug at line 530.
- [ ] **AC-4**: Existing game loader tests continue to pass.

## Technical Approach
The own team's INTEGER PK is already known at `GameLoader` construction time via `self._team_ref.id`. The `_resolve_team_ids` call to `_ensure_team_row` for the own team is unnecessary and harmful when `gc_uuid` is None. Replace it with a direct use of `self._team_ref.id`. For the boxscore key identification (line 530 area), examine how keys are structured and whether `gc_uuid` matching is needed when the own team is already identified by other means.

Context files to read:
- `/workspaces/baseball-crawl/src/gamechanger/loaders/game_loader.py` (full file -- understand `_resolve_team_ids`, `_detect_team_keys`, `_ensure_team_row` and their callers)
- `/workspaces/baseball-crawl/tests/test_loaders/test_game_loader.py`

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (modified)
- `tests/test_loaders/test_game_loader.py` (modified -- new test case)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
