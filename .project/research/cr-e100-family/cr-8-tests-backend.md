# CR-8: Crawler, Loader, Pipeline, and Schema Tests Review

**Reviewer**: code-reviewer
**Scope**: 18 test files from E-100 family (E-100, E-114, E-115, E-116, E-118, E-120)
**Date**: 2026-03-17

## Critical Issues

None found.

## Warnings

### W-1: Schema setup inconsistency — 6 test files use direct `executescript()` instead of `run_migrations()`

**E-120-05 focus area.** The following test files read the migration SQL file directly and execute it via `executescript()` rather than calling `run_migrations()`:

| File | Pattern Used |
|------|-------------|
| `tests/test_config.py` | `_MIGRATION_FILE.read_text()` + `executescript()` |
| `tests/test_schema.py` | `_MIGRATION_FILE.read_text()` + `executescript()` |
| `tests/test_db.py` | `_MIGRATION_FILE.read_text()` + `executescript()` |
| `tests/test_loaders/test_game_loader.py` | `_MIGRATION_FILE.read_text()` + `executescript()` |
| `tests/test_loaders/test_roster_loader.py` | `_MIGRATION_FILE.read_text()` + `executescript()` |
| `tests/test_loaders/test_season_stats_loader.py` | `_MIGRATION_FILE.read_text()` + `executescript()` |

Files that correctly use `run_migrations()`: `test_scouting_loader.py`, `test_scouting_crawler.py`, `test_e100_schema.py`, `test_migrations.py`, `test_opponent_resolver.py`.

**Risk**: Direct `executescript()` bypasses any logic in `run_migrations()` (WAL mode, idempotency tracking, seed data, future multi-file migration support). If migration machinery evolves, these 6 files will silently test against a different schema setup path than production uses. This is the most significant consistency gap in the test suite.

### W-2: `test_schema.py` and `test_e100_schema.py` overlap significantly

Both files test DDL structure (table existence, column names, constraints). `test_e100_schema.py` (804 lines) is more comprehensive and uses `run_migrations()`. `test_schema.py` (512 lines) uses direct `executescript()` and covers a subset of the same ground. The overlap creates maintenance burden — schema changes require updates in two places. Not blocking, but a consolidation candidate.

## Minor Issues

### M-1: `sys.path.insert` in 4 test files

The following files use `sys.path.insert(0, ...)` to add `src/` or project root to the path:

- `tests/test_config.py:8-9`
- `tests/test_schema.py:7`
- `tests/test_e100_schema.py:8`
- `tests/test_migrations.py:9`

This is technically allowed (python-style.md only prohibits `sys.path` manipulation in `src/` modules, not test files). However, the editable install (`pip install -e .`) already makes all `src/` packages importable. The `sys.path.insert` calls are unnecessary and could mask import resolution issues. Low priority cleanup.

### M-2: `test_config.py` uses `_MIGRATION_FILE` path resolution via `sys.path`

`test_config.py:12-13` resolves the migration file path using a hardcoded relative traversal from the test file location. This is fragile if the test file moves. Other files using the same pattern (test_schema.py, test_db.py, loader tests) have the same issue but it's consistent across them.

## Observations

### O-1: Test isolation is solid across all 18 files

Every file uses either `:memory:` SQLite databases or `tmp_path`-based file databases. No shared state between tests. No test ordering dependencies detected. Fixtures are properly scoped.

### O-2: `from __future__ import annotations` present in all files

All 18 test files include the required future annotations import. Full compliance with python-style.md.

### O-3: Multi-scope aggregate isolation tests exist and are well-designed

`test_scouting_loader.py` has two critical multi-scope tests:
- `test_aggregate_isolated_per_season` — seeds boxscores across 2 seasons, verifies aggregates filter by season
- `test_aggregate_isolated_per_team` — seeds boxscores across 2 teams, verifies aggregates filter by team

`test_db.py` also has multi-scope tests for the API layer (e.g., `test_get_team_batting_stats_filters_by_team_and_season`).

These tests would catch wrong-scope WHERE clause bugs — exactly the pattern the review rubric calls out.

### O-4: TeamRef usage is correct throughout

Test files that interact with the scouting pipeline (`test_scouting_loader.py`, `test_scouting_crawler.py`, `test_opponent_resolver.py`) properly construct and use `TeamRef` with `id: int`, `gc_uuid: str | None`, `public_id: str | None`. No confusion between INTEGER PK and external identifiers.

### O-5: FK constraint satisfaction in seed data

All loader and DB test files properly seed prerequisite rows (programs, seasons, teams, players) before inserting dependent records. `test_game_loader.py` explicitly tests the FK auto-creation path where the loader creates stub rows for missing prerequisites. No FK violation failures observed in test design.

### O-6: Mock correctness in crawler tests

All 6 crawler test files (`test_game_stats_crawler.py`, `test_opponent_crawler.py`, `test_opponent_resolver.py`, `test_player_stats_crawler.py`, `test_roster_crawler.py`, `test_schedule_crawler.py`) use realistic mock data structures matching API response shapes. No real HTTP calls. Error paths (401, 403, 5xx) are tested. `CrawlResult` accumulation is verified.

### O-7: resolve-opponents CLI test exists

`test_cli_data.py:test_resolve_opponents_invokes_resolver` tests the `bb data resolve-opponents` CLI command. The E-120-01 regression test (`test_resolve_opponents_passes_db_path`) verifies that `resolve_opponents()` correctly passes `db_path` to `load_config`.

### O-8: Error-path coverage is good

- `test_bootstrap.py` covers credential failure and crawl failure propagation
- `test_scouting_crawler.py` covers `CredentialExpiredError` and `ForbiddenError`
- `test_opponent_crawler.py` covers 403/401 responses
- `test_opponent_resolver.py` covers 403/401/5xx/404 responses
- `test_cli_data.py` tests CLI error paths via mocked failures

### O-9: No PII in test data

Test files use synthetic data (fake team names, generated UUIDs, placeholder stats). Files with synthetic credential data (test_config.py) use obviously fake values. No real emails, names, or tokens detected.

## Summary

The test suite is well-structured with solid isolation, comprehensive coverage, and correct use of project patterns (TeamRef, CrawlResult, FK satisfaction). The primary finding is the schema setup inconsistency (W-1) where 6 files bypass `run_migrations()` — this is a consolidation opportunity rather than a correctness bug today, but it creates drift risk as the migration system evolves. No critical issues found.
