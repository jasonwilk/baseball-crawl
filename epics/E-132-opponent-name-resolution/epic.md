# E-132: Fix Opponent Names Showing as UUIDs on Player Detail Page

## Status
`READY`

## Overview
The player detail page (`/dashboard/players/{player_id}`) shows game UUIDs instead of opponent team names in the "Recent Games" section. The root cause is `GameLoader._ensure_team_row()`, which creates opponent team rows with `name = gc_uuid` because the boxscore response contains no team name metadata. The fix uses opponent names already available on disk: `opponents.json` (authenticated path) and `games.json` (scouting path).

## Background & Context
When `_ensure_team_row()` creates a new `teams` row for an opponent, it sets `name = gc_uuid` (the UUID string) because the boxscore API response has no opponent name field. The query layer and template are correct -- they display `teams.name`, which is just a UUID right now.

Three data sources already have opponent names on disk:
- **`opponents.json`** (authenticated path, primary): `data/raw/{season}/teams/{team_id}/opponents.json` contains `name` + `progenitor_team_id` for each opponent. Crawled by `OpponentCrawler`. Co-located with `game_summaries.json`. Only exists for member teams.
- **`schedule.json`** (authenticated path, supplementary): `data/raw/{season}/teams/{team_id}/schedule.json` contains `pregame_data.opponent_name` and `pregame_data.opponent_id`. Crawled by `ScheduleCrawler`. Also co-located.
- **`games.json`** (scouting path): `data/raw/{season}/scouting/{public_id}/games.json` contains `opponent_team.name` for every game. Crawled by `ScoutingCrawler`. Only source available for the scouting pipeline.

The `opponent_resolver` (lines 373-382) already has logic to fix UUID-stub names, but only runs for explicitly resolved opponents. This epic does not duplicate that logic -- it ensures names are correct at insert time.

No expert consultation required -- this is a loader bug fix using data sources already crawled and documented.

## Goals
- Opponent team names display correctly on the player detail page instead of UUIDs
- Both ingest mechanisms (authenticated game loader + scouting loader) produce named team rows
- The same opponent appearing in multiple games maps to one team row (existing `gc_uuid` UNIQUE constraint handles this)
- Existing UUID-stub team rows in the database are backfilled from on-disk data

## Non-Goals
- Changing the database schema (no migration needed -- `teams.name` column already exists)
- Modifying the query layer or templates (already correct)
- Duplicating opponent_resolver logic (that module handles resolved/linked opponents; this epic handles initial insert)
- Changing the crawler layer (schedule data is already crawled and saved)

## Success Criteria
- On the player detail page, "Recent Games" shows human-readable opponent names (e.g., "Anytown Eagles") instead of UUIDs
- Running `bb data load` with existing raw data produces named team rows
- Running `bb data scout` with existing scouting data produces named team rows
- No team rows in the database have `name = gc_uuid` where a corresponding opponent name exists in on-disk data (rows with no on-disk name source may retain UUID names)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-132-01 | Use opponent names from on-disk data in both loader paths | TODO | None | - |
| E-132-02 | Backfill existing UUID-stub team names from on-disk data | TODO | E-132-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Authenticated Loader Path
`GameLoader` (in `src/gamechanger/loaders/game_loader.py`) processes boxscores from `data/raw/{season}/teams/{team_id}/games/`. It already reads `game_summaries.json` from the same team directory to build a summary index.

**Primary name source: `opponents.json`** -- co-located in the same team directory. Contains `progenitor_team_id` (the canonical GC UUID) and `name` for each opponent. The `progenitor_team_id` matches `pregame_data.opponent_id` from schedule and the UUID used as boxscore keys (confirmed in API docs: `docs/api/endpoints/get-teams-team_id-opponents.md`). This is the simplest source because it's a direct UUID→name mapping already co-located with the game data.

**UUID semantics caveat**: `opponents.json` has TWO UUID fields with different meanings. `root_team_id` is a local registry key. `progenitor_team_id` is the canonical GC team UUID used everywhere else. The lookup MUST be keyed by `progenitor_team_id`, NOT `root_team_id`. Additionally, `progenitor_team_id` is null on ~14% of opponent records (10/70 observed) -- those opponents will fall back to UUID-as-name.

**Supplementary source: `schedule.json`** -- also co-located. Contains `pregame_data.opponent_id` (same UUID as `progenitor_team_id`) and `pregame_data.opponent_name`. Can fill gaps where `opponents.json` has null `progenitor_team_id` but the game still has a scheduled opponent name.

`_ensure_team_row()` uses `INSERT OR IGNORE`, so for existing rows it falls through to `SELECT`. When the existing row has `name == gc_uuid` (UUID-stub from a prior load), the name should be updated to the real opponent name. When the existing row has a non-UUID name (set by opponent_resolver or manual edit), the name should NOT be overwritten. This makes normal loading self-healing: re-running `bb data load` fixes UUID-stub names without needing the separate backfill command.

### Scouting Loader Path
`ScoutingLoader` (in `src/gamechanger/loaders/scouting_loader.py`) delegates boxscore loading to `GameLoader.load_file()`. It builds a `GameSummaryEntry` index from `games.json` (public games endpoint response), which contains `opponent_team.name`. The opponent name from `games.json` needs to flow through to `GameLoader` so `_ensure_team_row()` uses it.

The scouting path has an additional wrinkle: in `_build_games_index()`, the `GameSummaryEntry.opponent_id` is set to `""` (empty string) because the public games response structure differs from game-summaries. The opponent UUID comes from the boxscore keys, not from the games index. The opponent name, however, IS in the games index (`opponent_team.name`). The `id` field in each `games.json` entry is the `game_stream_id` (same value used as the boxscore filename), so a `game_stream_id → opponent_team.name` map can be built alongside the existing games index. The challenge is then passing that name through to `GameLoader` when the opponent UUID is discovered during boxscore parsing.

### Scouting Loader Safety Net
`ScoutingLoader._record_uuid_from_boxscore_path()` (line 488 of `scouting_loader.py`) has an inline `INSERT OR IGNORE` that creates UUID-stub rows as a "safety net" for UUID keys found in boxscores. This runs AFTER `GameLoader.load_file()` for each boxscore, so in the happy path the row already exists with a name and the INSERT is a no-op. However, if `load_file()` fails/skips a boxscore, this safety net can create a UUID-stub row. This code path must also use opponent names when available.

Note: `roster.py` and `season_stats_loader.py` also have `_ensure_team_row()` methods with the same pattern, but they only run for member teams (which already have proper names from admin setup). Those are not in scope.

### Opponent Deduplication
The `teams` table has a UNIQUE constraint on `gc_uuid`. When the same opponent appears in multiple games, `_ensure_team_row()` uses `INSERT OR IGNORE` -- the first insert creates the row, subsequent calls fall through to `SELECT`. With the self-healing behavior (update UUID-stub names on SELECT), deduplication works correctly: the first insert creates a named row, and subsequent calls for the same opponent are no-ops.

### Backfill Strategy
Existing UUID-stub rows (where `teams.name` looks like a UUID) can be fixed by scanning on-disk data files. For each `opponents.json`, `schedule.json`, and scouting `games.json`, extract the opponent name mapping and UPDATE any teams row where `name = gc_uuid`.

The opponent_resolver already does this for resolved opponents (lines 373-382 of `opponent_resolver.py`). The backfill should use the same pattern: only update rows where `name == gc_uuid` (preserving any name already set by opponent_resolver or manual edit).

## Open Questions
None.

## History
- 2026-03-19: Created
- 2026-03-19: Revised to use opponents.json as primary name source (per SE analysis)
- 2026-03-19: Codex spec review remediation -- 5 findings fixed (method name, CLI contract, success criteria/fallback reconciliation, guard alignment, UUID caveat propagation). Set to READY.
- 2026-03-19: Refinement pass -- AC-4 revised for self-healing behavior (update UUID-stub names on existing rows during normal loading, not just on INSERT). Scouting path linkage clarified (game_stream_id connects games.json name to boxscore UUID). E-132-02 context updated to reflect catch-stragglers role.
- 2026-03-19: Holistic refinement -- added scouting_loader `_record_uuid_from_boxscore_path()` (line 488) as third code path in scope (AC-5 on E-132-01). Confirmed roster.py and season_stats_loader.py NOT in scope (member teams only). No UXD or api-scout consultation needed.
