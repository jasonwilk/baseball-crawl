# Code Review: Crawlers, Loaders & Pipeline

**Scope**: All source files in `src/gamechanger/crawlers/`, `src/gamechanger/loaders/`, `src/pipeline/`, `src/gamechanger/bridge.py`, `src/gamechanger/url_parser.py`, `src/gamechanger/team_resolver.py`, and their corresponding test files.

**Tests**: All 347 tests pass.

---

## Critical Issues

### C-1: `game_loader.py` ignores `R` (runs) from boxscore batting -- schema column exists but is never populated

**File**: `src/gamechanger/loaders/game_loader.py:79`

The `_BATTING_SKIP_DEBUG` set includes `"R"` with the comment "R is not in the schema -- log at DEBUG, do not store." However, the `player_game_batting` table **does** have an `r` column (line 162 of `001_initial_schema.sql`). The `R` stat from the boxscore response is silently discarded. The `_upsert_batting` method (line 830) does not include `r` in its INSERT/UPDATE.

Similarly, `TB` is in `_BATTING_SKIP_DEBUG` but the schema has a `tb` column on `player_game_batting` (line 173 of schema). And `HBP`, `CS`, `E` are in `_BATTING_EXTRAS_SKIP_DEBUG` but all three exist as columns in `player_game_batting` (lines 172, 175, 176 of schema).

This means 5 available boxscore stats (`R`, `TB`, `HBP`, `CS`, `E`) that have schema columns are silently dropped during game loading.

**Impact**: Data loss on every load. The schema was clearly designed to hold these values but the loader was not updated when columns were added. Per CLAUDE.md: "Store every GameChanger stat" is an explicit project directive.

### C-2: `game_loader.py` pitching -- `R` (total runs) and `HR` are skipped despite schema columns

**File**: `src/gamechanger/loaders/game_loader.py:100-102`

- `_PITCHING_SKIP_DEBUG` includes `"R"` but `player_game_pitching` has an `r` column (line 198).
- `_PITCHING_EXTRAS_SKIP_DEBUG` includes `"WP"`, `"HBP"`, `"#P"`, `"TS"`, `"BF"`, `"HR"` -- all of which have corresponding schema columns (`wp`, `hbp`, `pitches`, `total_strikes`, `bf`, `hr` at lines 203-207 of schema).

**Impact**: 7 pitching stat columns are never populated from boxscore data despite having schema columns. Same "store every stat" directive violation.

### C-3: `scouting.py:287-301` -- `update_run_load_status` uses f-string interpolation in SQL

**File**: `src/gamechanger/crawlers/scouting.py:287-301`

```python
completed_at = (
    "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
    if status == "completed"
    else "NULL"
)
self._db.execute(
    f"""
    UPDATE scouting_runs SET
        status       = ?,
        last_checked = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
        completed_at = {completed_at}
    WHERE team_id = ? AND season_id = ? AND run_type = ?
    """,
    (status, team_id, season_id, _RUN_TYPE),
)
```

The `completed_at` value is constructed from `status` which is passed in from caller code (CLI layer). While the current callers always pass `"completed"` or `"failed"`, this is a SQL injection surface if any future caller passes a crafted `status` string. The f-string embeds a value derived from a function parameter directly into SQL.

**Impact**: Latent SQL injection risk. The `status` parameter is validated by the CHECK constraint on the column (`IN ('pending', 'running', 'completed', 'failed')`), which limits exploitability, but the pattern violates secure coding practice. Should use parameterized SQL with CASE expression.

---

## Important Issues

### I-1: `bridge.py` creates a new `GameChangerClient` on every call

**File**: `src/gamechanger/bridge.py:51,84`

Both `resolve_public_id_to_uuid()` and `resolve_uuid_to_public_id()` instantiate a new `GameChangerClient()` internally. This means every call reads `.env`, creates a new HTTP session, and initializes a new `TokenManager`. If these are called in a loop (e.g., resolving multiple teams), this is wasteful and violates the pattern used by every other module (client injected via constructor).

**Impact**: Performance waste and inconsistent API. Not a correctness bug but significantly suboptimal for batch usage.

### I-2: `team_resolver.py` uses raw `create_session()` instead of `GameChangerClient`

**File**: `src/gamechanger/team_resolver.py:93,170`

The `resolve_team()` and `discover_opponents()` functions create their own HTTP sessions directly via `create_session()` and make raw `session.get()` calls, bypassing `GameChangerClient` entirely. While these are public endpoints that don't need auth, the project convention per CLAUDE.md is: "All callers (ingestion scripts, smoke tests, etc.) must use this client -- never make raw httpx calls directly." The `GameChangerClient` has a `get_public()` method specifically for unauthenticated endpoints.

**Impact**: Convention violation. These functions miss the rate limiting, retry logic, and error handling standardized in `GameChangerClient.get_public()`.

### I-3: Duplicated `_is_fresh()` and `_ensure_season_row()` helper methods across multiple modules

**Files**:
- `_is_fresh()` in `schedule.py:223`, `player_stats.py:156`, `roster.py:151`, `opponent.py:327`
- `_ensure_season_row()` in `game_loader.py:960`, `roster.py:344`, `season_stats_loader.py:416`, `scouting_loader.py:468`, `scouting.py:420`
- `_ensure_team_row()` in `game_loader.py:934`, `roster.py:316`, `season_stats_loader.py:388`

These are nearly identical implementations copied across 4-5 modules. The `_ensure_season_row` logic (parse year from slug, INSERT ON CONFLICT DO NOTHING) is the same in every location. The `_ensure_team_row` logic (INSERT OR IGNORE into teams with gc_uuid, fallback SELECT) is the same in 3 loaders.

**Impact**: DRY violation. Any bug fix or behavior change requires updating 4-5 copies. Consider extracting to a shared `src/gamechanger/db_helpers.py` module.

### I-4: `game_loader.py` -- `_BATTING_MAIN` does not include `R` (runs scored) but the data is available

**File**: `src/gamechanger/loaders/game_loader.py:70-77`

The batting main stats mapping only includes `AB`, `H`, `RBI`, `BB`, `SO`. The `R` (runs) stat is in the boxscore response's main stats object (it's in `_BATTING_SKIP_DEBUG`), and there is a corresponding `r` column in `player_game_batting`. This is the same as C-1 but worth noting that the mapping is straightforwardly incomplete -- `R` belongs in `_BATTING_MAIN`, not `_BATTING_SKIP_DEBUG`.

### I-5: No `from __future__ import annotations` in `src/pipeline/__init__.py`

**File**: `src/pipeline/__init__.py:1`

The file only contains a docstring. Per `.claude/rules/python-style.md`: "Use `from __future__ import annotations` at the top of each module." This is a minimal file but the convention applies universally.

### I-6: `roster.py` crawler -- unused `datetime` import

**File**: `src/gamechanger/crawlers/roster.py:29`

```python
from datetime import datetime, timezone
```

Neither `datetime` nor `timezone` is used anywhere in the file.

### I-7: `scouting_loader.py` reads boxscore JSON files twice

**File**: `src/gamechanger/loaders/scouting_loader.py:436-462`

The `_record_uuid_from_boxscore_path()` method re-reads and re-parses each boxscore JSON file that was already loaded by `GameLoader.load_file()` moments before. For large seasons with many boxscores, this doubles the file I/O.

**Impact**: Unnecessary performance cost. The UUID keys could be extracted during the initial load or passed as a return value from `load_file()`.

### I-8: `scouting_loader.py:_load_roster` silently accepts empty first_name/last_name

**File**: `src/gamechanger/loaders/scouting_loader.py:269`

```python
first_name=str(player.get("first_name") or ""),
last_name=str(player.get("last_name") or ""),
```

Players with missing or empty `first_name`/`last_name` are upserted with empty strings. The main `RosterLoader` (in `loaders/roster.py:242-253`) correctly skips such records with an error log. The scouting loader's roster handling is more permissive, creating inconsistent behavior.

### I-9: `season_stats_loader.py` only loads a subset of available batting stats

**File**: `src/gamechanger/loaders/season_stats_loader.py:257-290`

The `_upsert_batting` method only inserts 10 stat columns (`gp, ab, h, doubles, triples, hr, rbi, bb, so, sb`). The schema has 40+ batting stat columns (`pa`, `singles`, `r`, `sol`, `hbp`, `shb`, `shf`, `gidp`, `roe`, `fc`, `ci`, `pik`, `cs`, `tb`, `xbh`, `lob`, `three_out_lob`, `ob`, `gshr`, `two_out_rbi`, `hrisp`, `abrisp`, `qab`, `hard`, `weak`, `lnd`, `flb`, `gb`, `ps`, `sw`, `sm`, `inp`, `full`, `two_strikes`, `two_s_plus_3`, `six_plus`, `lobb`), and the season-stats API response likely contains many of them. Same issue for pitching -- only 7 stat columns are loaded but the schema has 30+.

**Impact**: Significant data loss for season stats. The "store every stat" directive makes this a high priority to address.

---

## Minor Issues

### M-1: `_SEASON_STATS_USER_ACTION` constant defined but never used

**File**: `src/gamechanger/crawlers/player_stats.py:40`

```python
_SEASON_STATS_USER_ACTION = "data_loading:team_stats"
```

This constant is defined but never referenced anywhere in the file or project.

### M-2: `schedule.py` type annotation uses `str` for team_id in `_crawl_schedule` but `CrawlConfig.member_teams` yields `TeamEntry` objects

**File**: `src/gamechanger/crawlers/schedule.py:88,113`

The `crawl_all` method passes `team.id` (a string) to `_crawl_schedule(team_id: str, ...)`. The type annotation is correct but the variable name `team_id` is misleading -- in the E-100 schema, `team_id` conventionally refers to the INTEGER PK. The crawler uses `team.id` which is `gc_uuid` (the API identifier string). This naming is internally consistent within crawlers but diverges from the loader/DB convention.

### M-3: `opponent.py:120` -- `owned_ids` set uses string comparison for integer PKs

**File**: `src/gamechanger/crawlers/opponent.py:120`

```python
owned_ids = {t.id for t in self._config.member_teams}
```

This creates a set of strings (gc_uuid values). The comparison on line 231 (`if progenitor_id in owned_ids`) compares `progenitor_team_id` (a UUID string) against these. This works correctly because both are UUID strings, but the variable name `owned_ids` suggests INTEGER PKs in the context of this codebase.

### M-4: `_parse_summary_record` in `game_loader.py` logs raw record on warning

**File**: `src/gamechanger/loaders/game_loader.py:337`

```python
logger.warning(
    "Skipping summary record missing event_id or game_stream.id: %r", record
)
```

The `%r` format logs the full raw record. If the record contains any sensitive data, this could leak it to logs. In practice, game-summaries records don't contain credentials, but the pattern is worth noting.

---

## Observations

### O-1: Strong error handling pattern across crawlers

All crawlers follow a consistent pattern: catch `GameChangerAPIError` per-item, log with context, count errors, and re-raise `CredentialExpiredError` to abort. This is well-designed -- individual failures don't cascade but auth failures correctly stop the run.

### O-2: `ForbiddenError` as subclass of `CredentialExpiredError` requires careful ordering

The exception hierarchy (`ForbiddenError` extends `CredentialExpiredError`) means every `except CredentialExpiredError` also catches `ForbiddenError`. The codebase handles this correctly everywhere by catching `ForbiddenError` before `CredentialExpiredError`, but it's a footgun for future code.

### O-3: Test coverage is comprehensive

The test suite covers happy paths, error paths, idempotency, edge cases (missing fields, malformed data), and cross-cutting concerns (FK prerequisites, multi-team/multi-season isolation). The scouting loader tests include the important multi-season and multi-team aggregate isolation tests that verify correct SQL scope filtering.

### O-4: Idempotency is well-implemented

All loaders use `INSERT ... ON CONFLICT DO UPDATE` patterns that make re-runs safe. The crawlers use freshness-based caching that prevents unnecessary API calls. The opponent resolver's manual-link protection via COALESCE is a thoughtful design.

### O-5: Consistent use of parameterized SQL throughout

With the exception of the f-string interpolation in `scouting.py:update_run_load_status` (C-3), all SQL queries use parameterized placeholders. This is good security hygiene.

### O-6: The `GameSummaryEntry` dataclass is a clean abstraction

The `GameSummaryEntry` in `game_loader.py` provides a well-defined contract between the game-summaries index and the boxscore loader, cleanly separating the ID mapping logic from the stat loading logic.

---

## Summary

The crawlers, loaders, and pipeline orchestration code is **structurally sound** with good error handling, idempotency, and test coverage (347 tests, all passing). The architecture follows a clean separation between crawling (raw JSON to disk) and loading (JSON to DB), with the pipeline modules orchestrating the sequence.

The most significant issues are:

1. **Data loss** (C-1, C-2, I-9): Multiple boxscore stats that have schema columns are explicitly skipped by the game loader (`R`, `TB`, `HBP`, `CS`, `E` for batting; `R`, `WP`, `HBP`, `#P`, `TS`, `BF`, `HR` for pitching). The season stats loader only populates ~25% of available schema columns. This directly contradicts the "store every GameChanger stat" project directive.

2. **Latent SQL injection** (C-3): The `update_run_load_status` method uses f-string SQL interpolation from a function parameter. The CHECK constraint limits exploitability but the pattern should be fixed.

3. **Convention violations** (I-2): `team_resolver.py` bypasses `GameChangerClient` for public endpoints, missing standardized retry/error handling.

4. **DRY violations** (I-3): The same helper methods are copy-pasted across 3-5 modules.

Overall code health: **Good with data completeness gaps**. The infrastructure is solid and well-tested; the primary gap is that the loaders were written for a minimal stat set and not updated when the schema expanded to include comprehensive stats.
