# E-219-03: Cross-Perspective Data Cleanup

## Epic
[E-219: Own-Side-Only Boxscore Loading](epic.md)

## Status
`TODO`

## Description
After this story is complete, all cross-perspective duplicate players and misattributed data will be cleaned up. Team 537 (Blackhawks 14U) has 11 known duplicate players and 1 duplicate game. A global scan will identify and fix any additional affected teams.

## Context
The root cause fix (E-219-01) prevents new cross-perspective duplicates, but existing data contains phantom players and misattributed stats from prior loads. The existing `merge_player_pair()` in `src/db/player_dedup.py` handles the FK reassignment and cleanup atomically. A cleanup script (exposed as a `bb data` CLI subcommand) uses this function to merge known duplicates and scan globally for others. See TN-6 in the epic.

## Acceptance Criteria
- [ ] **AC-1**: A Python cleanup script removes cross-perspective duplicate players. The cleanup uses `merge_player_pair()` from `src/db/player_dedup.py` for safe FK reassignment. The script is exposed as a `bb data` CLI subcommand for operator access.
- [ ] **AC-2**: A test using fixtures that simulate the Team 537 scenario (11 phantom players with `last_name` matches and overlapping `game_id` participation, plus 1 duplicate game) verifies the cleanup tool merges all duplicates and leaves zero phantom players. Live verification against Team 537 is an operational follow-up, not an in-worktree AC.
- [ ] **AC-3**: A global scan runs across ALL teams (not just Team 537) to detect and merge cross-perspective duplicates. The scan identifies phantom players (players with stat rows but no `team_rosters` entry) and matches them to canonical players using: same `last_name`, overlapping `game_id` participation, AND same `team_id` in game stat tables. All three conditions must match to prevent false positives from unrelated players with common last names.
- [ ] **AC-4**: Misattributed spray chart rows from opponent-perspective loads are cleaned up. The scouting spray loader's documented cleanup query (see docstring in `src/gamechanger/loaders/scouting_spray_loader.py`, lines 42-56) is the pattern for identifying rows where `player_id` is not in `team_rosters` for either game team.
- [ ] **AC-5**: Cross-perspective duplicate games (same `game_date` + same unordered `{home_team_id, away_team_id}` but different `game_id`) are detected and merged. The merge reassigns all child rows (`player_game_batting`, `player_game_pitching`, `plays`, `spray_charts`) from the duplicate `game_id` to the canonical one, then deletes the duplicate game row.
- [ ] **AC-6**: The cleanup is idempotent -- running it again produces no changes.
- [ ] **AC-7**: Season aggregates (`player_season_batting`, `player_season_pitching`) are recomputed after merges to reflect consolidated stats.

## Technical Approach
The cleanup needs to identify phantom players (those with stat rows but no roster entry, or those whose UUIDs appear only from cross-perspective loads). The existing `merge_player_pair()` handles the merge atomically. For spray chart cleanup, the pattern from the scouting spray loader docstring identifies misattributed rows. Season aggregate recomputation may require running the scouting loader's `_compute_season_aggregates()` or a targeted re-aggregation. See TN-6 in the epic.

## Dependencies
- **Blocked by**: E-219-01, E-219-02
- **Blocks**: E-219-05

## Files to Create or Modify
- `src/db/cross_perspective_cleanup.py` (cleanup logic -- must live in `src/` per import boundary rule)
- `src/cli/data.py` (new `bb data cleanup-cross-perspective` subcommand)
- `tests/test_cross_perspective_cleanup.py` (test fixtures simulating phantom players, duplicate games, spray misattribution)
- Possibly `src/db/player_dedup.py` (if new detection heuristics are needed beyond existing `find_duplicate_players()`)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The cleanup script should log all merges and deletions for operator visibility.
- This is a one-time cleanup, not a permanent pipeline feature. However, the script should be idempotent so it can be safely re-run.
- The `find_duplicate_players()` function uses roster-based detection which is blind to phantom players (not on any roster). The cleanup may need a different detection approach: find players with stat rows but no roster entry, then match by last_name + team context.
- **Execution context**: The script writes code + tests that can be verified in the worktree. Actual data cleanup runs post-deploy against the production database via `bb data cleanup-cross-perspective`. The story delivers the tool; the operator runs it.
