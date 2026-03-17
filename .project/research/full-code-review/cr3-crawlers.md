# Code Review: Data Pipeline -- Crawlers

**Scope**: All crawler source files (`src/gamechanger/crawlers/`), pipeline orchestration (`src/pipeline/`), and their test files.
**Date**: 2026-03-17
**Reviewer**: code-reviewer agent (full-project audit, not story-based)
**Tests**: All 165 tests pass.

---

## Critical Issues

### C-1: `CredentialExpiredError` silently caught by schedule, roster, game_stats, and player_stats crawlers

**Files**: `src/gamechanger/crawlers/schedule.py:101`, `src/gamechanger/crawlers/roster.py:92`, `src/gamechanger/crawlers/game_stats.py:177`, `src/gamechanger/crawlers/player_stats.py:96`

These four crawlers catch `Exception` (with `# noqa: BLE001`) in their `crawl_all()` loops. This is correct for per-team resilience, but unlike `opponent.py` and `opponent_resolver.py`, **they do not distinguish `CredentialExpiredError` from other exceptions**. A 401 (expired token) on the first team is logged as a warning and the crawl continues to the next team -- where it will also get a 401, and the next, and so on.

The `opponent.py` crawler correctly re-raises `CredentialExpiredError` to abort immediately. The `scouting.py` crawler catches `CredentialExpiredError` in `_fetch_schedule` and `_fetch_boxscores` and treats it as a recoverable error per team (defensible since it's partially using public endpoints, though debatable). But `schedule.py`, `roster.py`, `game_stats.py`, and `player_stats.py` all use **authenticated-only endpoints** and should abort on 401 rather than burning through every team with a dead token.

**Impact**: When credentials expire mid-crawl, all four crawlers silently fail every team instead of aborting with a clear "credentials expired" message. The operator sees N errors in the log instead of one actionable abort. The crawl orchestrator (`crawl.py`) would also benefit from receiving the `CredentialExpiredError` to stop the pipeline early.

**Recommendation**: Add `except CredentialExpiredError: raise` before `except Exception` in each crawler's `crawl_all()` loop, matching the pattern in `opponent.py:263-271`.

### C-2: `scouting.py` sets status to `"running"` after crawl phase, never reaches `"completed"` if load fails

**File**: `src/gamechanger/crawlers/scouting.py:182`

After a successful crawl, `_finalize_crawl_result` writes `status='running'` to `scouting_runs` (line 182). The intent is that the CLI layer later calls `update_run_load_status()` to set `'completed'` after loading succeeds. However, `_is_scouted_recently()` (line 436) checks for `status = 'completed'` -- meaning a team stuck in `'running'` (e.g., load failed or was never called) will be re-scouted on every run, defeating the freshness check.

This is a design choice rather than a bug (fail-open is arguably correct for scouting freshness), but it means:
1. If the CLI layer doesn't call `update_run_load_status()` after loading, freshness gating never kicks in.
2. There's no TTL or cleanup for stale `'running'` rows -- they accumulate indefinitely.

**Impact**: Moderate. The scouting pipeline will re-crawl the same opponents repeatedly if the load step fails or is skipped, wasting API calls.

---

## High Priority

### H-1: No test coverage for `ScoutingCrawler` -- test file is missing

**File**: `tests/test_crawlers/test_scouting_crawler.py` -- does not exist

The scouting crawler (`src/gamechanger/crawlers/scouting.py`, 571 lines) has **zero test coverage**. It is the most complex crawler in the project, with:
- DB writes (team stubs, season rows, scouting_runs tracking)
- A three-step crawl chain (schedule -> roster -> boxscores)
- Freshness gating via `_is_scouted_recently()`
- Season derivation from game timestamps
- UUID extraction from boxscore keys
- Status lifecycle management

This is a significant test gap. The scouting pipeline handles opponent data and is called from `bb data scout`.

### H-2: `_is_fresh` duplicated identically in 3 crawlers (roster, schedule, player_stats)

**Files**: `src/gamechanger/crawlers/roster.py:149-162`, `src/gamechanger/crawlers/schedule.py:221-234`, `src/gamechanger/crawlers/player_stats.py:154-167`

The `_is_fresh(self, path, freshness_hours)` method is copy-pasted identically across three crawler classes. A fourth variant exists in `opponent.py:327-339` (without the `freshness_hours` parameter -- uses `self._freshness_hours` directly). This should be a shared utility function in the `crawlers` package `__init__.py` or a mixin.

**Impact**: Maintenance burden. If the freshness check logic needs to change (e.g., to handle timezone issues or add jitter), it must be updated in four places.

### H-3: `load.py` runner functions use `config: object` instead of `CrawlConfig` type hint

**File**: `src/pipeline/load.py:29,58,97`

The three runner functions (`_run_roster_loader`, `_run_game_loader`, `_run_season_stats_loader`) all type-hint `config` as `object` instead of `CrawlConfig`. This loses type safety -- the functions access `config.member_teams` and `config.season` which are `CrawlConfig`-specific attributes.

**Convention violated**: `.claude/rules/python-style.md` line 8: "Use type hints for all function parameters and return types in `src/`."

### H-4: `src/pipeline/__init__.py` missing `from __future__ import annotations`

**File**: `src/pipeline/__init__.py:1`

The module has only a docstring and is missing the required `from __future__ import annotations` import.

**Convention violated**: `.claude/rules/python-style.md` line 9.

### H-5: `roster.py` has unused import `from datetime import datetime, timezone`

**File**: `src/gamechanger/crawlers/roster.py:29`

The `datetime` and `timezone` names are imported but never referenced anywhere in the file. The file uses `time.time()` for freshness checks, not `datetime`.

### H-6: `player_stats.py` has unused constant `_SEASON_STATS_USER_ACTION`

**File**: `src/gamechanger/crawlers/player_stats.py:40`

The constant `_SEASON_STATS_USER_ACTION = "data_loading:team_stats"` is defined but never used anywhere in the module.

### H-7: `scouting.py` catches `CredentialExpiredError` and `ForbiddenError` on public schedule endpoint

**File**: `src/gamechanger/crawlers/scouting.py:197`

`_fetch_schedule` uses `client.get_public()` which never sends auth headers, so it should never receive 401 or 403 responses. Yet the exception handler catches `CredentialExpiredError` and `ForbiddenError`. While harmless (the public client raises `GameChangerAPIError` for unexpected status codes), this is misleading -- it suggests auth errors are expected on a public endpoint.

---

## Medium Priority

### M-1: `crawl.py` _build_crawlers uses `object` return type for factories

**File**: `src/pipeline/crawl.py:43`

`_build_crawlers()` returns `list[tuple[str, object]]` where the second element is a lambda factory. The `object` type hint discards the callable signature. Better: `list[tuple[str, Callable[[GameChangerClient, CrawlConfig], Any]]]`.

### M-2: `load.py` _LOADERS uses `object` for runner type

**File**: `src/pipeline/load.py:128`

`_LOADERS: list[tuple[str, object]]` loses the callable type information. The runners are `Callable[[sqlite3.Connection, CrawlConfig, Path], LoadResult]` but typed as `object`, requiring `# type: ignore[operator]` at the call site (line 196).

### M-3: `scouting.py` `_ensure_team_row` uses team identifier as `name` for stub rows

**File**: `src/gamechanger/crawlers/scouting.py:387,399`

When inserting a stub team row, the `name` column is set to the `public_id` or `gc_uuid` value. While the opponent resolver later updates UUID-as-name stubs, the `public_id`-as-name stubs in the scouting crawler are never updated to real team names by any downstream process. The team list in the admin UI would show slugs like `"8O8bTolVfb9A"` instead of team names.

### M-4: `scouting.py` `_record_uuid_from_boxscore` doesn't commit

**File**: `src/gamechanger/crawlers/scouting.py:524-531`

The method inserts stub team rows but doesn't call `db.commit()`. The insertions rely on the next `db.commit()` call elsewhere in the flow (e.g., `_finalize_crawl_result` at line 183). If an error occurs between the insert and the next commit, the stub rows are lost. This is minor since the rows are "best-effort" and will be re-discovered on the next run.

### M-5: No `RateLimitError` handling in any crawler

**Files**: All crawler modules in `src/gamechanger/crawlers/`

None of the crawlers import or handle `RateLimitError`. The `GameChangerClient` raises `RateLimitError` on 429 responses, but the crawlers' exception handlers only catch `GameChangerAPIError` (which does not include `RateLimitError` in its hierarchy). A 429 would propagate as an unhandled exception, killing the entire crawler run rather than being caught and counted as an error.

The client does `time.sleep(retry_after)` before raising `RateLimitError`, so there's a delay, but the exception still bubbles up. The `crawl.py` orchestrator's top-level `except Exception` would catch it and continue to the next crawler, but the per-team/per-game granularity of error handling is lost.

### M-6: Test helper functions (`_make_config`, `_make_client`) duplicated across 7 test files

**Files**: All test files in `tests/test_crawlers/`, `tests/test_scripts/test_crawl_orchestrator.py`, `tests/test_scripts/test_load_orchestrator.py`

Nearly identical helper functions are duplicated across every test file. A shared `conftest.py` with common fixtures would reduce duplication.

### M-7: `crawl.py` config loading for `source="db"` duplicates path resolution logic from `load.py`

**Files**: `src/pipeline/crawl.py:120-131`, `src/pipeline/load.py:157-165`

The `DATABASE_PATH` env var resolution logic (check env, resolve relative paths, fall back to default) is duplicated between the two orchestrators. This should be a shared helper.

---

## Low Priority

### L-1: `scouting.py` f-string in SQL `UPDATE` statement

**File**: `src/gamechanger/crawlers/scouting.py:289`

`update_run_load_status` uses an f-string to embed `completed_at` expression in SQL:
```python
completed_at = (
    "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
    if status == "completed"
    else "NULL"
)
self._db.execute(f"... completed_at = {completed_at} ...")
```

While not a SQL injection risk (the interpolated values are hardcoded string constants, not user input), f-strings in SQL are a code smell that makes auditing harder. A parameterized approach would be cleaner.

### L-2: Inconsistent `_DATA_ROOT` naming

**Files**: `src/gamechanger/crawlers/scouting.py:79`, vs all other crawlers

All crawlers and the pipeline modules define their own `_DATA_ROOT` constant. While consistent in value (`Path(__file__).resolve().parents[3] / "data" / "raw"`), having 6+ independent definitions of the same path is fragile.

### L-3: `game_stats.py` catches `Exception` but not `CredentialExpiredError` specifically

**File**: `src/gamechanger/crawlers/game_stats.py:177`

Same pattern as C-1 but at per-game granularity. On a 401, every remaining game in a team's schedule will also fail.

### L-4: Test files don't consistently test `RateLimitError` scenarios

**Files**: All test files in `tests/test_crawlers/`

No test in any crawler test file verifies behavior when `RateLimitError` is raised. Given M-5 above, this is a gap -- the current behavior (unhandled exception) isn't tested or documented.

---

## Positive Observations

### P-1: Consistent crawler architecture

All crawlers follow the same pattern: constructor takes `(client, config)`, `crawl_all()` returns `CrawlResult`, per-item errors are caught and counted, and overall crawl continues. This makes the code predictable and the orchestrator simple.

### P-2: Raw response preservation

Every crawler writes the unmodified API response to disk (`json.dumps(data, indent=2)`). No transformation or filtering happens in the crawl layer -- that's the loader's job. This follows the project's "raw -> processed pipeline" architecture cleanly.

### P-3: Idempotency is well-implemented

Freshness checks (file mtime for member crawlers, DB `scouting_runs` for scouting) prevent re-fetching data that hasn't changed. Game stats uses existence-only checks (completed game data never changes). All patterns are appropriate for their data characteristics.

### P-4: Good error containment in the orchestrators

Both `crawl.py` and `load.py` catch unhandled exceptions per-crawler/per-loader and continue to the next, with appropriate exit code signaling. The manifest captures per-crawler error counts.

### P-5: Excellent test coverage depth

The test suite covers happy paths, error paths, freshness/staleness, multi-team accumulation, API error continuation, and edge cases (missing files, missing fields, malformed data). The opponent_resolver tests are particularly thorough with real SQLite schema and FK validation.

### P-6: Correct pagination handling

`ScheduleCrawler` correctly uses `get_paginated()` for game-summaries (which is paginated) and `get()` for schedule (which is not). The `OpponentCrawler` and `OpponentResolver` also correctly use `get_paginated()` for the opponents endpoint.

### P-7: Security -- no credential leakage

No crawler logs, stores, or exposes authentication tokens. The scouting crawler correctly uses `get_public()` for unauthenticated endpoints and `get()` for authenticated ones, maintaining clean session separation.
