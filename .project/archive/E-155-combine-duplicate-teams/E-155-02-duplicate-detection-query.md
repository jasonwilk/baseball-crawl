# E-155-02: Duplicate Detection Query

## Epic
[E-155: Combine Duplicate Teams](epic.md)

## Status
`DONE`

## Description
After this story is complete, the system will have a `find_duplicate_teams(db)` function that returns groups of tracked teams with identical names (case-insensitive) within the same season year. This powers the "Potential Duplicates" banner on the admin team list.

## Context
Auto-detection of duplicates is a coaching must-have (per discovery). This story provides the detection query that the admin UI (E-155-03) will use to surface potential duplicates. Per TN-5, detection uses exact case-insensitive name matching among tracked teams with the same `season_year`. Member teams are excluded from auto-detection.

## Acceptance Criteria
- [ ] **AC-1**: A `find_duplicate_teams(db)` function exists in `src/db/merge.py` that returns a list of duplicate groups. Each group contains 2+ team records (id, name, season_year, gc_uuid, public_id, game_count, has_stats) that share the same normalized name and season_year.
- [ ] **AC-2**: Name matching is case-insensitive. "Lincoln East", "lincoln east", and "LINCOLN EAST" are treated as the same name.
- [ ] **AC-3**: Only tracked teams (`membership_type = 'tracked'`) are included in duplicate detection. Member teams are excluded.
- [ ] **AC-4**: Teams with the same name but different `season_year` values are NOT flagged as duplicates. Teams with the same name and both having `season_year IS NULL` ARE flagged as duplicates.
- [ ] **AC-5**: Each team in a duplicate group includes a `game_count` (number of games where the team appears as `home_team_id` or `away_team_id`) and a `has_stats` boolean (true if the team has any rows in `player_season_batting`, `player_season_pitching`, or `scouting_runs`) to help the admin identify which is the canonical team.
- [ ] **AC-6**: When no duplicates exist, the function returns an empty list. Test verifies with uniquely-named teams.

## Technical Approach
A single SQL query groups tracked teams by `LOWER(name)` and `COALESCE(season_year, 0)` (or equivalent NULL handling), filters to groups with `COUNT(*) >= 2`, then fetches full team details for those groups. The game count can be derived via a subquery or LEFT JOIN on `games`. The function lives alongside the merge functions in `src/db/merge.py`.

## Dependencies
- **Blocked by**: E-155-01 (shared file: `src/db/merge.py`)
- **Blocks**: E-155-03

## Files to Create or Modify
- `src/db/merge.py` (modify -- add function)
- `tests/test_merge.py` (modify -- add tests)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-155-03**: The `find_duplicate_teams` function that the admin teams route calls to populate the duplicates banner.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The function should be efficient enough for the expected team count (~50-100 teams). No pagination needed.
- Game count alone is a weak proxy for data richness. A team with 5 game references but 0 boxscores is less valuable as canonical than one with 2 games and full stats. The `has_stats` boolean addresses this by checking for actual stat rows.
