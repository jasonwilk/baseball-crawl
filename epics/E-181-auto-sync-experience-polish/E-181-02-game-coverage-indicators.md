# E-181-02: Game Coverage Indicators on Dashboard Pages

## Epic
[E-181: Auto-Sync and Experience Polish](epic.md)

## Status
`TODO`

## Description
After this story is complete, opponent dashboard pages (detail and print) show a game coverage indicator that tells coaches what data backs their decisions: "Through [date] ([N] games)". This replaces the need for coaches to guess whether scouting data is current.

## Context
Coach feedback: "Updated Mar 27" tells when the *system* ran. "Through game Mar 25 (5 games)" tells what's *in the data*. Coaches think in games, not sync dates. When preparing for an opponent, the coach needs to know how many recent games they're looking at and how current the data is. The game coverage indicator derives this from the games table rather than the sync timestamp.

## Acceptance Criteria

**Coverage indicator display:**
- [ ] **AC-1**: The opponent detail page shows a game coverage indicator in the format "Through [date] ([N] games)" -- e.g., "Through Mar 25 (5 games)".
- [ ] **AC-2**: The opponent print report page shows the same game coverage indicator.
- [ ] **AC-3**: The date format is absolute: abbreviated month + day (e.g., "Mar 25").
- [ ] **AC-4**: The schedule page does NOT show a game coverage indicator (games have their own dates).

**Edge cases:**
- [ ] **AC-5**: When no games exist for the opponent, the coverage indicator is not displayed (no "Through (0 games)" -- the empty state handles this case).

**Query:**
- [ ] **AC-6**: Game coverage data (most recent game date + game count) is derived from the `games` table per TN-2, not from `teams.last_synced`. The query matches on `home_team_id` or `away_team_id` and filters for completed games (`status = 'final'`).

**Tests:**
- [ ] **AC-7**: Tests verify the coverage indicator appears with correct data on opponent detail.
- [ ] **AC-8**: Tests verify the coverage indicator is absent when no games exist.
- [ ] **AC-9**: No regressions in existing tests.

## Technical Approach
A lightweight query against the `games` table derives MAX(game_date) and COUNT(*) for the opponent team. The `games` table uses `home_team_id` / `away_team_id` (not a single `team_id`), so the query must match on either column and filter for `status = 'final'`. This can be a small helper function or inline query in the dashboard route handlers. The result is passed to the template context for both pages. The template renders the indicator only when games exist. Per TN-2, this covers opponent teams only (member team pages are out of scope).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-181-03 (shared file: `opponent_detail.html`)

## Files to Create or Modify
- `src/api/routes/dashboard.py` -- add game coverage query to opponent detail and print route handlers
- `src/api/templates/dashboard/opponent_detail.html` -- add coverage indicator display
- `src/api/templates/dashboard/opponent_print.html` -- add coverage indicator display
- `tests/test_dashboard.py` -- add tests for coverage indicator presence and absence

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The query uses: `SELECT MAX(game_date), COUNT(*) FROM games WHERE (home_team_id = ? OR away_team_id = ?) AND status = 'final'`. No joins needed.
- "Through Mar 25" is more natural than "As of Mar 25" -- it implies completeness through that date.
- Member team dashboard pages are out of scope for this epic. Game coverage for own teams can be added later if coaches find it useful.
