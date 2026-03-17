# CR-1: Schema & Data Layer Review

**Scope**: migrations/001_initial_schema.sql, src/api/db.py, src/api/auth.py, src/gamechanger/config.py, src/gamechanger/types.py

## Critical Issues

None found.

## Warnings

### W-1: `player_season_pitching` has two games-played columns that could confuse consumers

`migrations/001_initial_schema.sql:301` defines `gp_pitcher INTEGER` ("games pitched") and line 325 defines `gp INTEGER` ("games played (all roles)"). Both are legitimate GC stats, but the coexistence in the same table is a documentation/naming hazard — a query selecting `gp` from this table may silently get the wrong metric. The header comment (line 288) explains the distinction, but downstream query authors (db.py, loaders) must be careful.

**Impact**: Not a bug — the schema correctly models two distinct GC stats. But any future query on this table should be audited to ensure it picks the right column.

### W-2: `get_teams_by_ids` accepts a list but builds SQL via f-string

`src/api/db.py:128-129`: `placeholders = ",".join("?" for _ in team_ids)` then `f"SELECT id, name FROM teams WHERE id IN ({placeholders})"`. This is safe because `placeholders` is always `?,?,?...` (no user input interpolated into SQL), but the f-string pattern is a footgun if someone later modifies it to include actual values. The parameterized bind on line 133 correctly passes `team_ids` as params.

**Impact**: No current vulnerability. Minor maintenance risk.

## Minor Issues

### M-1: `config.py` does not use `TeamRef` from `types.py`

`src/gamechanger/config.py` defines its own `TeamEntry` dataclass with an `internal_id` field that parallels `TeamRef.id`. The CLAUDE.md documents `TeamRef` as the standard pipeline pattern (`id` for DB, `gc_uuid`/`public_id` for API). `config.py` predates or sits alongside that pattern — `TeamEntry.id` holds the GC UUID (not the DB integer), and `internal_id` is the DB PK. This is a different shape than `TeamRef` but serves a different purpose (YAML config loading vs. runtime pipeline reference).

**Impact**: No bug. Two parallel team-identity patterns coexist. Consolidation would be a future cleanup story, not a current defect.

### M-2: `_DEFAULT_CONFIG_PATH` and `_DEFAULT_DB_PATH` use different parent depths but both resolve correctly

- `src/api/db.py:23`: `Path(__file__).resolve().parents[2]` → repo root (correct for `src/api/db.py`)
- `src/gamechanger/config.py:43`: `Path(__file__).resolve().parents[2]` → repo root (correct for `src/gamechanger/config.py`)

Both are correct per the repo-root resolution convention. `parents[2]` works for both because both are exactly 2 directories deep under `src/` (`src/api/` and `src/gamechanger/`).

**Impact**: None — just confirming correctness.

## Observations

### Schema correctness

- **INTEGER PK on teams**: Correctly implemented with `AUTOINCREMENT` (line 50). All FK references use `teams(id)` — verified across `team_rosters`, `games`, `player_game_batting`, `player_game_pitching`, `player_season_batting`, `player_season_pitching`, `spray_charts`, `opponent_links`, `scouting_runs`, `user_team_access`, `coaching_assignments`, `team_opponents`.
- **UNIQUE constraints**: Partial unique indexes on `gc_uuid` and `public_id` (lines 479-482) correctly allow multiple NULLs while enforcing uniqueness on non-NULL values.
- **Index coverage**: Comprehensive — covers all major query join/filter patterns (team+season on roster/stats tables, game lookup by season/team/date, player lookups, coaching assignments).
- **CHECK constraints**: Classification values, stat_completeness enums, membership_type, scouting_runs status — all properly constrained.
- **Self-referential guard**: `team_opponents` has `CHECK(our_team_id != opponent_team_id)` (line 107) — good.
- **IP_OUTS convention**: Consistently applied in both game and season pitching tables, with clear header documentation.

### TeamRef dataclass (types.py)

- Clean, minimal, well-documented. Fields match CLAUDE.md spec: `id: int`, `gc_uuid: str | None`, `public_id: str | None`.

### db.py query quality

- All queries use parameterized binds (no SQL injection risk).
- All functions use `with closing(get_connection())` context managers — connections are properly closed.
- `get_connection()` enables WAL mode and foreign keys — correct.
- Error handling is consistent: `sqlite3.Error` catch → log + return empty/default.
- The opponent count query (`get_team_opponents`) correctly handles home/away symmetry with CASE expressions and proper GROUP BY.

### auth.py INTEGER PK migration

- All auth tables reference `users(id)` as INTEGER — correct.
- Session creation uses `user_id: int` parameter — matches schema.
- `_get_permitted_teams` queries `user_team_access.user_id` → INTEGER FK — correct.
- Dev bypass creates users with `INSERT INTO users (email)` and reads `cursor.lastrowid` — correctly leverages INTEGER PK auto-assignment.
- OperationalError handling for missing tables (503 response) — good defensive pattern.

### Credential safety

- No hardcoded credentials or tokens in any reviewed file.
- `auth.py` uses `secrets.token_hex(32)` for session tokens and stores only SHA-256 hashes — correct.
- Dev bypass is guarded against production use (line 248: raises `RuntimeError` if `APP_ENV=production`).

### Import boundary compliance

- `src/api/db.py`: imports only stdlib + no `scripts/` imports — compliant.
- `src/api/auth.py`: imports from `src.api.db` — compliant (src-to-src).
- `src/gamechanger/config.py`: imports only stdlib + yaml — compliant.
- `src/gamechanger/types.py`: imports only stdlib — compliant.

### Convention compliance

- All 5 files have `from __future__ import annotations` — compliant.
- All use `pathlib.Path` for file paths — compliant.
- All use `logging` module — compliant.
- Type hints on all public functions — compliant.
- Docstrings on all public functions — compliant.
