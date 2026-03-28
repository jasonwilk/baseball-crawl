# E-173-04: Dashboard Opponent Sort and Data Status

## Epic
[E-173: Fix Opponent Scouting Workflow End-to-End](epic.md)

## Status
`TODO`

## Description
After this story is complete, the dashboard opponent list defaults to sorting by next game date (upcoming opponents first) instead of alphabetically, and each opponent row displays a data-availability indicator showing one of three states: stats loaded, syncing, or scoresheet-only.

## Context
Coaches think schedule-first: "who do we play next?" The current alphabetical sort buries upcoming opponents. Additionally, three different opponent situations (stats loaded, sync in progress, no GC profile) all display identically as blank stats ("--"), leaving coaches unsure whether data is missing, loading, or unavailable. This story addresses both coaching needs identified in the baseball-coach consultation and template walkthrough.

## Acceptance Criteria
- [ ] **AC-1**: The dashboard opponent list (`/dashboard/opponents`) defaults to sorting by `next_game_date` ascending (soonest game first). Opponents with no upcoming game sort after those with one (NULL last).
- [ ] **AC-2**: Each opponent row displays a data status indicator per TN-3: green dot for "stats loaded" (has season batting or pitching data), yellow dot for "syncing" (`crawl_jobs` row with `status = 'running'`), gray dash for "scoresheet only" (neither condition met).
- [ ] **AC-3**: On screens wider than the Tailwind `sm:` breakpoint (640px), a short text label appears next to the dot: "Stats", "Syncing", or "Scoresheet".
- [ ] **AC-4**: The opponent name remains a clickable link to the detail page regardless of data state.
- [ ] **AC-5**: The Next/Last column is positioned as the second column (after Opponent name) for mobile readability, per UXD spec. GP and W-L columns follow.
- [ ] **AC-6**: Tests verify that `get_team_opponents()` returns opponents sorted by next_game_date ascending with NULLs last, and that data status is included in each row.

## Technical Approach
The `get_team_opponents()` function in `src/api/db.py` (line 520) currently sorts by `opponent_name ASC`. The sort needs to change to `next_game_date ASC NULLS LAST, opponent_name ASC`. The data status requires a subquery or LEFT JOIN: check `player_season_batting`/`player_season_pitching` for the "stats loaded" state, and `crawl_jobs` for the "syncing" state. The template changes are in `dashboard/opponent_list.html` for column reorder and status dot rendering.

## Dependencies
- **Blocked by**: E-173-01 (correct `opponent_team_id` in `team_opponents` is prerequisite for stats lookup to work)
- **Blocks**: E-173-05

## Files to Create or Modify
- `src/api/db.py` -- modify `get_team_opponents()` to sort by next_game_date, add data_status field per opponent
- `src/api/templates/dashboard/opponent_list.html` -- add status dot column, reorder columns (Next/Last to position 2), responsive labels
- `tests/test_dashboard.py` or `tests/test_api_db.py` -- test sort order and data status derivation

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The "syncing" state check queries `crawl_jobs` for the opponent's `team_id` where `status = 'running'`. The `crawl_jobs` schema (migration 003) uses column `status` with values `'running'`, `'completed'`, `'failed'`.
- The sort change affects only the default; no user-selectable sort toggle is needed for this story.
- NULL `next_game_date` means no upcoming game scheduled -- these opponents sort last but are still shown.
