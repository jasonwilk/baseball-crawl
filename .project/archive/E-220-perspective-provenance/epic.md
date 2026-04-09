# E-220: Perspective-Aware Data Architecture

## Status
`COMPLETED`

## Overview
Make perspective provenance a first-class concept in the data model and pipeline. Every piece of player data records which team's API perspective produced it, pipeline runs cannot inherit stale cached files from previous runs, and cross-perspective contamination becomes structurally impossible. This replaces E-219 (own-side-only) with a more complete solution that preserves both perspectives rather than discarding one.

## Background & Context
GameChanger returns different identifiers (player UUIDs, game IDs, player names) depending on which team's perspective data is fetched from. This is permanent API behavior, not a bug. Four prior attempts addressed symptoms:

- **E-211**: UUID contamination prevention (stopped `root_team_id` from polluting `gc_uuid`)
- **E-215**: Player dedup merge (cleanup tool, blind to phantom players not on rosters)
- **E-216**: Cross-perspective game dedup (game-level, didn't address player side)
- **E-219**: Own-side-only boxscore loading (READY but never dispatched; discards opponent data)

All failed because none addressed root causes: (1) no perspective provenance on data rows, (2) no run isolation on the filesystem cache, (3) loaders merging two perspectives without tracking.

The user explicitly rejected the "discard opponent data" approach (E-219). Opponent-side data has real coaching value -- e.g., analyzing how opposing batters performed against a specific pitcher requires both sides. The user authorized a clean-slate database and filesystem wipe.

Expert consultations:
- **DE**: Option A -- `perspective_team_id` on all four stat tables; `game_perspectives` junction table; single new 001_initial_schema.sql (E-100 pattern); UNIQUE constraint changes.
- **SE**: Load both sides with perspective tagging; eliminate disk cache for scouting/reports pipeline (in-memory crawl-to-load); keep disk cache for own-team pipeline.
- **API Scout**: Confirmed field inventory. Stable: `event_id`, stat numbers (`game_stream_id` stability moot -- endpoints use `event_id`). Perspective-specific: player UUIDs, player names, `home_away`, score labels, boxscore keys. Public games `id` field: treat as potentially perspective-specific.
- **CA**: New `.claude/rules/perspective-provenance.md`; update data-model.md; minimal CLAUDE.md update. E-219 should be ABANDONED with forward reference.

## Goals
- Every player stat row (`player_game_batting`, `player_game_pitching`, `spray_charts`, `plays`) records `perspective_team_id` -- the team whose API call produced it
- Game rows track which perspectives have been loaded via a `game_perspectives` junction table
- Scouting and reports pipelines eliminate disk caching (crawl-to-load in-memory), removing the stale-file vector
- Cross-perspective contamination is structurally impossible: UNIQUE constraints include `perspective_team_id`
- Season aggregate computation filters by `perspective_team_id` to prevent double-counting
- Context layer codifies the perspective provenance principle as a permanent invariant

## Non-Goals
- Changing how game-level data (scores, dates, team rows) is loaded -- games remain one canonical row per real-world game
- Modifying the own-team crawl pipeline's disk cache (crawl and load are separate CLI invocations; not where the perspective bug lives)
- Adding new analytical features or dashboard views using perspective data (future work)
- Addressing `gc_athlete_profile_id` cross-team identity (E-104)
- Changing the public games endpoint's `id` field handling (treat as potentially perspective-specific per API Scout)
- Migrating existing data -- clean-slate rebuild authorized

## Success Criteria
- After a full rebuild (DB wipe + re-crawl), every `player_game_batting`, `player_game_pitching`, `spray_charts`, and `plays` row has a non-NULL `perspective_team_id`
- Loading the same game from two different team perspectives produces two sets of stat rows with different `perspective_team_id` values, not merged rows
- The scouting pipeline and report generator produce zero files in `data/raw/` for their crawl-load cycle
- Season aggregates for scouting teams are computed from own-perspective data only (no double-counting from opponent perspective)
- All existing tests pass (updated where they relied on perspective-free data loading)
- Context-layer rule prevents regression

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-220-01 | Schema rewrite with perspective provenance | DONE | None | - |
| E-220-02 | GameLoader perspective tagging | DONE | E-220-01 | - |
| E-220-03 | PlaysLoader perspective tagging | DONE | E-220-01 | - |
| E-220-04 | SprayChartLoader perspective tagging | DONE | E-220-01 | - |
| E-220-05 | ScoutingLoader in-memory pipeline | DONE | E-220-02, E-220-04 | - |
| E-220-06 | Report generator in-memory pipeline | DONE | E-220-05, E-220-10, E-220-03 | - |
| E-220-07 | Season aggregate perspective filtering | DONE | E-220-05 | - |
| E-220-08 | Perspective provenance context layer | DONE | E-220-05, E-220-07, E-220-10 | - |
| E-220-09 | Clean-slate rebuild procedure | DONE | E-220-05, E-220-06, E-220-07, E-220-10 | - |
| E-220-10 | Scouting spray in-memory pipeline | DONE | E-220-05, E-220-04 | - |

## Dispatch Team
- software-engineer
- data-engineer
- claude-architect

## Technical Notes

### TN-1: Perspective Provenance Schema Design (DE Consultation)
Add `perspective_team_id INTEGER NOT NULL REFERENCES teams(id)` to four stat tables: `player_game_batting`, `player_game_pitching`, `spray_charts`, `plays`. NOT on season aggregate tables (`player_season_batting`, `player_season_pitching`) -- filter at computation time.

**UNIQUE constraint changes** (critical):
- `player_game_batting`: `UNIQUE(game_id, player_id)` becomes `UNIQUE(game_id, player_id, perspective_team_id)`
- `player_game_pitching`: `UNIQUE(game_id, player_id)` becomes `UNIQUE(game_id, player_id, perspective_team_id)`
- `plays`: `UNIQUE(game_id, play_order)` becomes `UNIQUE(game_id, play_order, perspective_team_id)`
- `spray_charts`: add `UNIQUE(event_gc_id, perspective_team_id)` (event_gc_id column exists per migration 006)

New junction table:
```sql
CREATE TABLE game_perspectives (
    game_id TEXT NOT NULL REFERENCES games(game_id),
    perspective_team_id INTEGER NOT NULL REFERENCES teams(id),
    loaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (game_id, perspective_team_id)
);
```

Index: composite `(perspective_team_id, game_id)` on batting and pitching tables.

### TN-2: Clean-Slate Migration Strategy (DE Consultation)
Rewrite `001_initial_schema.sql` with all perspective columns baked in (E-100 pattern). Archive current migrations 001-015 to `.project/archive/migrations-pre-E220/`. The `perspective_team_id` column is `NOT NULL` with no default -- loaders must supply it. This makes contamination a hard failure (insertion error) rather than a silent default.

**Folded migrations**: The new 001 must incorporate all columns added by migrations 002-015: `users.role` (002), `crawl_jobs` table (003), `teams.season_year` (004), `teams.public_id` backfill (005), spray_charts indexes + `event_gc_id`/`created_at_ms`/`season_id` (006), `idx_teams_name_season_year` (007), `reports` table (008), `plays`/`play_events` tables (009), `season_id` fix (011 -- data-only, skip), `reconciliation_discrepancies` table (012), stale season_id fix (013 -- data-only, skip), `games.start_time`/`timezone` (014), `player_game_pitching.appearance_order` (015).

### TN-3: Loader Perspective Tagging (SE Consultation)
All loaders pass `perspective_team_id` on every INSERT. The value is always `owned_team_ref.id` -- the team whose API credentials or public_id were used to fetch the data. This is already available in every loader's constructor or method signature.

GameLoader continues to load both `own_data` AND `opp_data` from boxscores. Both sides get tagged with the same `perspective_team_id` (the team that fetched the boxscore). This preserves opponent data's coaching value while making provenance explicit.

**Player names**: Player names are perspective-specific (opponent players often appear as initials). The existing `ensure_player_row()` length-based name preference (longer name wins; "Unknown" treated as length 0) handles this correctly -- when the player's own team loads their full name, it overwrites any initial-only name from an opponent perspective. No additional handling needed.

### TN-4: In-Memory Pipeline for Scouting/Reports (SE Consultation)
The scouting pipeline and report generator currently use disk as an intermediate cache: crawlers write JSON to `data/raw/`, loaders read from disk. This is the primary vector for run-isolation failures.

**Fix**: Crawlers return data in-memory (dicts/lists). Loaders consume directly from the returned data rather than reading files. Game IDs come from crawl results, not filesystem globs. The own-team pipeline (member sync) retains disk caching because its crawl and load are separate CLI invocations.

### TN-5: Season Aggregate Filtering (SE/DE Consultation)
`ScoutingLoader._compute_season_aggregates()` currently aggregates all `player_game_batting`/`player_game_pitching` rows for a team_id+season_id. After this epic, it must also filter by `WHERE perspective_team_id = ?` to prevent double-counting when the same game has been loaded from multiple perspectives.

### TN-6: Perspective-Specific vs. Stable Fields (API Scout Consultation)
**Stable across perspectives**: `event_id` (= `game_stream.game_id`), stat numbers (scores, batting/pitching lines). Note: `game_stream_id` stability is moot for this epic -- all endpoints that need a game identifier use `event_id` as the path parameter (boxscore, plays).

**Perspective-specific**: player UUIDs, player names (initials vs. full), `home_away`, `owning_team_score`/`opponent_team_score` labels, boxscore top-level keys (slug vs. UUID), `team_players` keys in plays data, `game_stream.opponent_id`.

**Uncertain**: Public games `id` field -- treat as potentially perspective-specific.

### TN-7: Game Dedup Compatibility
`GameLoader._find_duplicate_game()` continues to merge cross-perspective games into one canonical `game_id`. This is correct: one real-world game = one `games` row. The new `game_perspectives` table tracks which perspectives have loaded data for each game. Stat rows differentiate via `perspective_team_id`.

### TN-8: E-219 Technical Notes Absorption
E-219's TN-1 (cross-perspective UUID behavior), TN-2 (high-risk endpoints), TN-3 (flow collision pairs), and TN-4 (plays loader assessment) are absorbed into this epic's technical notes. E-219 will be marked ABANDONED with a forward reference to E-220.

### TN-9: Dedup Infrastructure
The existing dedup infrastructure (`dedup_team_players()` hooks in ScoutingLoader and trigger.py, `find_duplicate_players()`, `bb data dedup-players` CLI) should be retained. It serves two purposes: (1) cross-perspective cleanup (reduced but not eliminated -- plays loader still creates stubs), and (2) genuine name-variant dedup. Assessment of simplification opportunities is deferred to a follow-up idea.

### TN-10: Report Generator Disk Independence
The report generator currently:
- Discovers games from boxscore filenames on disk (`generator.py:568`)
- Skips plays fetch if a file exists on disk (`generator.py:588-590`)

After this epic, game discovery comes from crawl results in memory. No file-existence checks. The report generator's scouting crawl+load cycle becomes a single in-memory operation.

### TN-11: Reconciliation Engine Perspective Awareness
The reconciliation engine (`src/reconciliation/engine.py`) queries `plays` rows by `game_id`. After this epic, a game may have plays from multiple perspectives. The reconciliation engine should be assessed for perspective-awareness in a follow-up. This is not a blocker: reconciliation runs on own-team games where typically only one perspective exists. Capture as a follow-up idea if perspective collisions are observed.

### TN-12: In-Memory Crawl Result Shape
The scouting crawler's in-memory return should be a dataclass (or equivalent) containing:
- `games`: list of game dicts (from public games endpoint)
- `roster`: list of player dicts (from public roster endpoint)
- `boxscores`: dict mapping game identifier to boxscore dict
- `season_id`: the crawl-derived season slug

The scouting spray crawler returns a similar structure with spray chart data. Stories E-220-05, E-220-06, and E-220-10 must consume this interface. The exact field names are implementation decisions for the implementing agent.

### TN-13: ON CONFLICT Clause Cascade (Critical)
The current `GameLoader._upsert_batting()` and `_upsert_pitching()` use `ON CONFLICT(game_id, player_id) DO UPDATE`. After E-220-01 changes the UNIQUE constraint to `(game_id, player_id, perspective_team_id)`, these ON CONFLICT clauses reference a non-existent 2-column constraint and will fail at runtime. E-220-02 MUST update all ON CONFLICT clauses to reference the new 3-column constraint: `ON CONFLICT(game_id, player_id, perspective_team_id) DO UPDATE`. Similarly, `PlaysLoader` ON CONFLICT on `(game_id, play_order)` must become `(game_id, play_order, perspective_team_id)` in E-220-03, and spray chart INSERT OR IGNORE keyed on `event_gc_id` must include `perspective_team_id` in E-220-04.

### TN-14: CrawlResult Replacement for In-Memory Pipeline
The current `ScoutingCrawler.scout_team()` returns a `CrawlResult` dataclass with disk-oriented fields (`files_written`, `files_skipped`). Multiple callers branch on these fields (`trigger.py` lines ~692-701, `generator.py`, CLI). The in-memory pipeline (E-220-05) needs a new return type that carries the actual data plus status metadata. The `CrawlResult` fields are no longer meaningful when no files are written. E-220-05 must define what replaces `CrawlResult` and update all callers that branch on its fields.

### TN-15: Crawler DB Side Effects Are Preserved
`ScoutingCrawler.scout_team()` writes to `scouting_runs`, `teams`, and `seasons` tables during the crawl phase. "Eliminate disk cache" means removing file writes (`data/raw/` JSON files) only. All database side effects (status tracking, team/season row creation) must be preserved in the in-memory pipeline.

## Open Questions
- None -- problem, root cause, fix strategy, and expert recommendations are fully specified.

## History
- 2026-04-08: Created (replaces E-219 own-side-only approach)
- Expert consultations: DE (schema), SE (loaders/cache), API Scout (field inventory), CA (context layer)
- 2026-04-08: Internal review iteration 1. 6 reviewers (CR, PM, DE, SE, CA, API Scout), 37 findings total (31 accepted, 2 dismissed, 4 N/A). Key changes: E-220-05 split (spray pipeline moved to new E-220-10), E-220-06 dependency on E-220-05 added, member pipeline ACs added to E-220-02/03/04, E-220-09 reframed as docs-only, spray_charts UNIQUE made unconditional, TN-2 folded migration inventory added, TN-3 player name handling noted, TN-6 game_stream_id stability corrected, TN-11 (reconciliation follow-up) and TN-12 (in-memory result shape) added, E-220-08 architecture-subsystems.md scope added.
- 2026-04-08: CR holistic review iteration 2. 7 findings, all accepted. Key additions: TN-13 (ON CONFLICT clause cascade -- critical runtime trap), TN-14 (CrawlResult dataclass replacement), TN-15 (crawler DB side effects preserved). ON CONFLICT ACs added to E-220-02/03/04. CrawlResult and DB side effects ACs added to E-220-05. team_id == perspective_team_id assumption documented in E-220-07.
- 2026-04-08: Codex spec review iteration 1. 4 findings (3 P1, 1 P2), all accepted. E-220-01 AC-7 rewritten (resolved conflict with TN-2 folded migrations), AC-8 added enumerating folded columns. E-220-05 breaking-change note added (report generator broken until E-220-06). E-220-06 AC-7 added (restore report generator). E-220-08 dependencies changed from E-220-02 to E-220-05/07/10 (must describe final state). E-220-07 AC-4 narrowed to documented assessment list (not unbounded audit).
- 2026-04-08: Codex spec review iteration 2. 5 findings (4 P1, 1 P2): 2 accepted, 3 dismissed (verified already fixed in iteration 1). E-220-06 dependency on E-220-10 added (report generator uses spray APIs). E-220-01 AC-5 now enumerates all 14 migration files by exact name.
- 2026-04-08: Internal review iteration 2. 7 findings (6 minor + 1 CR HR2-1 spray CLI), all accepted. E-220-02 Blocks trimmed (E-220-08 removed). E-220-10 Blocks expanded (E-220-06, E-220-08, E-220-09). E-220-08 AC-5 scope widened (scouting + reports sections). Epic consultation summary corrected (game_stream_id stability moot). TN ordering fixed (TN-12 moved before TN-13). E-220-10 handoff note added (read post-E-220-05 code). E-220-10 AC-6 added (standalone spray CLI commands), Files list expanded (spray_chart.py, crawl.py).
- 2026-04-08: READY after 5 review passes (60 findings: 51 accepted, 5 dismissed, 4 N/A).
- 2026-04-08: ACTIVE -- dispatch begun.
- 2026-04-08: COMPLETED -- all 10 stories DONE. Perspective provenance is now a first-class concept: `perspective_team_id` on all 4 stat tables, `game_perspectives` junction table, in-memory scouting/reports pipelines (no disk intermediary), perspective-filtered season aggregates, context-layer rule codified, clean-slate rebuild procedure documented.
- 2026-04-09: Reverted from COMPLETED to ACTIVE. Post-dispatch integration review found read-side perspective filtering gaps in player_dedup.py, api/db.py, and reports/generator.py that violate the core invariant. Remediation in progress.
- 2026-04-09: Eight rounds of post-dispatch Codex remediation. The core architectural contribution -- perspective_team_id as first-class NOT NULL on the four stat tables, game_perspectives junction, in-memory scouting/reports pipelines, consolidated single-migration schema with 14 prior migrations archived -- is intact and shipped. Rounds 1-7 closed 50+ integration gaps (helpers that took game_id/team_id without the perspective dimension) plus one round-6-induced regression (cluster 2's cascade_delete_team FK violation resolved in round 7). Round 7 also added perspective_team_id to reconciliation_discrepancies (dual-column with participant team_id, preserving home-vs-away distinction for cancellation detection) and fixed a latent round-6 over-preservation bug in the report cleanup helper as a side effect. Round 8 surfaced 3 remaining P1s (cluster 3 Phase 1a incompleteness in admin delete cascade, Phase 1b missing reconciliation_discrepancies cleanup, bb data reconcile --game-id not plumbing perspective) plus evidence that 7 test files use inline fixtures that do not enforce production FK constraints -- the enabling condition for the round-by-round discovery cascade. User chose to ship E-220 with residuals captured as E-221 rather than grind round 9; diminishing returns were clear by round 7, and round 6's own regression showed that continuing to patch was risking new bugs. Final test baseline: 72F/4254P/16E (same 72 pre-existing failures and 16 errors as E-220 pre-dispatch baseline; zero regression from the 8 rounds of remediation, +1 new passing test from the round 7 cross-perspective discrepancy test). Documentation assessment: no documentation impact -- all changes are invariant-layer and test infrastructure, not user-facing features or APIs. Context-layer assessment: (1) new convention/pattern = YES (perspective provenance invariant codified in .claude/rules/perspective-provenance.md during dispatch); (2) architectural decision with ongoing implications = YES (single-migration rewrite pattern reinforced as canonical, dual-column provenance+participant semantics for reconciliation_discrepancies); (3) footgun/failure mode = YES (per-story CR is insufficient for cross-cutting invariants, test fixtures are part of the invariant, executescript() PRAGMA pitfall for FK enforcement -- captured in .claude/rules/migrations.md); (4) agent behavior/routing change = NO; (5) domain knowledge = YES (cross-perspective rows are the MODAL case for LSB-adjacent tracked opponents, not rare -- policy decisions that depend on frequency need grounded input before locking); (6) new CLI/workflow = NO. CA assessment of per-trigger codification deferred to E-221 close or ad-hoc CA dispatch. Residuals captured in E-221 (round 8 P1-1/P1-2/P1-3 + full test fixture schema parity audit + CI guardrail).
- 2026-04-09: COMPLETED with residuals -- see E-221 for the landing spot.

### Planning Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 (CR + DE + SE + CA + API Scout + PM) | 37 | 31 | 2 |
| CR holistic review | 7 | 7 | 0 |
| Codex spec review iteration 1 | 4 | 4 | 0 |
| Codex spec review iteration 2 | 5 | 2 | 3 |
| Internal iteration 2 (CR + DE + SE + CA + API Scout + PM) | 7 | 7 | 0 |
| **Total** | **60** | **51** | **5** |

### Dispatch Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-220-01 | 17 | 17 | 0 |
| Per-story CR -- E-220-02 | 1 | 1 | 0 |
| Per-story CR -- E-220-03 | 0 | 0 | 0 |
| Per-story CR -- E-220-04 | 0 | 0 | 0 |
| Per-story CR -- E-220-05 | 3 | 3 | 0 |
| Per-story CR -- E-220-06 | 0 | 0 | 0 |
| Per-story CR -- E-220-07 | 0 | 0 | 0 |
| Per-story CR -- E-220-10 | 2 | 2 | 0 |
| **Total** | **23** | **23** | **0** |

(E-220-08, E-220-09 were context-layer/docs-only -- no CR.)
