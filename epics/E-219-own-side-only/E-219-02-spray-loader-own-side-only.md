# E-219-02: Spray Chart Loader Own-Side-Only

## Epic
[E-219: Own-Side-Only Boxscore Loading](epic.md)

## Status
`TODO`

## Description
After this story is complete, the member-team spray chart loader (`SprayChartLoader`) will only insert spray events for players on the crawling team's roster. Opponent player events (with perspective-specific UUIDs) will be skipped. This aligns the member spray loader with the scouting spray loader, which already skips unresolvable players.

## Context
The spray endpoint returns BOTH teams' data when called with the owning team's UUID. The member spray loader currently iterates all players in the `offense` and `defense` sections, creating stub player rows and spray events for opponent players whose UUIDs are perspective-specific. The scouting spray loader (`scouting_spray_loader.py`) already handles this correctly by skipping unresolvable players. See TN-5 in the epic for the full SE assessment.

The plays loader does NOT need a code change -- whole-game idempotency prevents double-loading, and phantom stubs are benign (see TN-4).

## Acceptance Criteria
- [ ] **AC-1**: Given a spray chart JSON containing both own-team and opponent-team player events, when `SprayChartLoader._load_game_file()` processes the file, then only events for players whose resolved `team_id` matches the crawling team's ID are inserted. Opponent player events are skipped.
- [ ] **AC-2**: Given an opponent player UUID in the spray chart response, when the loader resolves the player's team, then no `players` stub row and no `spray_charts` row is created for that opponent UUID.
- [ ] **AC-3**: Given the crawling team has players in both `offense` and `defense` sections, when the loader processes the file, then events for those own-team players are inserted normally (no false filtering).
- [ ] **AC-4**: A new test verifies that opponent player events are skipped (zero spray rows for opponent player UUIDs) while own-team events are inserted.
- [ ] **AC-5**: Existing tests in `tests/test_loaders/test_spray_chart_loader.py` are updated to reflect own-side-only behavior. Tests in `tests/test_scouting_spray_loader.py` continue to pass without modification (the scouting spray loader is not changed).

## Technical Approach
The fix is in `src/gamechanger/loaders/spray_chart_loader.py`, method `_load_game_file()`. The `crawling_team_id` is already resolved (line 88/150). After `_resolve_player_team_id()` returns a `team_id`, skip the player if `team_id != crawling_team_id`. This is more precise than the scouting spray loader's approach (which skips players not in `team_rosters`) because it also skips opponent players who happen to be in `team_rosters` from a prior scouting crawl. See TN-5 in the epic.

## Dependencies
- **Blocked by**: E-219-01
- **Blocks**: E-219-03, E-219-05

## Files to Create or Modify
- `src/gamechanger/loaders/spray_chart_loader.py`
- `tests/test_loaders/test_spray_chart_loader.py` (update existing tests; add own-side-only verification)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The scouting spray loader (`scouting_spray_loader.py`) is already correct and should not be modified.
- The plays loader does not need a code change per the SE assessment (TN-4). Document this decision in the context-layer rule (E-219-04).
