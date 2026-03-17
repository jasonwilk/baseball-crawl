# CR4 Verification: Data Pipeline -- Loaders & Schema

**Verifier**: data-engineer agent
**Date**: 2026-03-17
**Source**: `.project/research/full-code-review/cr4-loaders-schema.md`

---

## Critical Issues

### C-1 — Game loader drops `R` (runs) from batting -- schema has the column but loader skips it
**Verdict**: CONFIRMED
**Evidence**: `game_loader.py:78-79` has `_BATTING_SKIP_DEBUG = {"R", "TB"}` with the comment `"R" is not in the schema`. Schema at `001_initial_schema.sql:162` defines `r INTEGER` on `player_game_batting`. Similarly, `_BATTING_EXTRAS_SKIP_DEBUG = {"TB", "HBP", "CS", "E"}` at line 89 -- all four have schema columns: `tb` (line 171), `hbp` (line 172), `cs` (line 175), `e` (line 176). Five stat columns silently discarded.
**Notes**: **OVERLAP: Fully covered by E-117-01** (game loader full boxscore stat coverage). E-117 epic Success Criteria explicitly lists all five columns. The stale "not in schema" comments are also in E-117 scope (goal: "stale comments corrected or removed").

### C-2 — Game loader drops pitching extras that the schema has columns for
**Verdict**: CONFIRMED
**Evidence**: `game_loader.py:102` has `_PITCHING_EXTRAS_SKIP_DEBUG = {"WP", "HBP", "#P", "TS", "BF", "HR"}`. Schema at `001_initial_schema.sql:203-207` defines `wp`, `hbp`, `pitches`, `total_strikes`, `bf`. Five of six are real columns. `_PITCHING_SKIP_DEBUG = {"R"}` at line 100 -- schema has `r INTEGER` at line 198. Only `HR` is correctly excluded (line 185 comment: "HR allowed not present in boxscore pitching extras").
**Notes**: **OVERLAP: Fully covered by E-117-01.** E-117 epic column inventory confirms 6 missing pitching columns (r, wp, hbp, pitches, total_strikes, bf). HR exclusion is intentional per E-100 Technical Notes. Also overlaps with **E-122 Non-Goals** (TN-1 explicitly defers pitching data loss to E-117-01).

### C-3 — `_PlayerPitching` dataclass has `hr` field but loader never writes it to DB
**Verdict**: CONFIRMED
**Evidence**: `game_loader.py:159` defines `hr: int = 0` on `_PlayerPitching`. The `_upsert_pitching` SQL at lines 884-907 lists only `ip_outs, h, er, bb, so` -- no `hr`. Since `"HR"` is in `_PITCHING_EXTRAS_SKIP_DEBUG`, the field is never populated anyway. Dead code.
**Notes**: **OVERLAP: Covered by E-117-01 AC-13** ("Remove dead `_PlayerPitching.hr` field"). E-122 Non-Goals also explicitly exclude this.

---

## High Priority

### H-1 — `apply_migration()` uses `executescript()` which auto-commits
**Verdict**: CONFIRMED
**Evidence**: `apply_migrations.py:130` calls `conn.executescript(sql)`. Python docs confirm `executescript()` implicitly issues a `COMMIT` before executing statements. The `conn.rollback()` at line 138 is therefore ineffective for partial failures within the script. However, the reviewer correctly notes this is low risk today -- with only `001_initial_schema.sql` using all `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`, partial application is safe because re-running is idempotent.
**Notes**: Real issue but severity is LOW in current state. Would become HIGH if a future migration includes data-modifying DML. The fix is to use `conn.execute()` per-statement or switch to `conn.backup()` + WAL checkpoint before migration. Not covered by E-117 or E-122.

### H-2 — `_ensure_season_row()` is duplicated across 4 loaders
**Verdict**: CONFIRMED
**Evidence**: Identical logic in:
- `game_loader.py:960-980`
- `scouting_loader.py:468-487`
- `roster.py:344-372`
- `season_stats_loader.py:416-439`

All four parse season_id, extract year, INSERT OR IGNORE with same SQL. `_ensure_team_row()` is similarly duplicated. This is a genuine DRY violation.
**Notes**: Not covered by E-117 or E-122. Refactoring would move these to a shared `src/gamechanger/loaders/helpers.py` or a base class. Low urgency -- the code works correctly, just maintenance cost.

### H-3 — No test file exists for `scouting_loader.py`
**Verdict**: FALSE POSITIVE
**Evidence**: `tests/test_scouting_loader.py` EXISTS (confirmed via glob). File header shows it covers: roster upsert, GameLoader delegation, season aggregate computation, idempotency, scouting_runs metadata, UUID opportunism, and FK-safe stub player pattern. The reviewer stated "does not exist" -- this is incorrect.
**Notes**: The file was likely added after the reviewer took their snapshot, or the reviewer searched in the wrong location (`tests/test_loaders/test_scouting_loader.py` vs `tests/test_scouting_loader.py`). The test file is at the project's standard location (`tests/test_scouting_loader.py`), not in a `test_loaders/` subdirectory.

### H-4 — Season aggregate queries filter correctly but have zero test coverage
**Verdict**: FALSE POSITIVE
**Evidence**: Since H-3 is false (tests DO exist), the aggregate queries at `scouting_loader.py:342-386` and `388-430` ARE tested. `test_scouting_loader.py` header explicitly lists "Season aggregate computation (counting stat sums, rate stats NOT stored)" as covered. The E-120-02 story also added `test_aggregate_isolated_per_team` specifically for cross-scope verification.
**Notes**: Coverage exists. The reviewer's premise (H-3) was wrong, invalidating H-4.

### H-5 — `scouting_loader._load_roster()` duplicates logic from `roster.py`
**Verdict**: CONFIRMED
**Evidence**: `scouting_loader.py:246-282` implements its own `_load_roster()` and `_upsert_roster_player()`. `roster.py` has `RosterLoader` with its own upsert logic. The scouting version is simpler (no field validation, no unknown field logging) but performs the same DB operations (INSERT into players, INSERT into team_rosters with ON CONFLICT).
**Notes**: Not covered by E-117 or E-122. This is a maintenance concern -- if roster upsert logic changes in one place but not the other, behavior diverges. However, the scouting version intentionally handles a different response shape (public API roster format vs. authenticated roster format), so full dedup may not be trivial.

### H-6 — `backup_database()` uses `shutil.copy2()` on WAL-mode database
**Verdict**: CONFIRMED
**Evidence**: `src/db/backup.py:68` calls `shutil.copy2(db_path, backup_path)`. For a WAL-mode SQLite database, this copies only the main `.db` file, not the `-wal` and `-shm` sidecar files. If the database is being written to during backup, the copy may be inconsistent. `sqlite3.Connection.backup()` or a WAL checkpoint before copy would be the safe approach.
**Notes**: Not covered by E-117 or E-122. Severity depends on usage pattern -- if backups only run when the app is idle (no writes), risk is low. But the current code has no such guard. The `sqlite3.Connection.backup()` API is the standard fix.

---

## Medium Priority

### M-1 — `src/db/__init__.py` missing `from __future__ import annotations`
**Verdict**: NEEDS CONTEXT
**Evidence**: `src/db/__init__.py` is a single-line docstring: `"""Database utility modules (backup, reset)."""`. No type annotations, no imports, no code. The `from __future__ import annotations` convention exists for modules that use type annotations.
**Notes**: Technically a convention violation, but with zero functional impact since the file has no annotations. Severity: TRIVIAL. Not covered by E-117 or E-122.

### M-2 — `_UUID_RE` duplicated in `game_loader.py` and `scouting_loader.py`
**Verdict**: CONFIRMED
**Evidence**: `game_loader.py:64-67` and `scouting_loader.py:56-59` both compile identical regex. Minor DRY issue.
**Notes**: Not covered by E-117 or E-122. Same consolidation target as H-2 (shared helpers module).

### M-3 — `RosterLoader._upsert_roster_membership()` docstring says `INSERT OR IGNORE` but uses `ON CONFLICT DO UPDATE`
**Verdict**: CONFIRMED
**Evidence**: `roster.py:292` docstring says "Uses ``INSERT OR IGNORE`` so re-running is idempotent" but lines 299-305 use `ON CONFLICT(team_id, player_id, season_id) DO UPDATE SET jersey_number = excluded.jersey_number, position = excluded.position`. The actual behavior (update on conflict) is better than described (ignore). Documentation is misleading.
**Notes**: Not covered by E-117 or E-122. Fix is a one-line docstring edit.

### M-4 — `SeasonStatsLoader._upsert_batting()` stores only 10 of 50+ available batting stat columns
**Verdict**: CONFIRMED
**Evidence**: `season_stats_loader.py:257-290` maps only `GP, AB, H, 2B, 3B, HR, RBI, BB, SO, SB` to the INSERT. The schema has ~47 batting columns. All other stats from the API are silently dropped by `dict.get()` not being called for them.
**Notes**: **OVERLAP: Fully covered by E-117-02** (season stats batting column expansion, 37 missing columns). E-117 epic column inventory confirms all 37 missing columns.

### M-5 — `SeasonStatsLoader._upsert_pitching()` stores only 10 of 40+ available pitching stat columns
**Verdict**: CONFIRMED
**Evidence**: `season_stats_loader.py:321-352` maps only `GP:P, IP, H, ER, BB, SO, HR, #P, TS` (9 columns after IP conversion). The schema has ~38 additional pitching columns.
**Notes**: **OVERLAP: Fully covered by E-117-03** (season stats pitching column expansion, 15 confirmed + 23 optimistic columns).

### M-6 — `games.game_stream_id` is never populated by either loader
**Verdict**: CONFIRMED
**Evidence**: `game_loader.py:803-818` `_upsert_game()` INSERT lists `game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status`. No `game_stream_id`. Schema at `001_initial_schema.sql:135` defines `game_stream_id TEXT` on `games`. The `GameSummaryEntry` dataclass at line 125 HAS `game_stream_id` -- it's available but not threaded through.
**Notes**: **OVERLAP: Fully covered by E-117-01** (AC includes "games rows include `game_stream_id` from the boxscore file stem").

### M-7 — `load_seed()` in `reset.py` uses f-string for table name in SQL
**Verdict**: NEEDS CONTEXT
**Evidence**: `reset.py:141-142` uses `f"SELECT COUNT(*) FROM {table};"` with `noqa: S608`. Table names come from `sqlite_master` (internal SQLite catalog, not user input). The code comment acknowledges this.
**Notes**: Safe in practice -- `sqlite_master` is a trusted source. The `noqa` comment is appropriate. Parameterized queries cannot be used for table names in SQL. Severity: INFORMATIONAL. Not covered by E-117 or E-122.

### M-8 — `get_team_batting_stats()` default season_id hardcoded to `"2026-spring-hs"`
**Verdict**: CONFIRMED
**Evidence**: `src/api/db.py:59` has `season_id: str = "2026-spring-hs"`. Same at line 143 for `get_team_pitching_stats()`. This will break next season.
**Notes**: Not covered by E-117 or E-122. Should be made dynamic (e.g., derive from current date or fetch latest season). Low urgency for 2026 season but will need fixing before 2027.

### M-9 — Test files use `sys.path.insert()` unnecessarily
**Verdict**: CONFIRMED
**Evidence**: grep found 21 test files using `sys.path.insert(0, str(_PROJECT_ROOT))`. With the editable install (`pip install -e .`), these are unnecessary. Some loader test files (e.g., `test_game_loader.py`, `test_roster_loader.py`, `test_scouting_loader.py`) do NOT use this pattern, confirming it's not needed.
**Notes**: Reviewer's claim that "technically not a violation" because tests aren't `src/` is correct -- the python-style rule targets `src/` modules. Still, the inconsistency is a maintenance issue. **OVERLAP: Partially covered by E-122-04** (migrating inline `_SCHEMA_SQL` to `run_migrations()` in 5 test files). The `sys.path.insert()` removal is NOT in E-122 scope -- it's a separate issue.

### M-10 — `player_season_pitching` has two `gp` columns with different semantics
**Verdict**: CONFIRMED
**Evidence**: Schema at `001_initial_schema.sql:301` has `gp_pitcher INTEGER, -- games pitched` and line 325 has `gp INTEGER, -- games played (all roles)`. Scouting loader `_compute_pitching_aggregates` at line 416 sets `gp_pitcher = games_tracked` (COUNT of per-game rows). The `gp` column is never set by any loader.
**Notes**: **PARTIALLY COVERED by E-117-03**: E-117 epic Technical Notes explicitly address the GP vs GP:P ambiguity -- `gp` lives in the `general` API section, not `defense`, so `defense.get("GP")` returns None. E-117-03 will map it optimistically (NULL is acceptable). The scouting loader conflation of `gp_pitcher = games_tracked` is addressed in E-117-04 (aggregate expansion).

---

## Summary

| Finding | Verdict | Overlap |
|---------|---------|---------|
| C-1 | CONFIRMED | E-117-01 (full) |
| C-2 | CONFIRMED | E-117-01 (full), E-122 defers |
| C-3 | CONFIRMED | E-117-01 AC-13 (full) |
| H-1 | CONFIRMED | None |
| H-2 | CONFIRMED | None |
| H-3 | FALSE POSITIVE | N/A -- test file exists |
| H-4 | FALSE POSITIVE | N/A -- tests exist (H-3 was wrong) |
| H-5 | CONFIRMED | None |
| H-6 | CONFIRMED | None |
| M-1 | NEEDS CONTEXT | None (trivial) |
| M-2 | CONFIRMED | None |
| M-3 | CONFIRMED | None |
| M-4 | CONFIRMED | E-117-02 (full) |
| M-5 | CONFIRMED | E-117-03 (full) |
| M-6 | CONFIRMED | E-117-01 (full) |
| M-7 | NEEDS CONTEXT | None (safe by design) |
| M-8 | CONFIRMED | None |
| M-9 | CONFIRMED | E-122-04 (partial -- schema only, not sys.path) |
| M-10 | CONFIRMED | E-117-03/04 (partial) |

### Net New Issues (not covered by E-117 or E-122)

1. **H-1**: `executescript()` auto-commit defeats rollback safety (low risk today, high risk for future migrations)
2. **H-2**: `_ensure_season_row()` / `_ensure_team_row()` duplicated across 4 loaders (DRY)
3. **H-5**: Scouting loader roster logic duplicates RosterLoader (maintenance risk)
4. **H-6**: `backup_database()` unsafe for WAL-mode active DB (data integrity)
5. **M-2**: `_UUID_RE` regex duplicated (DRY, minor)
6. **M-3**: Docstring says INSERT OR IGNORE but code does ON CONFLICT UPDATE (misleading)
7. **M-8**: Hardcoded `"2026-spring-hs"` default season (will break next season)
8. **M-9**: Unnecessary `sys.path.insert()` in 21 test files (inconsistency, not E-122 scope)
