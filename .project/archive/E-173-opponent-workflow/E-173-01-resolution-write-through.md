# E-173-01: Resolution Write-Through to team_opponents

## Epic
[E-173: Fix Opponent Scouting Workflow End-to-End](epic.md)

## Status
`DONE`

## Description
After this story is complete, resolving an opponent (via search, manual connect, or auto-resolver) atomically propagates `resolved_team_id` to `team_opponents`, activates the resolved team, and reassigns FK references from the old stub to the resolved team. A shared `finalize_opponent_resolution()` function encapsulates the write-through logic and is called from all three resolution paths.

## Context
The root cause of the broken scouting workflow is that resolving an opponent updates `opponent_links.resolved_team_id` but never touches `team_opponents` (the junction table the dashboard queries) or `teams.is_active`. Stats load into the resolved team's ID, but the dashboard shows the stub team created by the schedule loader -- a different row with no stats. This story fixes the data disconnect by making resolution a write-through operation that propagates to all dependent tables.

## Acceptance Criteria
- [ ] **AC-1**: A shared function `finalize_opponent_resolution(conn, our_team_id, resolved_team_id, opponent_name, first_seen_year)` exists in `src/api/db.py`. It performs five operations atomically per TN-1: (a) discovers the old stub team via the `_find_tracked_stub()` pattern using `opponent_name`, (b) upserts a `team_opponents` row linking `our_team_id` to `resolved_team_id`, (c) sets `teams.is_active = 1` on the resolved team, (d) reassigns all FK references from the old stub to the resolved team when a stub is discovered, and (e) returns a dict with `resolved_team_id`, `public_id`, and `old_stub_team_id`.
- [ ] **AC-2**: The search resolve handler (`resolve_opponent_confirm` in admin.py) calls `finalize_opponent_resolution()` after setting `opponent_links.resolved_team_id`. The dashboard shows scouting stats for the resolved opponent after this handler completes.
- [ ] **AC-3**: The manual connect handler (`save_manual_opponent_link` in db.py) calls `finalize_opponent_resolution()` inside its existing transaction (before `conn.commit()`). The dashboard shows scouting stats for the connected opponent after this handler completes.
- [ ] **AC-4**: When `team_opponents` already has a row for `(our_team_id, resolved_team_id)` (e.g., from a previous resolution attempt or manual entry), the function does not raise a UNIQUE constraint error. It handles this by deleting the old stub row (if one exists and differs from the resolved team) rather than inserting a duplicate.
- [ ] **AC-5**: The resolved team's `is_active` flag is set to `1` regardless of its prior state. This ensures the team appears in dashboard queries and is eligible for scouting.
- [ ] **AC-6**: The function discovers the old stub internally by querying `team_opponents JOIN teams` for a tracked team matching `(our_team_id, opponent_name)` using the same pattern as the existing `_find_tracked_stub()` function. Callers do not need to determine or pass the old stub team ID.
- [ ] **AC-7**: The function runs within the caller's existing database transaction. It does not open its own connection or commit. For the manual connect path (`save_manual_opponent_link`), the function is called inside that function's existing transaction before `conn.commit()`.
- [ ] **AC-8**: The auto-resolver (`OpponentResolver.resolve()` in `opponent_resolver.py`) calls `finalize_opponent_resolution()` after setting `opponent_links.resolved_team_id`, so that automatic resolution during `run_member_sync` also propagates to the dashboard.
- [ ] **AC-9**: When an old stub is discovered and differs from `resolved_team_id`, the function reassigns all FK references from the stub to the resolved team: `games.home_team_id`/`away_team_id`, `player_game_batting.team_id`, `player_game_pitching.team_id`, `player_season_batting.team_id`, `player_season_pitching.team_id`, `spray_charts.team_id`, `team_rosters.team_id`. The dedup guard skips rows where the resolved team already has a matching record (e.g., same `game_stream_id` in games, same `player_id + game_id` in per-game stats) to avoid duplicate constraint violations.
- [ ] **AC-10**: Tests verify: (a) resolution creates `team_opponents` row and sets `is_active=1`, (b) resolution with existing stub updates the row to point to resolved team, (c) resolution with no stub creates a new row, (d) UNIQUE constraint is not violated when resolved team already has a `team_opponents` row, (e) FK references are reassigned from stub to resolved team, (f) dedup guard prevents duplicate rows when resolved team already has matching data.

## Technical Approach
The shared function belongs in `src/api/db.py` alongside the existing `_find_tracked_stub()` and resolution functions. The stub discovery uses the same query pattern as `_find_tracked_stub()` (line 1225-1248): join `team_opponents` with `teams` on `opponent_team_id`, filter by `our_team_id` and `opponent_name` match, restrict to `membership_type='tracked'`. The FK reassignment follows the same table list as `src/db/merge.py` (lines 694-758) which handles the full team merge operation. The function should be called after the caller has already updated `opponent_links` but before the transaction commits, so all changes are atomic.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-173-02, E-173-03, E-173-04, E-173-06

## Files to Create or Modify
- `src/api/db.py` -- add `finalize_opponent_resolution()` function
- `src/api/routes/admin.py` -- call `finalize_opponent_resolution()` from `resolve_opponent_confirm`
- `src/gamechanger/crawlers/opponent_resolver.py` -- call `finalize_opponent_resolution()` from `OpponentResolver.resolve()`
- `tests/test_admin_resolve.py` -- test write-through for search resolve path
- `tests/test_admin_connect.py` -- test write-through for manual connect path
- `tests/test_crawlers/test_opponent_resolver.py` -- test write-through for auto-resolver path

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `first_seen_year` parameter should be derived from the member team's `teams.season_year` (the team identified by `our_team_id`), with a fallback to the current calendar year if NULL.
- FK reassignment is global (not scoped to `our_team_id`), matching the convention in `src/db/merge.py`. If team 27 (stub) has game rows from multiple member teams' schedules, all are reassigned to team 44 (resolved). This is correct because the stub and resolved team represent the same real-world team.
- Pre-existing duplicate game rows (same `game_stream_id` on both stub and resolved team) are possible if a game was loaded for both teams independently. The dedup guard in AC-9 handles this by skipping rows where the resolved team already has a matching record.
