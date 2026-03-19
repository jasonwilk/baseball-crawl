# E-131: Jersey Number as Distinct Dashboard Column

## Status
`READY`

## Overview
Display player jersey number as its own column in every dashboard stat table, separated from the player name. Currently jersey number is either inlined with the name (`#23 Smith`) or absent entirely on some views. After this epic, every stat table shows a dedicated `#` column as the first column, with consistent formatting and NULL handling across all views.

## Background & Context
Coaches identify players by number first, name second -- "number 23 up to bat" is the mental model. The current inline treatment buries the number inside the name cell, making it harder to scan rosters at a glance. Some views (game detail, opponent scouting) don't show jersey number at all.

The data layer already supports this: `team_rosters.jersey_number TEXT` exists in the schema, and the data flows through two distinct ingestion mechanisms:

1. **Member teams (authenticated roster crawler)**: `RosterLoader` reads `roster.json` fetched from `/teams/{team_id}/players`. Maps the API `"number"` field to `team_rosters.jersey_number` via `_ROSTER_FIELD_MAP`. Source: `src/gamechanger/loaders/roster.py`.
2. **Opponent/tracked teams (scouting pipeline)**: `ScoutingLoader._load_roster()` reads `roster.json` fetched from `/teams/public/{public_id}/players`. Extracts `player.get("number")` and writes it to `team_rosters.jersey_number`. Source: `src/gamechanger/loaders/scouting_loader.py`.

Both paths write to the same `team_rosters` table with the same column. The query layer and templates consume `team_rosters.jersey_number` identically regardless of which path populated it. The season stats queries already JOIN `team_rosters` to fetch it. The gaps are purely in the query layer (two functions missing the JOIN) and the UI templates (four templates need the column extracted or added).

All stories and ACs must work correctly for both member-team data (roster-loaded) and opponent-team data (scouting-loaded).

**Expert consultation completed:**
- **DE**: Confirmed no schema migration or ETL changes needed. Flagged three gotchas: (1) box score queries need `season_id` to JOIN `team_rosters`, (2) LEFT JOIN mandatory everywhere due to nullable roster data, (3) avoid N+1 per-player lookups.
- **SE**: Confirmed gap analysis is complete. Identified the cleanest JOIN approach for `get_game_box_score` (pass `season_id` from game row). Flagged test files and specific test patterns needed.
- **UXD**: Specified column design: `#` header, first column before Player, `w-8 text-center`, em dash for NULL, colspan increments for all empty-state rows.

## Goals
- Jersey number appears as a dedicated `#` column (first column) in all four stat table views
- Consistent NULL handling (em dash) across all tables
- No player rows lost due to missing roster data (LEFT JOIN everywhere)

## Non-Goals
- No schema migration (column already exists)
- No ingestion/ETL changes (data already flows)
- No changes to player profile page (inline header treatment is already appropriate for detail pages)
- No changes to game list or opponent list views (no per-player rows)

## Success Criteria
- All four stat tables (team batting, team pitching, game detail, opponent scouting) show a `#` column as the first column with jersey number data
- Players without jersey numbers show `—` (em dash), not blank cells
- No existing player rows disappear from any view (LEFT JOIN correctness)
- Jersey number displays correctly for both member teams (roster-loaded data) and opponent teams (scouting-loaded data)
- All existing tests pass; new tests cover jersey number in box score and scouting queries, including test scenarios for both member and opponent team data paths

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-131-01 | Season stats jersey number column | TODO | None | - |
| E-131-02 | Game box score jersey number column | TODO | None | - |
| E-131-03 | Opponent scouting jersey number column | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Column Design Spec (from UXD)
All four tables use the same column pattern:
- **Header**: `<th class="py-2 px-2 text-center w-8">#</th>` -- first column, before Player
- **Cell**: `<td class="py-2 px-2 text-center">{% if player.jersey_number %}{{ player.jersey_number }}{% else %}&mdash;{% endif %}</td>`
- **Empty-state rows**: Increment `colspan` by 1 on every "No data" `<tr>` row in the affected table. Note: only `team_stats.html` and `team_pitching.html` (E-131-01) use `<tr colspan>` empty states. `game_detail.html` and `opponent_detail.html` use `<p>` paragraph empty states — no colspan change needed for E-131-02 or E-131-03.

### TN-2: LEFT JOIN Requirement (from DE)
All `team_rosters` JOINs must be `LEFT JOIN`. Jersey number is nullable, and opponent players may not have roster rows at all (scouting pipeline may not have run). An INNER JOIN would silently drop player rows.

### TN-3: Box Score season_id Resolution (from DE + SE)
`get_game_box_score()` fetches the game row first, then executes separate batting/pitching queries. The `games` table has a `season_id` column, but the current `game_query` does NOT SELECT it — this must be added. Once `season_id` is available from the game row, pass it as a parameter to the batting/pitching queries and add `LEFT JOIN team_rosters tr ON tr.player_id = pgb.player_id AND tr.team_id = pgb.team_id AND tr.season_id = ?`.

### TN-4: Test Patterns (from SE) -- Applies to ALL Stories
Every story in this epic must test both ingestion paths. The query layer and templates do not distinguish between member and tracked team data, so tests must verify correct behavior for both:
1. Insert a `team_rosters` row with a known jersey number and assert it appears in results
2. Include a test where the roster row is absent -- assert `jersey_number` is `None`, not missing key or crash
3. **Dual-path coverage (mandatory for all stories)**: Set up test data for both a `membership_type='member'` team (simulating roster-loaded data) and a `membership_type='tracked'` team (simulating scouting-loaded data). Verify jersey number resolves correctly for both. For season stats (E-131-01), test both team types through the same template. For box scores (E-131-02), both teams appear in the same query. For scouting reports (E-131-03), test with both tracked and member team_ids since the query is team_id-based.

### TN-5: Dual Ingestion Path Context
Jersey number data reaches `team_rosters.jersey_number` via two mechanisms:
- **Member teams**: `RosterLoader` (`src/gamechanger/loaders/roster.py`) processes `/teams/{team_id}/players` API responses. Writes `jersey_number` from the `"number"` field.
- **Opponent teams**: `ScoutingLoader._load_roster()` (`src/gamechanger/loaders/scouting_loader.py`) processes `/teams/public/{public_id}/players` responses. Writes `jersey_number` from `player.get("number")`.

Both paths write to the same `team_rosters` table. The query layer does not and should not distinguish between them -- a `LEFT JOIN team_rosters` returns `jersey_number` regardless of which loader wrote it. The key testing implication: tests should set up roster data for both a `membership_type='member'` team and a `membership_type='tracked'` team to confirm the JOIN works for both.

### TN-6: Shared File Parallel Safety
All three stories modify `tests/test_dashboard.py`. E-131-02 and E-131-03 both modify `src/api/db.py` and `tests/test_db.py`. Per the parallel execution rule, stories that modify the same file normally require a dependency. These stories are an **acknowledged exception**: each modifies distinct, non-overlapping functions within the shared files (`get_game_box_score` vs `get_opponent_scouting_report`, separate test functions). Git auto-merge handles non-overlapping hunks in the same file cleanly. If merge conflicts arise during merge-back, the main session resolves them sequentially — the last story merged adapts to the prior merges.

## Open Questions
None.

## History
- 2026-03-19: Created. Expert consultation with DE, SE, and UXD completed. Set to READY.
- 2026-03-19: Refined per user feedback (round 1). Added dual ingestion path documentation (TN-5) covering member-team (RosterLoader) and opponent-team (ScoutingLoader) data paths. Updated ACs in E-131-02 and E-131-03 to require test coverage for both ingestion paths. Renumbered colspan ACs.
- 2026-03-19: Refined per user feedback (round 2). Extended dual-path test coverage requirement to ALL stories, not just E-131-02/03. E-131-01 gained new ACs (AC-5, AC-6, AC-7) for dual-path rendering tests and NULL handling verification, plus `tests/test_dashboard.py` added to its files list. TN-4 header updated to "Applies to ALL Stories" with mandatory dual-path coverage for every story. E-131-02 AC-7 and E-131-03 AC-7 strengthened to explicitly name both membership_type values.
- 2026-03-19: Codex spec review triage (5 findings, all valid, all fixed). (1-2) Removed impossible colspan ACs from E-131-02 and E-131-03 — those templates use `<p>` empty states, not `<tr colspan>`. Replaced with template rendering test ACs. Updated TN-1 to clarify colspan scope. (3-4) Added `tests/test_dashboard.py` to Files lists for E-131-02 and E-131-03 to cover template rendering ACs. (5) Fixed TN-3 and E-131-02 Context to note that `game_query` does NOT currently SELECT `g.season_id` — story must extend it.
- 2026-03-19: Final quality sweep. Added TN-6 documenting shared file parallel safety — all three stories modify `tests/test_dashboard.py`, E-131-02 and E-131-03 share `src/api/db.py` and `tests/test_db.py`. Acknowledged as exception to the dependency rule since changes target non-overlapping functions. No other issues found. Status remains READY.
