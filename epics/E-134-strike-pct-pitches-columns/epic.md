# E-134: Add Strike % and # Pitches to Pitching Displays

## Status
`READY`

## Overview
Add two pitching stats -- **Strike %** (total_strikes / pitches × 100) and **# Pitches** -- to all pitching display surfaces in the coaching dashboard. Both columns already exist in the database and are populated by all ingestion paths; this epic surfaces them in the UI.

## Background & Context
Coaches want to see pitch efficiency (Strike %) and total pitch count alongside the existing pitching rate stats (ERA, K/9, BB/9, WHIP). The data already flows through every ingestion method (game loader, season stats loader, scouting loader) into `player_season_pitching.pitches`, `player_season_pitching.total_strikes`, `player_game_pitching.pitches`, and `player_game_pitching.total_strikes`. The queries and templates simply don't select or render these columns yet.

No expert consultation required -- this is a pure display-layer change using existing populated schema columns.

## Goals
- Strike % and # Pitches visible on all pitching display surfaces in the coaching dashboard
- Consistent formatting across all surfaces (Strike % as percentage with one decimal, pitches as integer)

## Non-Goals
- Schema or migration changes (columns already exist and are populated)
- ETL/loader changes (data already flows correctly)
- Batting stats changes (pitches seen from the batter's perspective is a separate concern)
- Scouting key player card changes (already shows avg_pitches -- leave as-is)

## Success Criteria
- All 5 pitching display surfaces show Strike % and # Pitches columns
- Strike % displays as "-" when pitches is 0 or NULL (division guard)
- Existing tests continue to pass; new tests cover the added columns

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-134-01 | Add Strike % and # Pitches to all pitching display surfaces | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Display Surfaces (5 total)

All pitching tables in the dashboard need Strike % and # Pitches columns added:

1. **Team Pitching page** (`src/api/templates/dashboard/team_pitching.html`)
   - Query: `get_team_pitching_stats()` in `src/api/db.py` (line ~172)
   - Rate computation: `_compute_pitching_rates()` in `src/api/routes/dashboard.py` (line ~166)
   - Currently missing: `pitches` and `total_strikes` not in SELECT

2. **Opponent Scouting pitching table** (`src/api/templates/dashboard/opponent_detail.html`)
   - Query: scouting report pitching query in `get_opponent_scouting_report()` in `src/api/db.py` (line ~517)
   - Rate computation: `_compute_opponent_pitching_rates()` in `src/api/routes/dashboard.py` (line ~433)
   - Currently: `pitches` is already in SELECT; `total_strikes` is missing

3. **Game Box Score pitching lines** (`src/api/templates/dashboard/game_detail.html`)
   - Query: pitching query in `get_game_box_score()` in `src/api/db.py` (line ~325)
   - No rate computation function exists for game box score pitching -- create a new `_compute_game_pitching_rates()` helper for consistency with the other three surfaces
   - Currently missing: `pitches` and `total_strikes` not in SELECT

4. **Player Profile pitching-by-season table** (`src/api/templates/dashboard/player_profile.html`)
   - Query: pitching query in `get_player_profile()` in `src/api/db.py` (line ~669)
   - Rate computation: `_compute_player_pitching_rates()` in `src/api/routes/dashboard.py` (line ~842)
   - Currently missing: `pitches` and `total_strikes` not in SELECT

5. **Player Profile current season summary card** (`src/api/templates/dashboard/player_profile.html`)
   - Uses data from the same query as surface 4
   - Template section at line ~56

### Column Definitions

- **# Pitches** (`pitches`): Total pitches thrown. Integer display. Source: `pitches` column in `player_season_pitching` (season views) or `player_game_pitching` (game box score).
- **Strike %** (`strike_pct`): Computed as `total_strikes / pitches × 100`. Display as one decimal (e.g., "63.2%"). When `pitches` is 0 or NULL, display "-". Use the existing `or 0` coercion pattern (e.g., `pitches = row.get("pitches") or 0`) to handle both cases uniformly.

### Column Placement

Place `#P` and `Strike %` after the `SO` column on season/scouting tables, and after `SO` on the game box score table. This groups pitch-efficiency stats together visually.

### Implementation Notes

- **Colspan update**: `team_pitching.html` has a `<td colspan="12">` for the "No pitching stats available" empty state. After adding 2 columns, update to `colspan="14"`. Check other templates for similar colspan values.
- **NULL handling**: The `pitches` and `total_strikes` columns are nullable in the schema. The season stats loader writes non-null values, but seed/fixture data may contain NULLs. All compute functions must use the established `or 0` coercion pattern.
- **Testing**: AC-8 tests should be unit tests calling the compute functions directly with crafted input dicts -- not route-level integration tests. Test both normal case and NULL/zero-pitches guard. New fixture data with explicit non-null pitches/total_strikes values is needed (seed.sql has NULLs for these columns).

## Open Questions
None.

## History
- 2026-03-19: Created
- 2026-03-19: Holistic refinement with SE, DE, UXD, api-scout. Changes: (1) AC-6 expanded to cover NULL pitches, not just 0 -- DE identified nullable schema columns with inconsistent loader defaults; (2) game box score helper function guidance added to Technical Notes -- SE recommended for consistency and testability; (3) colspan update note added -- UXD identified stale colspan="12" in team_pitching.html empty state; (4) AC-8 refined to specify unit tests on compute functions with crafted dicts; (5) api-scout confirmed `TS` field IS present in season-stats defense object despite API spec documentation gap -- no scope change needed.
