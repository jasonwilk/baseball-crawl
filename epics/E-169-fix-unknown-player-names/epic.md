# E-169: Fix Unknown Player Names in Scouting Data

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
When the scouting pipeline loads opponent boxscores, players not found in the `players` table are created as stubs with `first_name='Unknown', last_name='Unknown'`. The boxscore JSON already contains a `players` array with real names for every player in the game — this data is loaded into memory but never used. This epic extracts those names during loading and adds a fallback display for any remaining edge cases.

## Background & Context
Team 13 (Pius X Varsity 2026) has 10 "Unknown Unknown" players in season batting stats. All 10 have real names available in cached boxscore files. The root cause is that loaders process the `groups` array (stat lines by player_id) but ignore the sibling `players` array (name lookup table). The stub pattern exists in four loaders, but only `GameLoader` has the boxscore `players` array in scope — the other loaders either delegate to GameLoader or genuinely lack name data.

**Expert consultations completed:**
- **SE**: GameLoader is the only fix point — ScoutingLoader delegates to it. Other loaders (season_stats, spray_chart) lack name data but run after boxscore loading, so players already exist. Recommends conditional UPSERT (`ON CONFLICT DO UPDATE WHERE first_name='Unknown'`) for safe idempotency. Single code change path.
- **DE**: No schema changes required. Conditional UPSERT handles precedence (roster authoritative, boxscore upgrades stubs). Jersey number lives on `team_rosters`, not `players`. No `name_source` column needed.
- **api-scout**: Boxscore `players` array is the best source (game-scoped, complete). Roster endpoint is point-in-time and may miss removed players. Player IDs are stable UUIDs across all endpoints. No additional API calls needed.
- **UXD**: Fallback display for truly unresolvable players: "Player #23" (jersey number) → "Unknown Player" (no jersey). Muted/italic visual treatment (`text-gray-500 italic`). Data layer cascade with `name_unresolved` flag for template styling.

## Goals
- Eliminate "Unknown Unknown" player names from opponent scouting data by extracting names from boxscore `players` array during loading
- Make the fix idempotent so re-running the pipeline backfills existing Unknown rows
- Provide a coach-friendly fallback display for any remaining unresolvable players

## Non-Goals
- Changing the roster loading pipeline (already works correctly for roster-sourced names)
- Adding a `name_source` column or other schema changes (DE confirmed unnecessary)
- Modifying season_stats_loader, spray_chart_loader, or scouting_spray_loader (they lack name data; pipeline ordering handles them)
- Making additional API calls to resolve names (boxscore data is already in memory)
- Backfill script or CLI command (idempotent loader + re-run is sufficient)

## Success Criteria
- Zero "Unknown Unknown" players in opponent scouting data after a pipeline re-run, for any team with cached boxscore files
- Existing real names (roster-sourced) are never overwritten by boxscore-sourced names
- Coaches see "Player #NN" instead of "Unknown Unknown" for any edge-case unresolvable players
- All existing tests continue to pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-169-01 | Extract player names from boxscore data in GameLoader | TODO | None | - |
| E-169-02 | Fallback display for unresolved player names | TODO | E-169-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Boxscore JSON Structure
The boxscore response contains per-team data keyed by team identifier. Each team entry has:
```
{team_key}: {
  "players": [
    {"id": "uuid", "first_name": "Caleb", "last_name": "Davis", "number": "23"},
    ...
  ],
  "groups": [
    {"category": "lineup", "stats": [ ... per-player batting lines ... ]},
    {"category": "pitching", "stats": [ ... per-player pitching lines ... ]}
  ]
}
```
Note: `groups` is an **array** of objects with `category` field (not an object keyed by `"batting"`/`"pitching"`). The category name for batting is `"lineup"`, not `"batting"`. See `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md`.

The `players` array is already loaded into memory in `GameLoader.load_file()` via `team_data = raw.get(team_key)`. Currently only `team_data.get("groups")` is used; `team_data["players"]` is ignored.

### Conditional UPSERT Pattern
The fix uses a conditional UPSERT that only upgrades names from stubs, never overwrites real names. The `players` table schema is: `player_id TEXT PK, first_name TEXT NOT NULL, last_name TEXT NOT NULL, bats, throws, gc_athlete_profile_id, created_at`. There is no `team_id` column on `players`.

```sql
INSERT INTO players (player_id, first_name, last_name)
VALUES (?, ?, ?)
ON CONFLICT(player_id) DO UPDATE
SET first_name = excluded.first_name, last_name = excluded.last_name
WHERE players.first_name = 'Unknown' AND players.last_name = 'Unknown'
```
This ensures:
- New players: inserted with real names
- Existing stubs: upgraded to real names
- Existing real names (roster-sourced): left untouched

### Jersey Number Backfill
The boxscore `players` array includes `number` (jersey number). Jersey number lives on `team_rosters.jersey_number`, not on `players`. The `team_rosters` PK is `(team_id, player_id, season_id)`.

When extracting names, also upsert `team_rosters` with the jersey number. Behavior: conditional UPSERT — create a new roster row if none exists, or backfill `jersey_number` on an existing row only when the current value is NULL. This covers the case where the roster loader created the row but didn't have the jersey number. `position` is left NULL on boxscore-sourced rows; existing `position` values are never overwritten.

```sql
INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number)
VALUES (?, ?, ?, ?)
ON CONFLICT(team_id, player_id, season_id) DO UPDATE
SET jersey_number = excluded.jersey_number
WHERE team_rosters.jersey_number IS NULL
```

The `season_id` is available via `self._season_id` on the GameLoader instance (set at construction). The `team_id` is passed as a parameter to `_load_team_stats()`.

### Name Resolution Precedence
1. Roster data (authoritative — unconditional upsert in roster loader)
2. Boxscore `players` array (upgrades stubs only — conditional UPSERT)
3. Stub fallback ("Unknown Unknown" — last resort)

### Fallback Display Cascade
For display purposes, unresolved players use this cascade:
1. Real name available → display normally
2. Name unresolved, jersey number available → "Player #NN"
3. Name unresolved, no jersey number → "Unknown Player"

Visual treatment: `text-gray-500 italic` (drop `font-medium`) for HTML surfaces. Print view (`opponent_print.html`) uses inline styles, not Tailwind — use `color: #6b7280; font-style: italic` or equivalent.

Affected surfaces (explicit enumeration):
- **Opponent detail page** (`src/api/templates/dashboard/opponent_detail.html`): season batting table, season pitching table, top pitchers card
- **Opponent print view** (`src/api/templates/dashboard/opponent_print.html`): print batting/pitching tables AND Batter Tendencies cards (line 334 renders `player.name`)
- **Game detail page** (`src/api/templates/dashboard/game_detail.html`): per-game boxscore batting/pitching lines

**Not in scope**: Player profile page (`player_profile.html`) — requires `team_rosters` entry on a permitted team (user's teams). Opponent players (the "Unknown Unknown" population) fail this auth check and cannot reach the player profile page. Spray chart modal — renders images only, no player name text.

**Top pitchers card exception**: The top pitchers card already renders `#{{ pitcher.jersey_number }}` as a prefix before the name. When the name is unresolved and jersey number is available, display ONLY the jersey number (e.g., `#23`) — do NOT display "Player #23" (which would be redundant with the prefix). When neither name nor jersey number is available, display "Unknown Player".

Note: spray chart PNG images (`src/charts/spray.py`) do NOT render player names — `render_spray_chart()` takes `(events, title)` only. No chart renderer changes needed.

### Display Data Source
Both the batting and pitching queries in `src/api/db.py` (`get_opponent_scouting_report()`, lines 636-691) construct `name` as `p.first_name || ' ' || p.last_name` in SQL. Both queries already LEFT JOIN `team_rosters` and return `jersey_number`. The fallback cascade can be applied either in the SQL (CASE WHEN) or as post-processing of the query results.

### Loader Scope
Only `GameLoader` (`src/gamechanger/loaders/game_loader.py`) needs code changes. The other loaders:
- **ScoutingLoader**: Delegates boxscore loading to `GameLoader.load_file()` — gets the fix for free
- **season_stats_loader**: `stats.json` has no player names; runs after boxscore loading so players already exist
- **spray_chart_loader** / **scouting_spray_loader**: No boxscore data; runs after boxscore loading so players already exist

## Open Questions
None — all questions resolved during expert consultation.

## History
- 2026-03-27: Created. Expert consultations with SE, DE, api-scout, UXD completed.
- 2026-03-28: Set to READY after 5 review passes (32 findings, 26 accepted, 2 dismissed).

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 6 | 6 | 0 |
| Internal iteration 1 — Holistic team | 16 | 11 | 1 |
| Codex iteration 1 | 5 | 4 | 1 |
| Codex iteration 2 | 3 | 3 | 0 |
| Codex iteration 3 | 2 | 2 | 0 |
| **Total** | **32** | **26** | **2** |
