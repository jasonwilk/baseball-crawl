# E-199: Plays-Derived Stats in Standalone Reports

## Status
`COMPLETED`

## Overview
Add plays-derived statistics (FPS%, QAB%, pitch counts) to standalone scouting reports so coaches get the full picture in the one-pager they actually use. Reports are the primary delivery mechanism handed to coaches -- this closes the #1 delivery gap. Neither the dashboard nor standalone reports currently display plays-derived stats; this epic adds them to reports first (the primary coaching tool).

## Background & Context
The plays pipeline (E-195) and reconciliation engine (E-198) built the data infrastructure for play-by-play analytics: per-PA records with FPS flags, QAB flags, pitch counts, and pitcher attribution corrections. The dashboard opponent flow can query this data live, but standalone reports (`src/reports/generator.py` + `src/reports/renderer.py`) don't query or display any of it.

The user has an explicit delivery parity requirement: new data capabilities must update BOTH delivery paths (dashboard and reports). Reports are the primary coaching tool.

**Expert consultations completed:**
- **Baseball-coach**: FPS% per pitcher and QAB% per batter are MUST HAVE (inline in existing sections). NO separate "advanced" section -- all stats inline with existing tables.
- **Software-engineer**: Existing query pattern supports new `_query_plays_pitching_stats()` and `_query_plays_batting_stats()` functions. Merge plays stats into existing batting/pitching dicts by player_id. Plays endpoint works for opponent games (not ownership-gated). Plays crawl should be added as a pipeline stage in report generation. Graceful degradation via "—" when no plays data. Performance: <10ms additional query time.
- **Data-engineer**: Existing indexes sufficient (idx_plays_game_id, idx_plays_pitcher_id, idx_plays_batter_id, idx_plays_fps). 1,700 rows is trivially fast. Direct SQL aggregation at query time -- no pre-computation or materialization needed. No new migrations or indexes required. Pitching query must NOT filter by `batting_team_id` -- scope to games and match pitcher_ids to roster in merge step.

**SE review findings incorporated (iteration 1):**
- PlaysCrawler requires CrawlConfig and is not reusable for the scouting/report flow. A new `_crawl_and_load_plays()` helper must be written in the generator.
- PlaysLoader expects `teams/{gc_uuid}/` directory layout; scouting data lives under `scouting/{public_id}/`. Directory path must be adapted.
- `games.game_id` (populated from public schedule's `id` field) is the correct path parameter for the plays endpoint -- confirmed by the scouting crawler using the same ID for boxscores via the same `/game-stream-processing/` base path.

**User scope correction:**
- Reconciliation must run automatically as part of the pipeline (crawl → load → reconcile → query). Data quality steps are part of the pipeline, not manual CLI commands. The standalone `bb data reconcile` CLI remains as a debugging/operator tool.
- Reconciliation confidence gating is not needed in reports -- not because reconciliation "won't have run," but because reconciliation ALWAYS runs as part of the pipeline, so the data IS reconciled by the time stats are queried.

## Goals
- Per-pitcher FPS% and pitches-per-batter displayed inline in the pitching table
- Per-batter QAB% displayed inline in the batting table
- Team-level pitches/PA aggregate in the executive summary
- Plays data crawled, loaded, and reconciled as part of the report generation pipeline
- FPS% reflects reconciled pitcher attribution (corrected data, not raw)
- Report-generated team data cleaned up on report deletion (when team is not independently tracked)
- Graceful degradation when plays data is unavailable

## Non-Goals
- Raw pitch sequences in reports (coach says too much noise)
- K/BB from play-by-play (nice-to-have, not this epic)
- Dashboard plays stats (neither dashboard nor reports display plays stats today; reports are addressed first in this epic; dashboard is a separate future epic)
- Reconciliation confidence gating in reports (not needed -- reconciliation runs automatically as part of the pipeline, so data IS reconciled by the time it's queried)
- New database migrations or indexes
- Heat-map coloring for plays-derived stats (future enhancement if warranted)

## Success Criteria
- A standalone report generated via `bb report generate` includes FPS% in the pitching table and QAB% in the batting table
- FPS% reflects reconciled pitcher attribution (reconciliation runs automatically as part of the pipeline)
- Stats show "—" when plays data is unavailable for a team
- Report generation pipeline crawls, loads, and reconciles plays data for the scouted team
- Deleting a report cascade-deletes the team's data when the team is not independently tracked
- No increase in report generation failure rate

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-199-01 | Plays pipeline stage and query functions in report generator | DONE | None | - |
| E-199-02 | Render plays-derived stats in report template | DONE | E-199-01 | - |
| E-199-03 | Cascade-delete team data on report deletion | DONE | E-199-01 (shared file) | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Plays Pipeline Stage in Report Generator

The report generator (`src/reports/generator.py`) runs a multi-stage pipeline: scouting crawl → scouting load → gc_uuid resolution → spray crawl → spray load → query → render. The plays crawl+load+reconcile should be added as a new stage in this pipeline:

**Updated pipeline**: scouting crawl → scouting load → gc_uuid resolution → spray crawl → spray load → **plays crawl → plays load → reconciliation** → query → render

The plays endpoint (`GET /game-stream-processing/{event_id}/plays`) is NOT ownership-gated -- it works for opponent games using the same `event_id` from game-summaries. The report generator already has an authenticated `GameChangerClient` available.

**Critical: PlaysCrawler cannot be reused directly.** `PlaysCrawler` takes a `CrawlConfig` and iterates `config.member_teams` -- it's designed for the member-team pipeline. In the scouting/report flow, there is no `CrawlConfig` or `game-summaries.json`. A new `_crawl_and_load_plays()` helper function must be written in the generator (similar to `_crawl_and_load_spray()`), but it cannot delegate to `PlaysCrawler`. Instead, it should:
1. Query completed game IDs from the `games` table (populated by the scouting loader): `SELECT game_id FROM games WHERE season_id = ? AND (home_team_id = ? OR away_team_id = ?) AND status = 'completed'`
2. For each game, check if plays rows already exist in the DB (whole-game idempotency)
3. Fetch plays via `GameChangerClient.get(f"/game-stream-processing/{game_id}/plays")`
4. Write raw JSON to the scouting data directory
5. Use `PlaysLoader` to load the fetched data
6. **Run reconciliation** for each loaded game: call `reconcile_game(conn, game_id, dry_run=False)` from `src/reconciliation/engine.py`. This corrects pitcher attribution errors in the plays data before stats are queried. The reconciliation engine reads boxscore data from cached JSON files and corrects `plays.pitcher_id` values in-place.

**ID mapping**: `games.game_id` (populated from the public schedule's `game["id"]` field by the scouting loader) is the correct path parameter for the plays endpoint. This is confirmed by the scouting crawler using the same ID for boxscores via the same `/game-stream-processing/` base path (see `src/gamechanger/crawlers/scouting.py:238-241`).

**Directory layout**: Plays files should be written to `data/raw/{season}/scouting/{public_id}/plays/{game_id}.json`. `PlaysLoader.load_all()` expects a `team_dir` with a `plays/` subdirectory -- pass the scouting directory (`data/raw/{season}/scouting/{public_id}/`) as `team_dir`. Construct a `TeamRef` from the team's DB row for the loader.

**Reconciliation dependency**: `reconcile_game()` reads cached boxscore JSON from disk to build ground-truth BF counts. The scouting crawler writes boxscores to `data/raw/{season}/scouting/{public_id}/boxscores/{game_id}.json`. These files must exist before reconciliation runs -- this is naturally satisfied because the scouting crawl stage runs before the plays stage.

**Failure semantics**: The plays stage has three sub-steps (crawl, load, reconcile). Failure handling is per-game, not all-or-nothing:
- If crawl fails for a game, that game has no plays data. Other games proceed.
- If load fails for a game, same -- other games proceed.
- If reconciliation fails for a game, the plays data for that game is still usable (reconciliation improves accuracy but its absence doesn't invalidate the data). Other games proceed.
- If the entire stage fails (e.g., auth expiration before any games are fetched), the report renders without plays-derived stats, showing "—" for FPS%/QAB%.
- Stats are computed from whatever plays data was successfully loaded and reconciled. Partial coverage is reflected in `plays_game_count`.

### TN-2: Query Functions and Data Merge

Two new query functions in the generator:

**`_query_plays_pitching_stats(conn, team_id, season_id)`**: Aggregates from the `plays` table grouped by `pitcher_id`:
- FPS%: `SUM(is_first_pitch_strike) / COUNT(*)` excluding HBP and Intentional Walk outcomes (per CLAUDE.md FPS% definition)
- Pitches per batter faced: `SUM(pitch_count) / COUNT(*)`

**Pitching query scoping**: The `plays` table has `batting_team_id` (the team at bat), NOT a `pitching_team_id`. For pitching stats, scope the query to games involving the scouted team, GROUP BY `pitcher_id`, and then match pitcher_ids to the scouted team's roster during the Python merge step. Do NOT filter by `batting_team_id = team_id` for pitching stats -- that would compute stats for the *opponent's* pitchers.

**`_query_plays_batting_stats(conn, team_id, season_id)`**: Aggregates from the `plays` table grouped by `batter_id`:
- QAB%: `SUM(is_qab) / COUNT(*)`
- Pitches seen per PA: `SUM(pitch_count) / COUNT(*)`

**Batting query scoping**: Filter by `batting_team_id = team_id` -- this correctly selects plays where the scouted team was batting.

Both functions return dicts keyed by player_id. The generator merges these into the existing batting/pitching dicts by player_id before passing to the renderer. Missing player_ids get default values ("—").

Team-level aggregates computed from the same queries:
- Team FPS%: overall (not per-pitcher average)
- Team pitches/PA: overall average

**Plays coverage metadata**: The generator should also compute `plays_game_count` (number of games with plays data) alongside the existing `game_count`. This allows the template to show coverage context (e.g., "FPS%/QAB% based on N of M games") when plays data is partial.

### TN-3: Template Integration

Plays-derived stats are added as new columns in existing tables -- NOT as separate sections (per coach consultation):

**Pitching table**: Add "FPS%" column after "Strike%" and "P/BF" (pitches per batter faced) column after FPS%. Both are `mob-hide` class (hidden on mobile).

**Batting table**: Add "QAB%" and "P/PA" (pitches seen per PA) columns after "BB%". Both `mob-hide` class. QAB% and P/PA tell different stories -- QAB% measures at-bat quality, P/PA measures plate discipline / ability to work counts.

**Executive summary strip**: Add team FPS% and team pitches/PA to the existing summary line. Team FPS% is "the first number I look at when scouting a pitching staff" (per coach consultation).

All new columns show "—" when plays data is unavailable for that player.

### TN-4: Data Availability and Graceful Degradation

Reports work for any GC `public_id`. Plays data may not exist for all games or all teams. The system must degrade gracefully:

1. **No plays data at all**: All plays columns show "—". No error. Template renders normally.
2. **Partial plays data**: Stats computed from available games only. `plays_game_count` provides coverage context.
3. **Plays crawl fails**: Non-fatal. Log warning, continue without plays data.

The `has_plays_data` boolean in the template context controls whether team aggregates appear in the executive summary.

### TN-5: Report Data Lifecycle

Reports are ephemeral (14-day expiry), but the data they create in the DB persists until the report is manually deleted. When a report is deleted via the admin UI, the associated team data is cascade-deleted IF the team is not independently tracked. Note: expired reports are currently only hidden/404'd, not actively deleted. Automatic expiry-triggered deletion is out of scope for this epic.

**What is created during report generation:**
- Team row (`is_active=0`, `membership_type='tracked'`) -- created by scouting crawl stage
- Season stats (player_season_batting, player_season_pitching) -- created by scouting load stage
- Spray charts -- created by spray crawl+load stage
- Plays and play_events rows -- NEW in this epic
- Reconciliation discrepancies -- NEW in this epic

**Cleanup-on-delete with guard conditions:**
1. When a report is deleted, read `team_id` from the `reports` row BEFORE deleting it (the FK is lost after deletion).
2. Check whether the team is eligible for cleanup:
   - `is_active = 0` (not actively managed)
   - No rows in `team_opponents` reference this `team_id` (not tracked as an opponent)
   - No other `reports` rows reference this `team_id` (not used by another report)
   - No games involving this team also involve a tracked team (a team that appears in `team_opponents`). This prevents cascade-deleting per-game data (player_game_batting, player_game_pitching, spray_charts) for tracked opponents who shared games with the report team.
3. If ALL conditions pass, cascade-delete the team and all dependent data (per TN-6).
4. If ANY condition fails, only delete the `reports` row and HTML file. The team data is preserved.

**Reusability during report lifetime:**
- If the same team is reported again, the plays loader's whole-game idempotency (skip if plays rows exist) naturally reuses existing data.
- If the team is tracked (added to `team_opponents`) before the report expires, the guard condition prevents cleanup.
- Dashboard isolation is maintained: report-generated teams have `is_active=0` and no `team_opponents` link, so they do not appear in dashboard views.

### TN-6: FK-Safe Cascade Delete Order

No FK cascades exist in the schema. All deletes must be explicit SQL in dependency-safe order.

**Phase 1 -- game-scoped** (find games by team_id, then delete game-dependent data):
1. Identify game_ids: `SELECT game_id FROM games WHERE home_team_id = ? OR away_team_id = ?`
2. `DELETE FROM play_events WHERE play_id IN (SELECT id FROM plays WHERE game_id IN (...))`
3. `DELETE FROM plays WHERE game_id IN (...)`
4. `DELETE FROM reconciliation_discrepancies WHERE game_id IN (...)`
5. `DELETE FROM player_game_batting WHERE game_id IN (...)`
6. `DELETE FROM player_game_pitching WHERE game_id IN (...)`
7. `DELETE FROM spray_charts WHERE game_id IN (...)`
8. `DELETE FROM games WHERE game_id IN (...)`

**Phase 2 -- team-scoped** (delete team-dependent data):
1. `DELETE FROM team_rosters WHERE team_id = ?`
2. `DELETE FROM player_season_batting WHERE team_id = ?`
3. `DELETE FROM player_season_pitching WHERE team_id = ?`
4. `DELETE FROM scouting_runs WHERE team_id = ?`
5. `DELETE FROM crawl_jobs WHERE team_id = ?`
6. `DELETE FROM coaching_assignments WHERE team_id = ?`
7. `DELETE FROM user_team_access WHERE team_id = ?`
8. `UPDATE opponent_links SET resolved_team_id = NULL, resolution_method = NULL, resolved_at = NULL WHERE resolved_team_id = ?` (un-resolve rather than delete -- preserves the opponent name and link for re-resolution)
9. `DELETE FROM teams WHERE id = ?`

## Open Questions
None -- all design decisions locked from expert consultation, SE/DE review, and user input.

## History
- 2026-04-02: Created. Expert consultation completed with baseball-coach (stat priorities, presentation), software-engineer (query patterns, architecture), data-engineer (index coverage, optimization).
- 2026-04-02: SE review iteration 1 -- 6 findings. Accepted: PlaysCrawler reuse constraint (TN-1 rewritten), directory layout mismatch (TN-1 updated), event_id confirmation (TN-1 updated), plays coverage metadata (TN-2 updated). Scope reduction: reconciliation confidence gating removed (dead code in reports context -- deferred to dashboard). DE review -- 2 findings accepted: query scoping clarification (TN-2), minimum reconciliation threshold (now moot after confidence gating removal).
- 2026-04-02: CR spec audit + coach holistic review -- 8 findings. 3 accepted (has_plays_data definition, per-batter P/PA column, team FPS% in exec summary), 5 dismissed (4 referenced removed reconciliation gating, 1 low-severity non-issue). User design consideration: report data lifecycle documented as TN-5 (plays data persists deliberately, consistent with existing pattern).
- 2026-04-02: User scope correction -- reconciliation must run automatically as part of the pipeline (not a manual CLI step). TN-1 updated: pipeline is now crawl → load → reconcile → query. E-199-01 AC-2 added for reconciliation. Rationale for no confidence gating corrected: data IS reconciled (not "won't be reconciled").
- 2026-04-02: User design decision -- report-generated team data should be cleaned up on report deletion (not persist indefinitely). E-199-03 added. TN-5 rewritten from "data persists" to "cleanup-on-delete with guard conditions." TN-6 added for FK-safe cascade delete order. E-199-03 expanded with 8 ACs covering 6 test scenarios per user request for thorough data destruction testing.
- 2026-04-02: DE review iteration 2 -- 4 findings on TN-6. 2 accepted: missing FK tables in Phase 2 (crawl_jobs, coaching_assignments, user_team_access, opponent_links added), opponent_links un-resolve approach (NULL instead of DELETE to preserve re-resolution path). 2 dismissed (confirmations, not findings).
- 2026-04-02: SE review iteration 2 -- 6 findings. 3 accepted: shared-game guard added to TN-5 (prevents cascade-deleting tracked opponent per-game data), PlaysLoader season_id derivation note (E-199-01), team_id read-before-delete note (E-199-03). 3 dismissed (1 duplicate of DE iter 2 findings, 1 already resolved by DE iter 2, 1 confirmation).
- 2026-04-02: CR spec audit iteration 2 -- 7 findings. 1 accepted: consolidate cascade logic in `_cleanup_orphan_teams()` rather than duplicating in admin.py (E-199-03 files updated). 6 dismissed (5 already fixed by DE/SE iter 2, 1 incorrect dependency claim).
- 2026-04-02: Self-review iteration 3 -- 2 issues fixed: E-199-03 dependency on E-199-01 added (shared file), E-199-02 Description completed.
- 2026-04-02: Codex spec review -- 6 findings. 4 accepted: partial-failure semantics defined (TN-1, E-199-01 AC-5), E-199-03 narrowed to manual deletion only (no auto-expiry), PlaysLoader season_id note corrected (derives from games table, not external), dashboard plays claims corrected (neither path displays plays stats today). 2 dismissed: implementation detail prescription claim (TNs describe constraints, not code), api-scout consultation (endpoint behavior already confirmed by SE review + CLAUDE.md).
- 2026-04-02: **Status → READY.** All review rounds complete.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 6 | 1 | 5 |
| Internal iteration 1 -- Coach holistic | 2 | 2 | 0 |
| Internal iteration 1 -- SE holistic | 6 | 5 | 1 |
| Internal iteration 1 -- DE holistic | 2 | 2 | 0 |
| Internal iteration 2 -- CR spec audit | 7 | 1 | 6 |
| Internal iteration 2 -- Coach holistic | 0 | 0 | 0 |
| Internal iteration 2 -- SE holistic | 6 | 3 | 3 |
| Internal iteration 2 -- DE holistic | 4 | 2 | 2 |
| Internal iteration 3 -- CR spec audit | 0 | 0 | 0 |
| Internal iteration 3 -- PM self-review | 2 | 2 | 0 |
| Codex iteration 1 | 6 | 4 | 2 |
| **Total** | **41** | **22** | **19** |

Note: Many dismissals in iterations 2-3 were duplicates of findings already incorporated from other reviewers in the same iteration.

- 2026-04-03: **Dispatch completed.** 3 stories delivered by SE. All ACs verified by PM. 226 tests passing, 0 failures.

### Implementation Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-199-01 | 4 | 4 | 0 |
| Per-story CR — E-199-02 | 0 | 0 | 0 |
| Per-story CR — E-199-03 | 1 | 1 | 0 |
| CR integration review | 1 | 1 | 0 |
| Codex code review | 3 | 3 | 0 |
| **Total** | **9** | **9** | **0** |

CR findings: E-199-01 had 2 MUST FIX (season_id on roster queries) + 2 SHOULD FIX (error-path test, team FPS% test). E-199-03 had 1 SHOULD FIX (play_events assertion). Integration had 1 SHOULD FIX (cleanup function rename). Codex: 2 high (auth expiry propagation, orphan cleanup scope) + 1 medium (missing tests). All fixed.

- 2026-04-03: **Documentation assessment**: Trigger 1 fires (new feature: plays-derived stats in reports). Trigger 5 fires (epic changes how users interact with reports -- new columns, new deletion behavior). Docs-writer dispatch warranted for `docs/coaching/` (new stats explanation) and `docs/admin/` (report deletion cascade behavior).

- 2026-04-03: **Context-layer assessment**:
  - T1 (New convention/pattern): **YES** -- `is_team_eligible_for_cleanup()` guard-condition pattern for conditional cascade deletion; consolidated `_cleanup_orphan_teams()` as the single FK-safe cascade function.
  - T2 (Architectural decision): **YES** -- Plays pipeline integrated into report generation flow (crawl → load → reconcile → query); report deletion now cascade-deletes team data with guard conditions.
  - T3 (Footgun/boundary discovered): **NO** -- No new footguns beyond what was already documented.
  - T4 (Agent behavior change): **NO** -- No changes to agent dispatch, routing, or coordination.
  - T5 (Domain knowledge): **YES** -- Coach consultation confirmed FPS% is "the first number I look at when scouting a pitching staff"; QAB% and P/PA are inline stats (no separate advanced section); plays endpoint is NOT ownership-gated.
  - T6 (New CLI/workflow): **NO** -- No new CLI commands or workflows added.

- 2026-04-03: **Status → COMPLETED.**
