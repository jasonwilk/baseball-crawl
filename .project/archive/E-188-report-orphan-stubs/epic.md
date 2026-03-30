# E-188: Eliminate Orphan Team Stubs from Report Generation

## Status
`COMPLETED`

## Overview
The standalone report generation flow creates ~30 orphan team rows per report, accumulating UUID-named junk in the `teams` table and risking name-collision bugs that cause spray chart failures. This epic eliminates the orphans via a snapshot-and-diff cleanup after each report generation.

## Background & Context
Promoted from IDEA-057. The report generator (`src/reports/generator.py`) calls `ScoutingLoader.load_team()`, which delegates boxscore loading to `GameLoader.load_file()`. The `games` table has `NOT NULL` FK references to `teams(id)` for both `home_team_id` and `away_team_id`, forcing the GameLoader to create a tracked team row for every opponent encountered in boxscores. Additionally, `ScoutingLoader._record_uuid_from_boxscore_path()` creates stubs as a redundant safety net.

A report for a team with 30 games creates ~30 UUID-named stub rows with no `public_id`, no human-readable name, and no purpose in the reports context. The Lincoln Sox 12U report created ~30 orphan teams. Each new report adds more.

**Real-world impact (North Star case, E-186)**: Stubs created in one flow can pollute `ensure_team_row` name matching for another flow. Team 35 ("Lincoln North Star Reserve 26'") was matched by name to a row with stale gc_uuid, causing all spray endpoint calls to 404. Eliminating orphan stubs prevents this class of collision.

**Expert consultation**: SE and DE consulted on approach selection. SE recommended the snapshot-and-diff approach (track team IDs before/after load, delete the difference) with a critical ordering insight: query game-dependent data BEFORE orphan cleanup, since cleanup deletes the game rows the queries depend on. DE confirmed FK cascade safety of the deletion order. SE advised against embedding gc_uuid verification in the generator (violates the "never overwrite gc_uuid" rule from `gc-uuid-bridge.md`; the North Star case is a data quality issue better addressed by a separate repair tool).

## Goals
- Eliminate orphan team stubs created by report generation without breaking the opponent scouting flow
- Prevent the name-collision class of bugs (North Star pattern) by reducing junk in the teams table

## Non-Goals
- Refactoring the GameLoader or ScoutingLoader to avoid game-row creation (the FK constraint is legitimate for the scouting flow)
- Changing the `games` table schema (nullable FKs would weaken integrity for the scouting flow)
- Addressing orphan stubs from the opponent scouting flow itself (those stubs are legitimate)
- Building a CLI command for one-time data cleanup (one-off tasks are documented SQL, not permanent CLI commands)
- Building a general-purpose team dedup/merge tool (covered by IDEA-043)
- Adding gc_uuid verification to the report generator (violates the "never overwrite" storage rule; address as separate data quality tooling if needed)

## Success Criteria
- Generating a standalone report creates zero net new orphan team rows in the `teams` table
- The opponent scouting flow (`bb data scout`, admin opponent resolution) continues to work unchanged
- All existing tests pass; new tests cover the cleanup paths

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-188-01 | Post-load orphan cleanup in report generator | DONE | None | - |
| E-188-02 | One-time cleanup of existing orphan stubs | ABANDONED | E-188-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Snapshot-and-Diff Cleanup Strategy

The generator snapshots team IDs before and after the scouting load to identify orphans created during this report run.

**Before load** (after `ensure_team_row` for the subject team, before `ScoutingLoader.load_team()`):
```
pre_team_ids = set of all teams.id values
```

**After load** (after `ScoutingLoader.load_team()` completes):
```
post_team_ids = set of all teams.id values
orphan_ids = post_team_ids - pre_team_ids - {subject_team_id}
```

**Critical ordering**: The generator must query all game-dependent data (W/L record, recent form, freshness, runs avg) BEFORE running the orphan cleanup. The cleanup deletes game rows that these queries depend on. The sequence is:

1. Run `ScoutingLoader.load_team()` (creates game rows, per-game stats, season aggregates, roster, stubs)
2. Query everything the report needs from the database (batting, pitching, roster, record, recent form, freshness, runs avg, spray charts)
3. Run orphan cleanup (deletes orphan teams + dependent data)
4. Render the report HTML from the queried data
5. Save the report file and mark the reports row as `ready`

The current code already queries before rendering (the `try` block after the pipeline in `generate_report()` that calls `_query_batting`, `_query_pitching`, etc.). The cleanup inserts between the query block and the render step.

**Deletion order** (two phases: game-scoped, then team-scoped):

Phase 1 -- game-scoped (delete by `game_id`, covering BOTH teams' data for affected games):
1. Identify affected games: `SELECT game_id FROM games WHERE home_team_id IN (:orphan_ids) OR away_team_id IN (:orphan_ids)`
2. `DELETE FROM player_game_batting WHERE game_id IN (:game_ids)`
3. `DELETE FROM player_game_pitching WHERE game_id IN (:game_ids)`
4. `DELETE FROM spray_charts WHERE game_id IN (:game_ids)`
5. `DELETE FROM games WHERE game_id IN (:game_ids)`

Phase 2 -- team-scoped (delete orphan-only data):
6. `DELETE FROM team_rosters WHERE team_id IN (:orphan_ids)`
7. `DELETE FROM player_season_batting WHERE team_id IN (:orphan_ids)`
8. `DELETE FROM player_season_pitching WHERE team_id IN (:orphan_ids)`
9. `DELETE FROM teams WHERE id IN (:orphan_ids)`

**Why game-scoped in Phase 1**: `player_game_batting.game_id` and `player_game_pitching.game_id` are `NOT NULL REFERENCES games(game_id)`. The subject team's per-game stat rows also reference the same game rows as orphan opponents. Deleting games without first deleting ALL referencing per-game stats (both teams) would violate FK constraints under `PRAGMA foreign_keys=ON`. Deleting the subject team's per-game rows is safe because season aggregates are already computed and queried before cleanup runs; re-generation recreates all data.

**Tables intentionally NOT touched by cleanup**:
- `players` -- player identity is shared across teams; orphan team stubs do not own player rows
- `scouting_runs` -- only created for the subject team (the team being scouted), never for opponent stubs
- `crawl_jobs` -- only created by the pipeline trigger, not by the report generator
- `opponent_links` -- only populated by the opponent resolution flow; if a team appears in `opponent_links.resolved_team_id`, it also appears in `team_opponents` (via `finalize_opponent_resolution()`), so the `team_opponents` check in TN-2 is sufficient

**Safety**: The cleanup only deletes teams that were created during THIS load run (snapshot diff). Teams that existed before the load -- including legitimate scouting opponents, member teams, and report subjects -- are never touched. Cleanup failure is non-fatal: wrap in try/except, log a warning, and continue to rendering.

### TN-2: One-Time Cleanup CLI Criteria

For existing orphan stubs from prior reports, the CLI command identifies teams that:
- Have `membership_type = 'tracked'` and `is_active = 0`
- Have no rows in `team_opponents` (not linked as a scouting opponent)
- Have no rows in `reports` (not a report subject)
- Have `source IN ('game_loader', 'scouting_loader')` (created by the loader pipeline)

The UUID-like name pattern (`________-____-____-____-____________`) is a supporting signal but not the sole filter -- the above criteria are the safety net. The command uses `--dry-run` (default) / `--execute` flags per the established pattern in `bb data dedup` and `bb data repair-opponents`. Deletion follows the same FK-safe order as TN-1.

### TN-3: Why Not Approach D (Bypass Games Table)

Season aggregates (`_compute_season_aggregates` in ScoutingLoader) JOIN `player_game_batting`/`player_game_pitching` through `games` on `game_id` + `season_id`. Per-game stat rows require game rows as FK targets. The report needs season aggregates for batting and pitching tables. A full games-table bypass would require either duplicating all stat extraction from JSON or restructuring the aggregate computation -- too much scope for the value delivered.

The snapshot-and-diff approach lets the full loader pipeline run (creating stubs as a side effect) and then cleans them up. The stubs exist only transiently.

## Open Questions
None -- all approach questions resolved during SE and DE consultation.

### Review Scorecard (Planning)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 3 | 5 |
| Internal iteration 1 -- Holistic team (PM+SE+DE) | 5 | 4 | 1 |
| **Total** | **13** | **7** | **6** |

Codex validation: skipped (small epic, critical FK issue caught and fixed during internal review).

### Review Scorecard (Dispatch)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-188-01 | 1 | 0 | 1 |
| Per-story CR -- E-188-02 | 2 | 2 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 1 | 1 | 0 |
| **Total** | **4** | **3** | **1** |

## History
- 2026-03-29: Created (promoted from IDEA-057)
- 2026-03-29: Revised based on SE consultation -- dropped gc_uuid verification story (violates "never overwrite" rule), adopted snapshot-and-diff approach, added critical query-before-cleanup ordering
- 2026-03-29: Incorporated review findings -- fixed FK violation in TN-1 deletion order (game_id-scoped Phase 1 + team_id-scoped Phase 2), added excluded tables documentation (players, scouting_runs, crawl_jobs, opponent_links), removed stale line references
- 2026-03-29: Set to READY after internal review
- 2026-03-30: Set to ACTIVE, dispatch started.
- 2026-03-30: All stories DONE. CR integration: APPROVED (0). Codex: 1 P1 (opponent_links guard -- fixed). Epic COMPLETED.
- 2026-03-30: E-188-02 dropped -- one-time cleanup tasks should not be permanent CLI commands. Existing orphans can be cleaned with documented SQL.
- Documentation assessment: No documentation impact (E-188-02 dropped; no new CLI command shipped).
- Context-layer assessment:
  - New convention/pattern: YES (snapshot-and-diff cleanup, shared cleanup module at `src/db/cleanup.py`) -- small enough to not require separate codification.
  - Architectural decision: No
  - Footgun: No
  - Agent behavior: No
  - Domain knowledge: No
  - New CLI command: No (E-188-02 dropped)
