# E-197: Derive season_id from Team Context

## Status
`COMPLETED`

## Overview
Fix season_id derivation so it comes from team metadata (season_year + program type) instead of the crawl directory path. Currently, all loaders derive season_id from the filesystem path or a single global config value, which produces wrong season tags when a team's real season differs from the crawl directory -- e.g., Lincoln Rebels 14U (2025 summer USSSA) had all 92 games tagged as `2026-spring-hs`. This epic decouples DB season_id from filesystem paths and corrects existing mis-tagged data.

## Background & Context
Promoted from [IDEA-061](/.project/ideas/IDEA-061-season-id-from-team-context.md).

The problem was discovered during plays data validation (E-195): players on multiple teams (like Kadyn Lichtenberg on both Rebels 14U and Freshman Grizzlies) had plays from different real seasons merged under the same season_id, making per-season validation and display impossible.

**Root cause**: Two season_id derivation patterns exist in the codebase, both wrong for multi-program setups:
1. **Constructor-injected** (GameLoader, ScheduleLoader, PlaysLoader, ScoutingLoader): season_id comes from `CrawlConfig.season` -- a single global value per pipeline run, not team-specific.
2. **Path-inferred** (RosterLoader, SeasonStatsLoader, SprayChartLoader, ScoutingSprayChartLoader): season_id parsed from the filesystem path (e.g., `data/raw/2026-spring-hs/teams/{uuid}/...`).

Additionally, `ScoutingCrawler._derive_season_id()` hardcodes `"spring-hs"` as the season suffix, making all scouting data tagged as HS regardless of actual program type.

A `warn_season_year_mismatch()` function in `src/gamechanger/loaders/__init__.py` already detects the mismatch but only logs a warning.

**Expert consultation** (SE): Confirmed ~12-15 source files affected. Identified that `PlaysLoader.load_game()` already reads season_id from the `games` table (not its constructor param), so fixing games cascades to new plays. Recommended a shared `derive_season_id_for_team()` utility.

**Expert consultation** (DE): Consulted on schema/migration strategy and season_id format. (Findings incorporated into Technical Notes.)

## Goals
- All loaders derive season_id from team metadata (`teams.season_year` + `programs.program_type`), not from filesystem paths or global config
- Existing mis-tagged data for Rebels 14U (and any other affected teams) is corrected via migration
- The `_ensure_season_row()` logic is consolidated into one shared function (currently duplicated in 4+ loaders)
- `warn_season_year_mismatch()` is replaced by correct derivation (the warning becomes unnecessary)

## Non-Goals
- Changing the crawl directory structure (filesystem paths remain an operator convenience)
- Changing how crawlers write files to disk (only DB inserts change)
- Adding new season metadata columns or restructuring the seasons table
- Fixing season_id for tracked opponents that have no `program_id` (they use a year-only fallback, which is correct for their context)
- Re-crawling existing cached data (loader changes only affect DB inserts, not file discovery)

## Success Criteria
- Running `bb data load` for the Rebels 14U team produces games/stats/plays tagged with `2025-summer-usssa`, not `2026-spring-hs`
- Running scouting sync for a tracked opponent produces the correct season_id based on the opponent's team metadata
- No loader derives season_id from a filesystem path or hardcoded suffix
- Existing Rebels 14U data in production is corrected by migration 011
- All existing tests pass; new tests cover the derivation utility and migration

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-197-01 | Canonical season_id derivation utility | DONE | None | - |
| E-197-02 | Update member-team loaders to use team-derived season_id | DONE | E-197-01 | - |
| E-197-03 | Update scouting pipeline loaders to use team-derived season_id | DONE | E-197-01, E-197-02 | - |
| E-197-04 | Data migration for existing mis-tagged season_id rows | DONE | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Architectural Decision -- Decouple Filesystem from DB season_id

The filesystem path (`data/raw/{season_slug}/teams/{uuid}/`) is for file organization and discovery. The DB `season_id` column is for data identity. These are decoupled:

- **Crawlers**: Continue writing to `data/raw/{config.season}/...` -- NO CHANGES.
- **File discovery**: Loaders continue finding files via paths constructed from config -- NO CHANGES.
- **DB inserts**: Loaders call `derive_season_id_for_team(db, team_id)` to get the correct season_id for INSERT/UPSERT operations. This is the ONLY change.

This means the same team's data may live in `data/raw/2026-spring-hs/teams/{uuid}/` on disk but be tagged as `2025-summer-usssa` in the database. This is correct and intentional.

### TN-2: season_id Derivation Logic

**Function**: `derive_season_id_for_team(db: sqlite3.Connection, team_id: int) -> str`

**Algorithm**:
1. Query `teams.season_year` and `programs.program_type` (via `teams.program_id → programs.program_id`).
2. Map `program_type` to season suffix:
   - `hs` → `spring-hs`
   - `usssa` → `summer-usssa`
   - `legion` → `summer-legion`
3. Construct: `{season_year}-{suffix}` (e.g., `2025-summer-usssa`).
4. **Fallbacks**:
   - NULL `season_year` → current calendar year
   - NULL `program_id` (no program association) → just `{season_year}` (no suffix)
   - Both NULL → `{current_year}`
5. **Error contract**: If `team_id` does not exist in the `teams` table, raise `ValueError`. All other cases (NULL program_id, NULL season_year, missing programs row) are handled via fallbacks, not errors.

**Location**: `src/gamechanger/loaders/__init__.py` (alongside existing `LoadResult` dataclass).

### TN-3: _ensure_season_row() Consolidation

Currently duplicated in loaders: `GameLoader`, `ScheduleLoader`, `RosterLoader`, `ScoutingLoader` (at minimum). `ScoutingCrawler` also has a copy but is out of scope for this epic (crawlers are unchanged per TN-1). All loader implementations parse the season_id slug to extract year and season_type, then INSERT OR IGNORE into `seasons`.

Consolidate into a single `ensure_season_row(db, season_id)` function in `src/gamechanger/loaders/__init__.py`. All loaders import from there. The consolidated function must handle:
- `{year}-{suffix}` format (e.g., `2025-summer-usssa`) -- extracts year and uses suffix as `season_type`
- Year-only format (e.g., `2026`) -- from teams with no `program_id`. Uses `"default"` as `season_type` since there is no suffix to derive a type from.

Both formats must produce valid `seasons` rows (the `season_type NOT NULL` constraint must be satisfied).

### TN-4: Legacy Function Disposition

**`warn_season_year_mismatch()`**: Once loaders derive season_id from team metadata, the mismatch warning is structurally impossible. The function and all its callers are removed in Stories 02/03 (NOT in Story 01 -- removing the function definition while callers still import it would cause ImportErrors in tests).

**`extract_year_from_season_id()`**: Has 5 live callers beyond the warning function (`schedule_loader.py` x3, `game_loader.py` x1, `scouting_loader.py` x1) that use it for team creation and opponent linking. These callers are replaced by `derive_season_id_for_team()` in Stories 02/03. The function definition is removed in Story 03 (after its last caller is eliminated). Do NOT remove it in Story 01.

### TN-5: PlaysLoader Special Case

`PlaysLoader.load_game()` reads `season_id` from the `games` table row (line 136 of `plays_loader.py`), not from its constructor parameter. This means:
- Once `GameLoader` writes the correct season_id to `games`, new plays loads automatically get the correct value.
- The `PlaysLoader` constructor still accepts `season_id` but it's unused for the actual DB writes. The constructor parameter should be removed (per Story 02 AC-4).
- **Existing** plays rows still have the wrong season_id and need migration correction (Story 04).

### TN-6: Data Migration Strategy (Migration 011)

**Note**: Migration numbered 011 because E-196 claims 010 (`010_add_game_start_time.sql`).

**Known correction**: Rebels 14U = team_id 126, current season_id = `2026-spring-hs`, correct = `2025-summer-usssa`.

**Affected team scope**: The migration must correct not just team 126 (Rebels 14U) but also any opponent data crawled through the scouting pipeline with the wrong season_id. The implementer should discover all affected team_ids by checking: (1) team 126 directly, and (2) opponents linked via `team_opponents WHERE our_team_id = 126` whose scouting data may also carry `season_id = '2026-spring-hs'`.

**Program prerequisite**: Rebels 14U currently has `program_id = NULL`. The derivation utility requires a program association to produce `2025-summer-usssa` (without it, it falls back to `"2025"`). The migration must create a USSSA program and assign team 126 to it.

**Migration steps**:
1. Prepend `PRAGMA foreign_keys=ON;` (required because `executescript()` resets connection state).
2. Create a USSSA program row (INSERT OR IGNORE): `program_id='rebels-usssa'`, `program_type='usssa'`, `name='Lincoln Rebels'`.
3. Assign team 126 to the program: `UPDATE teams SET program_id = 'rebels-usssa' WHERE id = 126 AND program_id IS NULL`.
4. Create the `2025-summer-usssa` season row (INSERT OR IGNORE) -- FK prerequisite for all UPDATEs.
3. UPDATE each table, scoped by team_id AND `season_id = '2026-spring-hs'` (the old value in WHERE clause ensures idempotency and precision):
   - `games` WHERE (home_team_id IN ({affected_ids}) OR away_team_id IN ({affected_ids})) AND season_id = '2026-spring-hs'
   - `plays` WHERE game_id IN (SELECT game_id FROM games WHERE season_id = '2025-summer-usssa') -- run AFTER games UPDATE
   - `player_season_batting` WHERE team_id IN ({affected_ids}) AND season_id = '2026-spring-hs'
   - `player_season_pitching` WHERE team_id IN ({affected_ids}) AND season_id = '2026-spring-hs'
   - `team_rosters` WHERE team_id IN ({affected_ids}) AND season_id = '2026-spring-hs'
   - `spray_charts` WHERE team_id IN ({affected_ids}) AND season_id = '2026-spring-hs' (note: `season_id` is nullable on this table)


**scouting_runs exclusion**: `scouting_runs.season_id` is NOT updated by this migration. Per TN-1, it is a file-discovery column (reflects the crawl directory path) and must remain `2026-spring-hs` so that `src/pipeline/trigger.py` and `src/reports/generator.py` can still locate crawled files on disk.

**Composite PK concern**: `team_rosters` has PK `(team_id, player_id, season_id)` and `player_season_batting`/`player_season_pitching` have UNIQUE constraints including `season_id`. Updating `season_id` changes the composite key. This is safe as long as no row with the new season_id already exists for the same player+team. Since `2025-summer-usssa` is a new season_id that has never been used, there will be no conflicts.

**Games table concern**: Games may involve both a member team and an opponent. The UPDATE should match on affected team_ids in either home or away position AND the old season_id value to be precise.

**Known cosmetic gap**: Existing `seasons` rows created before this epic (e.g., `2026-spring-hs`) will retain `season_type = 'unknown'` (the value written by the old `_ensure_season_row()` implementations). The new consolidated `ensure_season_row()` writes correct types for new rows, but does not backfill old ones. This is non-blocking -- the `seasons` table is used for FK existence checks, not season_type queries.

### TN-7: Affected File Inventory

**Story 01** (utility):
- `src/gamechanger/loaders/__init__.py` -- add new functions (keep both `warn_season_year_mismatch()` and `extract_year_from_season_id()` -- removed in Stories 02/03)
- `tests/test_season_id_derivation.py` -- new test file

**Story 02** (member-team loaders):
- `src/gamechanger/loaders/game_loader.py`
- `src/gamechanger/loaders/schedule_loader.py`
- `src/gamechanger/loaders/plays_loader.py`
- `src/gamechanger/loaders/roster.py`
- `src/gamechanger/loaders/season_stats_loader.py`
- `src/pipeline/load.py`
- Tests for each modified loader

**Story 03** (scouting pipeline):
- `src/gamechanger/loaders/__init__.py` -- remove `extract_year_from_season_id()` and `warn_season_year_mismatch()` (last callers eliminated)
- `src/gamechanger/loaders/scouting_loader.py`
- `src/gamechanger/loaders/spray_chart_loader.py`
- `src/gamechanger/loaders/scouting_spray_loader.py`
- `src/pipeline/trigger.py`
- `src/cli/data.py`
- `src/reports/generator.py` -- separate crawl-path season_id from DB season_id for stat queries
- `tests/test_trigger.py` -- remove `warn_season_year_mismatch` tests
- Tests for each modified loader

**Story 04** (migration):
- `migrations/011_fix_season_id_rebels_14u.sql`
- `tests/test_migration_011.py`

## Open Questions
- None remaining. All design decisions locked from consultation.

## History
- 2026-04-01: Created from IDEA-061. SE and DE consulted during discovery.
- 2026-04-01: Set to READY after 6 review passes (40 findings, 30 accepted, 5 dismissed, 5 duplicates/already-addressed).
- 2026-04-02: Set to ACTIVE, dispatch started.
- 2026-04-02: All 4 stories DONE. Epic COMPLETED. Decoupled DB season_id from filesystem paths across all loaders (member + scouting + spray), added canonical `derive_season_id_for_team()` utility, removed legacy `warn_season_year_mismatch()` and `extract_year_from_season_id()`, corrected Rebels 14U mis-tagged data via migration 011.

### Spec Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| DE pre-review consultation | 5 | 5 | 0 |
| Internal iteration 1 -- CR spec audit | 8 | 5 | 1 |
| Internal iteration 1 -- SE holistic | 9 | 7 | 1 |
| Internal iteration 1 -- DE holistic | 6 | 3 | 1 |
| Codex iteration 1 | 6 | 6 | 0 |
| Codex iteration 2 | 6 | 4 | 2 |
| **Total** | **40** | **30** | **5** |

Note: Some findings were duplicates across sources -- counts reflect raw finding count per source, not unique findings.

### Code Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-197-01 | 0 | 0 | 0 |
| Per-story CR -- E-197-02 | 2 | 2 | 0 |
| Per-story CR -- E-197-03 | 2 | 2 | 0 |
| Per-story CR -- E-197-04 | 2 | 0 | 2 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 2 | 2 | 0 |
| **Total** | **8** | **6** | **2** |

### Documentation Assessment

Reviewing against doc update triggers:
1. **New feature or endpoint**: No -- internal refactor, no new features or endpoints.
2. **Architecture or deployment config changes**: No -- no deployment changes.
3. **New agent or material agent modification**: No.
4. **Database schema changes**: Yes -- migration 011 (data correction only, no DDL). However, this is a data fix migration, not a structural schema change. The migration corrects existing mis-tagged rows and creates a USSSA program row. No new tables or columns.
5. **Epic changes how the system works or how users interact with it**: No -- internal loader refactor, invisible to users.

**Verdict**: Trigger 4 fires marginally (migration 011), but it is a data correction migration with no DDL changes. The data model section in CLAUDE.md already documents the `programs` table and `season_year` column. No documentation update required beyond what CLAUDE.md already covers. **No documentation impact.**

### Context-Layer Assessment

- **T1 (New convention)**: **YES** -- Filesystem path season_id is decoupled from DB season_id. Loaders use `derive_season_id_for_team()` for DB writes and filesystem paths for file discovery. `scouting_runs.season_id` is a file-discovery column, not a data identity column.
- **T2 (Architectural decision)**: **YES** -- `derive_season_id_for_team()` is the canonical season_id derivation utility. All loaders MUST use it for DB inserts. The `program_type → season suffix` mapping (`hs→spring-hs`, `usssa→summer-usssa`, `legion→summer-legion`) is codified.
- **T3 (Footgun discovered)**: **YES** -- `derive_season_id_for_team()` return type changed to `tuple[str, int | None]` during implementation (Story 03 needed `season_year` for `ensure_team_row()`). Callers must unpack the tuple.
- **T4 (Agent behavior change)**: **NO** -- No changes to agent routing, dispatch, or coordination.
- **T5 (Domain knowledge)**: **YES** -- `program_type → season suffix` mapping is domain knowledge. Teams without a `program_id` get year-only season_id (correct for tracked opponents). `scouting_runs.season_id` semantic distinction (file discovery vs data identity) is important for future pipeline work.
- **T6 (New CLI/workflow)**: **NO** -- No new commands or workflows.

**Verdict**: 4 YES triggers (T1, T2, T3, T5). Claude-architect should codify these findings before archival.

### Ideas Backlog Review

No CANDIDATE ideas are directly unblocked by E-197. IDEA-061 was already promoted to this epic. The season_id derivation fix enables correct multi-program data tagging but does not unblock any specific pending idea.

### Vision Signals

Unprocessed signals exist in `docs/vision-signals.md` (26+ signals as of last count). Mentioning for user awareness -- does not block archival.
