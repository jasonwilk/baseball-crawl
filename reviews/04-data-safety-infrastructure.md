# Code Review: Data Layer, Safety & Infrastructure

## Critical Issues

### 1. `collect-endpoints.sh` contains hardcoded real UUIDs (possible credential/PII leak)

**File**: `scripts/collect-endpoints.sh:24-27`

```bash
TEAM="72bb77d8-54ca-42d2-8547-9da4880d0cb4"
ORG="8881846c-7a9c-4230-ac17-09627aac7f59"
EVENT="1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6"
STREAM="c05a5413-d250-4f28-bd92-efbe67bac348"
```

These appear to be real GameChanger UUIDs (team, organization, event, game stream) hardcoded in a committed script. Per the project's security rules: "Credentials and tokens MUST NEVER appear in code, logs, commit history, or agent output." While UUIDs alone are not auth tokens, the CLAUDE.md data model section states "GameChanger user IDs... are PII because they resolve to real people via the API." Team and org UUIDs similarly resolve to real entities. These should be loaded from `.env` or a config file, not hardcoded in source.

Additionally, this script reads `gc-token` directly from a file and passes it via command-line arguments to curl, which means the token appears in the process list (`/proc/*/cmdline`). While this is a local-only script, it's worth noting.

### 2. `pii_patterns.py` missing `from __future__ import annotations`

**File**: `src/safety/pii_patterns.py:1`

This is a `src/` module that lacks the required `from __future__ import annotations` import. The python-style rules state: "Use `from __future__ import annotations` at the top of each module for modern type syntax." The file uses `list[dict[str, str]]` and `set[str]` type annotations at the module level (lines 47, 73, 89, 97) which work in Python 3.13 without the future import, but the project convention requires it consistently.

### 3. Docker container runs as root

**File**: `Dockerfile`

The Dockerfile does not include a `USER` directive. The container runs all processes (pip install, migrations, uvicorn) as root. This is a security concern for a production-deployed application. If an attacker exploits a vulnerability in the FastAPI application, they gain root access inside the container. Best practice is to create a non-root user and switch to it before running the application:

```dockerfile
RUN useradd --create-home appuser
USER appuser
```

### 4. No FK CASCADE DELETE rules -- orphan data risk on team deletion

**File**: `migrations/001_initial_schema.sql`

No foreign key references in the schema use `ON DELETE CASCADE` or `ON DELETE SET NULL`. If a team row is deleted from `teams`, all referencing rows in `team_rosters`, `games`, `player_game_batting`, `player_game_pitching`, `player_season_batting`, `player_season_pitching`, `scouting_runs`, `opponent_links`, `team_opponents`, `user_team_access`, and `coaching_assignments` become orphaned (or the delete fails if FKs are enforced). This is a data integrity concern. At minimum, junction tables like `user_team_access`, `team_opponents`, and `coaching_assignments` should cascade on delete.

### 5. `.env.example` references non-existent schema columns

**File**: `.env.example:171`

```
#   sqlite3 data/app.db "INSERT INTO users (...) VALUES (...);"  -- references display_name and is_admin columns that no longer exist
```

The `users` table in the E-100 schema has no `display_name` or `is_admin` columns (confirmed by `tests/test_migration_001_auth.py` which explicitly tests their absence). This SQL command will fail if anyone follows the instructions. The example should be updated to match the current schema.

## Important Issues

### 6. `executescript()` does not honor `PRAGMA foreign_keys=ON` set before it

**Files**: `migrations/apply_migrations.py:130`, `src/db/reset.py:130`, `scripts/seed_dev.py:108`

SQLite's `executescript()` issues an implicit `COMMIT` before executing and runs statements in autocommit mode. More importantly, `executescript()` effectively resets the connection state -- the `PRAGMA foreign_keys=ON` set before the call has no effect on statements inside `executescript()`. This means:

- In `apply_migration()` (line 130): the migration SQL runs without FK enforcement, so FK-violating data could be inserted during migrations without error.
- In `load_seed()` (reset.py line 130): seed data is loaded without FK enforcement.
- In `seed_dev.py` (line 108): same issue.

The fix is to include `PRAGMA foreign_keys=ON;` as the first statement inside the SQL being passed to `executescript()`, or to use `execute()` with individual statements.

### 7. `pii_scanner.py` uses `sys.path` manipulation in a `src/` module

**File**: `src/safety/pii_scanner.py:40`

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

The python-style rules explicitly state: "No `sys.path` manipulation in `src/` modules: Never use `sys.path.insert()` or `sys.path.append()` in modules under `src/`." The fallback import is there for the pre-commit hook use case (running as a standalone script), which is understandable, but it violates the documented convention. The hook (``.githooks/pre-commit``) could instead invoke the module via `python3 -m src.safety.pii_scanner` to avoid the need for `sys.path` manipulation.

### 8. `backup_database` connection not properly closed on error

**File**: `src/db/backup.py:72-73`

```python
with sqlite3.connect(db_path) as src, sqlite3.connect(backup_path) as dst:
    src.backup(dst)
```

The `with` statement on `sqlite3.connect()` does not close the connection -- it only commits/rolls back the transaction. If `src.backup(dst)` fails, neither connection is explicitly closed. This is a well-known SQLite/Python gotcha. The connections should be explicitly closed in a `try/finally` block or use a separate context manager that actually closes. In practice, the GC will clean up, but for WAL-mode databases, unclosed connections can hold locks.

### 9. `_run_migrations_and_count` does not use context manager for connection

**File**: `src/db/reset.py:94-103`

```python
conn = sqlite3.connect(str(db_path))
try:
    cursor = conn.execute(...)
    table_count: int = cursor.fetchone()[0]
finally:
    conn.close()
```

While this does close the connection in `finally`, it would be cleaner and more consistent to use `with closing(sqlite3.connect(...)) as conn:`. The same pattern appears in `load_seed` (line 127-151). Not a bug, but inconsistent with the project's preference for context managers.

### 10. `validate_api_docs.py` uses cwd-relative paths

**File**: `scripts/validate_api_docs.py:24-26`

```python
ENDPOINTS_DIR = Path("docs/api/endpoints")
README_PATH = Path("docs/api/README.md")
FORMAT_SPEC_PATH = Path(".project/research/E-062-format-spec.md")
```

These are relative to the current working directory, not the repo root. If the script is run from any directory other than the repo root, all paths will be wrong. Other scripts in the project use `Path(__file__).resolve().parent.parent` to derive the repo root. This script should do the same.

### 11. Missing `from __future__ import annotations` in `src/db/__init__.py`

**File**: `src/db/__init__.py`

The file contains only a docstring and no future import. While it has no type annotations currently, the project convention is to include this import in every module.

### 12. Missing `from __future__ import annotations` in `src/safety/__init__.py`

**File**: `src/safety/__init__.py`

Empty init file (1 line) with no future import.

### 13. `seed_dev.py` duplicates logic from `src/db/reset.py`

**File**: `scripts/seed_dev.py:82-116`

The `load_seed` function in `seed_dev.py` is nearly identical to `src.db.reset.load_seed`. Both read a SQL file, execute it with FK enforcement, and handle errors. The script should import from `src.db.reset` instead of duplicating the logic. This is a DRY violation.

### 14. `devcontainer.json` has very long single-line `postCreateCommand`

**File**: `.devcontainer/devcontainer.json:17`

The `postCreateCommand` is a single line with 12+ chained commands. This is extremely hard to read, debug, and maintain. A failure in any middle command will abort the rest. This should be extracted to a script file (e.g., `.devcontainer/post-create.sh`) for readability and maintainability.

### 15. Test files use `sys.path` manipulation

**Files**: `tests/test_schema.py:30-31`, `tests/test_schema_queries.py:30-31`, `tests/test_migrations.py:28-29`

Several test files use `sys.path.insert(0, str(_PROJECT_ROOT))`. While the python-style rules limit this restriction to `src/` modules and allow it in scripts, the project has an editable install (`pip install -e .`), making this unnecessary. The imports would work without the path manipulation.

## Minor Issues

### 16. `check_codex_rtk.py` uses `os.access` instead of pathlib

**File**: `scripts/check_codex_rtk.py:63`

```python
if not os.access(rtk_bin, os.X_OK):
```

The project convention prefers `pathlib.Path` over `os.path` for file operations. While `pathlib` does not have a direct equivalent of `os.access(X_OK)`, the `import os` could be noted. This is minor since pathlib does not cover the executable-check use case.

### 17. `conftest.py` missing `from __future__ import annotations`

**File**: `tests/conftest.py:1`

No future import. Minimal file, but for consistency with project conventions.

### 18. Backup timestamp lacks sub-second precision

**File**: `src/db/backup.py:68`

```python
timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H%M%S")
```

If two backups are created within the same second (e.g., in automated testing), the second one will overwrite the first. Adding `%f` (microseconds) or a counter would prevent this edge case.

### 19. `smoke_test.py` catches `CredentialExpiredError` both inside and outside `run_smoke_test`

**File**: `scripts/smoke_test.py:192-196`

```python
try:
    passed = run_smoke_test(team_id=args.team_id)
except CredentialExpiredError:
    ...
```

But `run_smoke_test` already catches `CredentialExpiredError` internally (lines 126-128, 147-149, 162-164) and returns `False`. The outer catch in `main()` is unreachable dead code, since all call sites within `run_smoke_test` that call `_call()` are wrapped in their own `CredentialExpiredError` handlers. This should be cleaned up for clarity.

### 20. `idx_games_game_date` index exists but no composite index for common query patterns

**File**: `migrations/001_initial_schema.sql:490`

There's an index on `games(game_date)` alone, but the most common query pattern is likely to filter by `(season_id, game_date)` or `(home_team_id, game_date)`. The individual column index is less useful than a composite one for these queries. This is a minor optimization concern.

### 21. `spray_charts` table FKs allow NULL without explicit documentation

**File**: `migrations/001_initial_schema.sql:363-376`

All FK columns in `spray_charts` (`game_id`, `player_id`, `team_id`, `pitcher_id`) lack `NOT NULL` constraints. While `pitcher_id` is documented as nullable, it's unclear whether `game_id`, `player_id`, and `team_id` should also be nullable. If these are always expected to be present, they should have `NOT NULL` constraints.

### 22. `test_schema.py` and `test_schema_queries.py` duplicate fixture setup

**Files**: `tests/test_schema.py:38-57`, `tests/test_schema_queries.py:38-62`

Both files create in-memory databases with very similar fixture code (apply migrations, enable FKs, enable WAL). This could be extracted to `conftest.py` as a shared fixture.

## Observations

### Things done well

1. **WAL-safe backup**: `backup_database()` correctly uses `sqlite3.Connection.backup()` instead of raw file copy, ensuring WAL-mode databases produce consistent backups.

2. **Production guard on reset**: The `check_production_guard()` function with `APP_ENV` checking and `--force` requirement is well-designed. The `_skip_guard` pattern for CLI vs. programmatic use is thoughtful.

3. **Migration idempotency**: Using `CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE`, and a `_migrations` tracking table provides solid idempotency guarantees.

4. **PII scanner design**: The allowlist-based scanning (SCANNABLE_EXTENSIONS), skip-path exclusions, and synthetic-data marker provide a practical, low-false-positive scanner. The integration with the pre-commit hook creates a genuine safety net.

5. **Test coverage breadth**: Schema tests, migration idempotency tests, backup validation, PII scanner edge cases, and integration tests with real git repos show thorough coverage.

6. **Script architecture**: The thin-wrapper pattern (scripts import from `src/` for business logic) keeps scripts focused and testable. The `sys.path` bootstrapping in scripts is the correct place for it.

7. **Credential handling in `.env.example`**: Placeholder values are clearly fake (all zeros, `eyJ...your-refresh-token-jwt`), and the file is well-documented with explanations for each credential.

8. **Schema documentation**: The header comments in `001_initial_schema.sql` (ID convention, IP_OUTS convention, classification check, timestamp format) provide excellent context for future developers.

### Patterns noted

- The project maintains three separate `get_db_path()` functions: one in `src/db/backup.py`, one in `src/db/reset.py`, and one in `migrations/apply_migrations.py`. These have slightly different signatures and resolution logic. A shared implementation would reduce duplication.

- SQLite connections throughout the codebase mix `with` statements (which don't close connections) and explicit `try/finally/close()` patterns. A consistent approach would improve maintainability.

- The project uses `from __future__ import annotations` consistently in `src/` modules with two exceptions (`pii_patterns.py` and `__init__.py` files).

## Summary

The data layer, safety infrastructure, and scripts are **solid and well-architected overall**. The migration system, backup logic, PII scanner, and production guards demonstrate careful engineering for a coaching analytics platform.

**Critical concerns** center on: (1) hardcoded real UUIDs in `collect-endpoints.sh` that should not be in source control, (2) the Docker container running as root in production, and (3) a stale `.env.example` instruction referencing deleted schema columns.

**The most impactful correctness issue** is `executescript()` silently ignoring `PRAGMA foreign_keys=ON`, which means FK enforcement is not actually active during migrations and seed loading. This hasn't caused problems yet because the seed data is correct, but it's a latent risk.

**Test coverage is strong** for the data layer, with schema validation, migration idempotency, backup integrity, and PII scanner edge cases well covered. The bootstrap pipeline tests use appropriate mocking to isolate external dependencies.

The code quality is generally high with good documentation, consistent patterns, and thoughtful error handling. The findings above represent opportunities to harden the existing solid foundation.
