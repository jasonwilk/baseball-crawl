# E-211: Fix Opponent-Perspective UUID Contamination

## Status
`ACTIVE`

## Overview
Stop opponent-perspective UUIDs from leaking into the `teams.gc_uuid` column and causing duplicate players and missing spray charts in standalone reports. The GameChanger API returns different UUIDs for the same team depending on the caller's perspective (own-team vs opponent); three pipeline paths currently store the wrong-perspective UUID as `gc_uuid`, which poisons downstream code that trusts it.

## Background & Context
When generating standalone reports for scouted teams (e.g., Waverly Vikings Varsity), two bugs appear:

1. **Duplicate players** -- "C Dewing" (10.2 IP) and "Cy Dewing" (1.0 IP) appear as separate pitchers. Same person, different UUIDs from different API perspectives.
2. **Missing spray charts** -- the spray endpoint returns 404 for every game because the stored `gc_uuid` is the opponent-perspective UUID, not the schedule-owning UUID.

**Root cause**: The GC API returns different UUIDs for the same team depending on which endpoint and perspective is used. When Standing Bear's member pipeline processes a boxscore, the opponent team is keyed by an opponent-perspective UUID (e.g., `18bf858f` for Waverly). Three pipeline paths store this as `gc_uuid` on the tracked team row. But the real gc_uuid (from `POST /search`) is `370cb40c`. The spray endpoint only works with the real UUID.

**Verified data** (2026-04-03):
- Waverly (team 93): DB has `gc_uuid = 18bf858f` (wrong). Search returns `370cb40c` (correct).
- Spray: 404 with wrong UUID, success with correct UUID.
- 10 plays files: 9 correct-perspective, 1 opponent-perspective (creating 20 duplicate players).
- 13 other scouted teams checked: only 1 other had opponent-perspective game, no duplicate players.

**Expert consultation**:
- SE identified 3 contamination vectors (game_loader, scouting_loader, scouting_crawler) and recommended `gc_uuid=None` for all boxscore-derived opponent UUIDs. Report plays query should be scoped to scouting directory's boxscore inventory.
- DE confirmed: fix callers not `ensure_team_row`; accept step-3 name dedup imperfection (small scale, existing dedup merge tool handles stragglers); data cleanup via documented SQL not CLI commands.

## Goals
- Eliminate all paths that store opponent-perspective UUIDs as `gc_uuid` on tracked teams
- Report generator always resolves gc_uuid via search (never trusts stored value for tracked teams)
- Report plays stage processes only games from the report's own crawled schedule
- Clean up existing contaminated data (wrong gc_uuids, duplicate players)

## Non-Goals
- Changing `ensure_team_row` internals (the function is correctly context-free)
- Building a permanent CLI command for data cleanup (one-time operation)
- Resolving name-variation dedup (existing `bb data dedup` handles this)
- Fixing member-team gc_uuid storage (member teams get their UUID from authenticated API -- correct)

## Success Criteria
- Waverly standalone report generates with correct spray charts and no duplicate players
- No tracked team row has an opponent-perspective UUID stored as `gc_uuid` after cleanup
- Re-running member pipeline does not re-contaminate tracked team gc_uuids
- Report plays stage does not pick up games from other teams' pipelines

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-211-01 | Stop UUID contamination at all three pipeline sources | DONE | None | SE |
| E-211-02 | Fix report generator gc_uuid resolution and plays scoping | DONE | None | SE |
| E-211-03 | Document and execute data cleanup | DONE | E-211-01, E-211-02 | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: The Three Contamination Vectors

All three paths call `ensure_team_row(gc_uuid=<boxscore_key>)` where `<boxscore_key>` is an opponent-perspective UUID, not the canonical gc_uuid:

1. **game_loader._ensure_team_row** (`src/gamechanger/loaders/game_loader.py:1176`): Called from `_resolve_team_ids` (line 542) with `summary.opponent_id or opp_key`. Both values come from the boxscore perspective.
2. **scouting_loader._record_uuid_from_boxscore** (`src/gamechanger/loaders/scouting_loader.py:575`): "UUID opportunism" -- iterates UUID keys from boxscore responses and creates stub rows with those UUIDs as gc_uuid.
3. **scouting_crawler._record_uuid_from_boxscore** (`src/gamechanger/crawlers/scouting.py:517`): Same UUID opportunism pattern in the crawler phase.

### TN-2: Fix Principle

"When you only use the real UUID, you won't use the wrong one." The `gc_uuid` for tracked teams should ONLY come from the search resolver (`POST /search` filtered by `public_id`). Boxscore keys are perspective-dependent and must never be stored as `gc_uuid`.

**Fix approach**: For the game loader (vector 1), pass `gc_uuid=None` to `ensure_team_row` and use the boxscore identifier as a name fallback only (never as gc_uuid). For the scouting loader and scouting crawler (vectors 2 and 3), remove the `_record_uuid_from_boxscore` methods entirely -- they are redundant since the game loader already creates team rows during boxscore loading. Rely on name+season_year dedup (step 3) instead. Accept that name variations may occasionally create duplicate rows -- this is preferable to storing wrong UUIDs, and the existing `bb data dedup` tool handles stragglers.

### TN-3: Report Generator Fixes

Three issues in `src/reports/generator.py`:

1. **gc_uuid resolution** (lines 970-987): Currently trusts stored gc_uuid (`if existing_gc_uuid: resolved_gc_uuid = existing_gc_uuid`). Should always search-resolve for tracked teams, ignoring any stored gc_uuid. The stored value may be opponent-perspective.

2. **Plays crawl scoping** (lines 553-562): `WHERE home_team_id = ? OR away_team_id = ?` picks up games loaded from other teams' pipelines. Replace with filesystem-only game discovery -- derive game IDs from boxscore filenames in the report's scouting directory (`data/raw/{crawl_season_id}/scouting/{public_id}/boxscores/*.json`). Each filename stem is the `event_id` (= `game_id` in the DB). This ensures the plays stage processes only games from the report's own crawled schedule. **Bonus**: this also mitigates the spray endpoint asymmetry concern -- when processing only games from the scouted team's own schedule, the scouted team is always the schedule owner, so spray calls return both teams' data.

3. **Plays pitching query scoping**: `_query_plays_pitching_stats` (line 677) uses the same broad `WHERE (g.home_team_id = ? OR g.away_team_id = ?)` pattern. This pulls in plays data from cross-pipeline games at query time, producing inflated stats and mixing perspective-dependent pitcher_ids. Must be scoped to the report's game set (derived from boxscore filenames) or filtered by pitching team identity.

### TN-4: Data Cleanup

One-time cleanup via documented operator procedure with SQL (not a migration, not a CLI command):

**Phase 1 -- Identify contaminated gc_uuids**: Query tracked teams where gc_uuid does not match any search-resolved UUID. In practice, NULL gc_uuid on all tracked teams that have a `public_id` (the search resolver can re-resolve them).

**Phase 2 -- Remove opponent-perspective game data**: Use a hybrid filesystem+SQL game-based identification approach. The operator lists `game_id`s from boxscore filenames in the scouting directory (`boxscores/*.json`), then SQL identifies games in the DB involving the scouted team that are NOT in that list -- those are the opponent-perspective games. For Waverly (team 93), this is the 1 opponent-perspective game out of 10. Delete all data from those games in FK order: `play_events` -> `plays` -> `player_game_batting` -> `player_game_pitching` -> `spray_charts` -> `reconciliation_discrepancies` -> `player_season_batting` -> `player_season_pitching` -> `team_rosters` -> `players` (orphaned players only). Also remove stale plays JSON files from the scouting plays directory. Then re-run the scouting pipeline to recreate with correct IDs.

**Phase 3 -- Re-resolve**: After code fixes are deployed, run `bb data scout` to re-trigger search resolution and scouting pipeline for all tracked teams. Their gc_uuids will be correctly set by the search resolver.

### TN-5: Safe Callers (No Changes Needed)

These paths correctly pass gc_uuid and need no changes:
- **roster loader** (`src/gamechanger/loaders/roster.py:339`): Uses team's own gc_uuid from file path
- **season_stats_loader** (`src/gamechanger/loaders/season_stats_loader.py:601`): Same
- **opponent_resolver** (`src/gamechanger/crawlers/opponent_resolver.py:617`): Uses gc_uuid from `POST /search` (canonical)

### TN-6: Boxscore Key Asymmetry

GC boxscore responses are asymmetric: own team = `public_id` slug (short alphanumeric), opponent = UUID (with dashes). The game_loader's `_detect_team_keys()` (line 635) splits these. The UUID key for the opponent is NOT the opponent's canonical gc_uuid -- it is a perspective-dependent identifier. `summary.opponent_id` from game-summaries is the same perspective-dependent value.

**UUID type hierarchy** (per api-scout, confirmed via proxy traffic): GC uses three distinct UUID types per opponent: `root_team_id` (local registry key, used for roster/avatar endpoints), `progenitor_team_id` (canonical gc_uuid, returned by `POST /search` as `result.id`), and `owning_team_id` (always equals the caller's own team_id). The boxscore opponent key and `game_stream.opponent_id` correspond to `root_team_id` -- the local registry key, NOT the canonical `progenitor_team_id`. This is why boxscore-derived UUIDs fail when used with the spray endpoint or other team-scoped authenticated endpoints.

## Open Questions
- None (all questions resolved through SE and DE consultation)

## History
- 2026-04-03: Created. SE and DE consulted on contamination vectors, fix approach, and data cleanup strategy.
- 2026-04-03: Set to READY after three review passes (24 findings, 14 accepted, 10 dismissed). All accepted findings incorporated with consistency sweeps.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 7 | 3 | 4 |
| Internal iteration 1 -- Holistic team (PM+SE+DE+api-scout) | 11 | 7 | 4 |
| Codex iteration 1 | 6 | 4 | 2 |
| **Total** | **24** | **14** | **10** |
