# Code Review: Data Pipeline -- Loaders & Schema

**Reviewer**: code-reviewer agent
**Date**: 2026-03-17
**Scope**: All loaders (`src/gamechanger/loaders/`), database layer (`src/db/`, `migrations/`), query layer (`src/api/db.py`), and associated tests.
**Tests**: 352 tests pass (all in-scope test files).

---

## Critical Issues

### C-1: Game loader drops `R` (runs) from batting -- schema has the column but loader skips it
**Files**: `src/gamechanger/loaders/game_loader.py:79`, `migrations/001_initial_schema.sql:162`

The schema defines `player_game_batting.r INTEGER` (runs scored), and the boxscore API provides `"R"` in batting stats. However, `game_loader.py` explicitly puts `"R"` in the `_BATTING_SKIP_DEBUG` set (line 79) with the comment `"R" is not in the schema`. This is wrong -- `R` IS in the schema (line 162: `r INTEGER`). Runs scored per game are silently discarded every time a boxscore is loaded. This is a data loss bug.

Similarly, `"TB"` (total bases) is in `_BATTING_SKIP_DEBUG` and also in `_BATTING_EXTRAS_SKIP_DEBUG` -- but the schema has `tb INTEGER` on `player_game_batting` (line 173). Total bases are silently discarded.

Additionally, `"HBP"`, `"CS"`, `"E"` are in `_BATTING_EXTRAS_SKIP_DEBUG` (line 89) but all three have columns in the schema (`hbp`, `cs`, `e` at lines 172-176). These batting extras are silently dropped.

**Impact**: Every boxscore load discards 5 stat columns that exist in the schema. This is the most significant finding.

### C-2: Game loader drops pitching extras that the schema has columns for
**Files**: `src/gamechanger/loaders/game_loader.py:102`, `migrations/001_initial_schema.sql:203-207`

`_PITCHING_EXTRAS_SKIP_DEBUG` (line 102) contains `"WP"`, `"HBP"`, `"#P"`, `"TS"`, `"BF"`, `"HR"` -- all are listed as "not in schema." But the schema defines: `wp INTEGER` (line 203), `hbp INTEGER` (line 204), `pitches INTEGER` (line 205), `total_strikes INTEGER` (line 206), `bf INTEGER` (line 207). Five of the six "skipped" extras have schema columns. Only `"HR"` is correctly excluded (per the schema comment at line 185).

Additionally, `"R"` (total runs allowed) is in `_PITCHING_SKIP_DEBUG` but the schema has `r INTEGER` (line 198).

**Impact**: Per-game pitching stats for WP, HBP, pitches, total strikes, BF, and R are all silently discarded.

### C-3: `_PlayerPitching` dataclass has an `hr` field but the loader never writes it to the DB
**File**: `src/gamechanger/loaders/game_loader.py:159, 884-907`

The `_PlayerPitching` dataclass includes `hr: int = 0` (line 159), but the `_upsert_pitching` SQL (lines 884-907) does not include `hr` in the INSERT or UPDATE columns. This field is populated from `_PITCHING_EXTRAS_SKIP_DEBUG` processing -- but since `"HR"` is in the skip set, it is never set. The field exists on the dataclass but is dead code. Not harmful on its own, but misleading.

---

## High Priority

### H-1: `apply_migration()` uses `executescript()` which auto-commits, defeating explicit transaction control
**File**: `migrations/apply_migrations.py:130-140`

`executescript()` implicitly commits any pending transaction before executing and runs each statement in its own implicit transaction. The `try/except` with `conn.rollback()` on line 138 is misleading -- if `executescript()` partially succeeds before failing, those statements are already committed and `rollback()` does nothing. The code appears to provide transactional safety but does not.

For a single-migration project (001_initial_schema.sql using all `IF NOT EXISTS`), this is low risk today. But if a future migration adds data-modifying statements alongside DDL, partial application becomes a real concern.

### H-2: `_ensure_season_row()` is duplicated across 3 loaders with identical logic
**Files**: `src/gamechanger/loaders/game_loader.py:960-980`, `src/gamechanger/loaders/scouting_loader.py:468-487`, `src/gamechanger/loaders/roster.py:344-372`, `src/gamechanger/loaders/season_stats_loader.py:416-439`

The `_ensure_season_row()` method is copy-pasted identically in `GameLoader`, `ScoutingLoader`, `RosterLoader`, and `SeasonStatsLoader`. Same logic, same best-effort year parsing, same INSERT ON CONFLICT DO NOTHING. This is a DRY violation across four files.

Similarly, `_ensure_team_row()` is duplicated in `RosterLoader`, `SeasonStatsLoader`, and `GameLoader` with essentially identical logic.

### H-3: No test file exists for `scouting_loader.py`
**File**: `tests/test_loaders/test_scouting_loader.py` -- does not exist

The scouting loader (`src/gamechanger/loaders/scouting_loader.py`) has zero dedicated test coverage. It contains significant logic:
- Roster loading
- Games index building (different format from game_summaries.json)
- Season aggregate computation (batting and pitching)
- UUID opportunism
- Delegation to GameLoader

The season aggregate computation is particularly important to test because it joins `player_game_batting` with `games` to filter by season -- exactly the pattern prone to wrong-scope bugs.

### H-4: Season aggregate queries correctly filter by `team_id` AND `season_id`, but test coverage is zero
**Files**: `src/gamechanger/loaders/scouting_loader.py:342-386, 388-430`

`_compute_batting_aggregates()` and `_compute_pitching_aggregates()` both JOIN through `games` to filter by season_id (correct per the SQL Dimension Audit pattern). However, since there are no tests, there is no verification that these queries produce correct results or that they don't silently cross-scope.

### H-5: `scouting_loader._load_roster()` duplicates logic from `roster.py`
**File**: `src/gamechanger/loaders/scouting_loader.py:246-282`

The scouting loader has its own `_load_roster()` and `_upsert_roster_player()` methods that duplicate the player/roster upsert pattern from `RosterLoader`. The scouting version is simpler (no field validation, no unknown field logging) but performs the same DB operations. If one is updated and the other is not, behavior diverges.

### H-6: `backup_database()` uses `shutil.copy2()` on a potentially active WAL-mode database
**File**: `src/db/backup.py:68`

`shutil.copy2()` does a simple file copy. For a WAL-mode SQLite database that may be actively written to, this can produce a corrupt backup because it does not checkpoint the WAL file or use SQLite's backup API. The `-wal` and `-shm` sidecar files are not copied. The `sqlite3.Connection.backup()` method would be the safe approach.

---

## Medium Priority

### M-1: `src/db/__init__.py` is missing `from __future__ import annotations`
**File**: `src/db/__init__.py:1`

The file is a one-line docstring, so there is no functional impact, but the project convention requires `from __future__ import annotations` at the top of every module (per `python-style.md`).

### M-2: `_UUID_RE` is duplicated in `game_loader.py` and `scouting_loader.py`
**Files**: `src/gamechanger/loaders/game_loader.py:64-67`, `src/gamechanger/loaders/scouting_loader.py:56-59`

Identical regex compiled twice. Minor DRY issue, but worth consolidating since both are in the same package.

### M-3: `RosterLoader._upsert_roster_membership()` docstring says `INSERT OR IGNORE` but uses `ON CONFLICT DO UPDATE`
**File**: `src/gamechanger/loaders/roster.py:289-308`

The docstring (line 291) states "Uses ``INSERT OR IGNORE`` so re-running is idempotent" but the actual SQL (lines 299-304) uses `ON CONFLICT(team_id, player_id, season_id) DO UPDATE SET jersey_number = excluded.jersey_number, position = excluded.position`. The behavior is correct (update on conflict, which is better than ignore), but the documentation is wrong.

### M-4: `SeasonStatsLoader._upsert_batting()` stores only 10 of 50+ available batting stat columns
**File**: `src/gamechanger/loaders/season_stats_loader.py:257-290`

The season-stats API provides dozens of batting stats (PA, singles, SOL, HBP, SHB, SHF, GIDP, ROE, FC, CI, PIK, CS, TB, XBH, LOB, QAB, HARD, WEAK, etc.) and the schema has columns for all of them. But the loader only maps: GP, AB, H, 2B, 3B, HR, RBI, BB, SO, SB. All other stats from the API response are silently discarded. This is the same class of issue as C-1/C-2 but for the season-stats endpoint.

The schema was designed to "store every GC stat" (per project feedback memory), but the loader does not implement this.

### M-5: `SeasonStatsLoader._upsert_pitching()` similarly stores only 10 of 40+ available pitching stat columns
**File**: `src/gamechanger/loaders/season_stats_loader.py:300-356`

Only maps: GP:P, IP, H, ER, BB, SO, HR, #P, TS. Many available stats (W, L, SV, BS, BF, WP, HBP, BK, etc.) are discarded.

### M-6: `games.game_stream_id` is never populated by either loader
**Files**: `src/gamechanger/loaders/game_loader.py:803-818`, `migrations/001_initial_schema.sql:135`

The schema has `game_stream_id TEXT` on the `games` table (line 135), and the game loader has the `game_stream_id` available (from the boxscore filename and the summaries index). But the `_upsert_game()` INSERT does not include `game_stream_id` -- it is always NULL. This means the downstream plays and boxscore endpoints cannot be linked back to games without re-deriving the mapping.

### M-7: `load_seed()` in `reset.py` uses f-string for table name in SQL
**File**: `src/db/reset.py:141-142`

```python
count: int = conn.execute(
    f"SELECT COUNT(*) FROM {table};"  # noqa: S608
).fetchone()[0]
```

The `noqa` comment acknowledges the risk. The table names come from `sqlite_master` (not user input), so this is safe in practice. But the pattern sets a precedent that could be copied elsewhere. Minor concern.

### M-8: `get_team_batting_stats()` default season_id is hardcoded to `"2026-spring-hs"`
**File**: `src/api/db.py:60`

The default parameter `season_id: str = "2026-spring-hs"` embeds a specific season. This will need to be updated every season or made dynamic. Same issue in `get_team_pitching_stats()` (line 143).

### M-9: `test_schema.py` and `test_schema_queries.py` use `sys.path.insert()` in test files
**Files**: `tests/test_schema.py:30-31`, `tests/test_schema_queries.py:30-31`

```python
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
```

The python-style rules say "No `sys.path` manipulation in `src/` modules" -- tests are not `src/`, so this is technically not a violation. However, with the editable install, these `sys.path` inserts are unnecessary and add noise. Several test files (`test_scouting_schema.py`, `test_e100_schema.py`, `test_migrations.py`, `test_migration_001_auth.py`) also do this. The loader test files do NOT do this, showing the pattern is inconsistent.

### M-10: `player_season_pitching` has two `gp` columns with different semantics
**File**: `migrations/001_initial_schema.sql:301, 325`

Line 301: `gp_pitcher INTEGER,  -- games pitched`
Line 325: `gp INTEGER,  -- games played (all roles)`

Both exist on `player_season_pitching`. The scouting loader's `_compute_pitching_aggregates()` sets `gp_pitcher = games_tracked` (the COUNT of per-game pitching rows), which conflates "games where the player pitched and we have data" with "games pitched per the season-stats API." The `gp` column is never set by any loader.

---

## Low Priority

### L-1: `GameSummaryEntry` is imported from `game_loader` by `scouting_loader` -- consider promoting to the package
**File**: `src/gamechanger/loaders/scouting_loader.py:50`

`GameSummaryEntry` is used across two modules. Moving it to `src/gamechanger/loaders/__init__.py` (alongside `LoadResult`) would be cleaner.

### L-2: `_PlayerBatting` and `_PlayerPitching` dataclasses could live in a shared module
**File**: `src/gamechanger/loaders/game_loader.py:134-160`

These are private to `game_loader.py` currently, so no immediate issue. Just a note for future refactoring if the dataclasses grow.

### L-3: Some test files use `Generator` from `typing` for fixtures
**Files**: `tests/test_scouting_schema.py:26`, `tests/test_e100_schema.py:27`

With `from __future__ import annotations`, `Generator` from `collections.abc` is preferred over `typing.Generator`. Minor style issue.

### L-4: `test_db.py` uses `reload(db_module)` pattern extensively
**File**: `tests/test_db.py` (multiple locations)

The `reload()` calls are needed because `get_db_path()` reads env vars at call time, but the module-level `_DEFAULT_DB_PATH` is evaluated at import time. The pattern works but is fragile -- any new module-level state that caches env vars would need the same treatment.

---

## Positive Observations

### P-1: Parameterized SQL throughout -- no SQL injection risk
All database operations across all loaders and the query layer use parameterized queries (`?` placeholders). The only f-string SQL is the `load_seed()` table-name interpolation, which sources table names from `sqlite_master` (safe). This is excellent.

### P-2: Comprehensive FK prerequisite handling
All loaders (`GameLoader`, `RosterLoader`, `SeasonStatsLoader`, `ScoutingLoader`) ensure FK prerequisite rows (teams, seasons, players) exist before inserting stat rows. This prevents FK constraint violations when loading data with unknown references. The pattern is consistent across all loaders.

### P-3: Idempotent upserts everywhere
All loaders use `ON CONFLICT DO UPDATE` or `ON CONFLICT DO NOTHING` consistently. Tests verify idempotency (load twice, verify same state). This is a strong foundation for a pipeline that re-runs.

### P-4: Schema design is thorough and well-documented
The `001_initial_schema.sql` file has excellent header comments explaining conventions (IP_OUTS, ID CONVENTION, CLASSIFICATION CHECK, TIMESTAMP FORMAT). Columns are documented inline. The schema covers the full breadth of stats the project needs.

### P-5: Test coverage for loaders is strong (where tests exist)
`test_game_loader.py` has 34 tests covering 8 acceptance criteria plus edge cases. `test_roster_loader.py` has comprehensive coverage including cross-team player scenarios. `test_season_stats_loader.py` covers IP conversion, stub players, position player filtering, and idempotency. The test quality is high.

### P-6: Migration system is simple and correct
`apply_migrations.py` is a straightforward, idempotent migration runner. The `_migrations` tracking table, file discovery, and ordered application are all correct. Tests verify idempotency and WAL mode.

### P-7: Partial unique indexes for nullable external IDs
Using `CREATE UNIQUE INDEX ... WHERE gc_uuid IS NOT NULL` allows multiple NULL values while enforcing uniqueness for non-NULL values. This is the correct approach for SQLite.

### P-8: Schema tests are exceptionally thorough
Seven test files verify the schema from different angles: table existence, column presence, constraint enforcement, index existence, query correctness, auth table structure, and migration idempotency. This level of schema test coverage is rare and valuable.
