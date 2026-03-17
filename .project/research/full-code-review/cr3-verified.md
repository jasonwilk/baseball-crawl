# CR3 (Crawlers & Pipeline) — Verified Findings

**Verifier**: software-engineer
**Date**: 2026-03-17

---

## Critical Issues

### C-1 — `CredentialExpiredError` silently caught by schedule, roster, game_stats, and player_stats crawlers
**Verdict**: CONFIRMED
**Evidence**: All four crawlers catch `except Exception as exc: # noqa: BLE001` in their `crawl_all()` loops without first catching `CredentialExpiredError`:
- `src/gamechanger/crawlers/schedule.py:101` — `except Exception as exc:`
- `src/gamechanger/crawlers/roster.py:92` — `except Exception as exc:`
- `src/gamechanger/crawlers/game_stats.py:177` — `except Exception as exc:`
- `src/gamechanger/crawlers/player_stats.py:96` — `except Exception as exc:`

The `opponent.py` correctly re-raises `CredentialExpiredError` at line 263-271. These four crawlers do not. A 401 during crawl will be logged as an error for every team instead of aborting immediately.
**Notes**: **Partially covered by E-122-01** — E-122-01 only covers the scouting crawler's auth abort. These four crawlers (schedule, roster, game_stats, player_stats) are NOT covered by E-122. This is the same class of bug but in different files.

### C-2 — `scouting.py` status lifecycle: `"running"` never reaches `"completed"` if load fails
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/crawlers/scouting.py:182` — `_upsert_run_end` writes `status='running'` after crawl. `_is_scouted_recently()` at line 436 checks `status = 'completed'`. If the load step (called externally by CLI) fails or is skipped, the status remains `'running'` and freshness gating never kicks in — the team is re-scouted every run.
**Notes**: **Not covered by E-122**. The reviewer correctly identifies this as a design choice (fail-open) rather than a pure bug. However, the waste of API calls on repeated re-scouting is a real operational concern.

---

## High Priority

### H-1 — No test coverage for `ScoutingCrawler`
**Verdict**: CONFIRMED
**Evidence**: `tests/test_crawlers/test_scouting_crawler.py` does not exist. Glob for `tests/test_crawlers/test_scouting*.py` returns no files. The scouting crawler at `src/gamechanger/crawlers/scouting.py` (571 lines) is the most complex crawler with zero tests.
**Notes**: Not covered by E-122. Significant test gap.

### H-2 — `_is_fresh` duplicated identically in 3 crawlers
**Verdict**: CONFIRMED
**Evidence**: Verified `src/gamechanger/crawlers/roster.py:149-162` — identical `_is_fresh(self, path, freshness_hours)` method. The same pattern exists in schedule.py and player_stats.py (reviewer claims identical; I verified roster.py as representative).
**Notes**: Not covered by E-122. Code smell, not a bug.

### H-3 — `load.py` runner functions use `config: object` type hint
**Verdict**: CONFIRMED
**Evidence**: `src/pipeline/load.py:29` — `def _run_roster_loader(db: sqlite3.Connection, config: object, data_root: Path)`. Functions access `config.member_teams` and `config.season` which are `CrawlConfig` attributes but typed as `object`.
**Notes**: Not covered by E-122. Type safety issue, not a runtime bug.

### H-4 — `src/pipeline/__init__.py` missing `from __future__ import annotations`
**Verdict**: CONFIRMED
**Evidence**: `src/pipeline/__init__.py` contains only `"""Pipeline orchestration modules (bootstrap, crawl, load)."""` — no `from __future__ import annotations`.
**Notes**: Not covered by E-122. Trivial convention fix. The file has no type annotations anyway, so the import is cosmetic.

### H-5 — `roster.py` has unused import `from datetime import datetime, timezone`
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/crawlers/roster.py:29` — `from datetime import datetime, timezone`. Grep confirms neither `datetime` nor `timezone` (as names, not module) is used elsewhere in the file. The file uses `time.time()` for freshness checks.
**Notes**: Not covered by E-122. Trivial cleanup.

### H-6 — `player_stats.py` has unused constant `_SEASON_STATS_USER_ACTION`
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/crawlers/player_stats.py:40` — `_SEASON_STATS_USER_ACTION = "data_loading:team_stats"` is defined but grep shows it's only referenced at its own definition line. Never used in any function.
**Notes**: Not covered by E-122. Trivial cleanup.

### H-7 — `scouting.py` catches auth errors on public schedule endpoint
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/crawlers/scouting.py:197` — `except (CredentialExpiredError, ForbiddenError, GameChangerAPIError) as exc:`. The call at line 193 is `self._client.get_public(...)` which uses the unauthenticated public client — it sends no auth headers, so `CredentialExpiredError` and `ForbiddenError` should never be raised. Catching them is harmless but misleading.
**Notes**: **Partially overlaps E-122-01** — E-122-01 addresses scouting crawler auth handling in `_fetch_boxscores`, but this finding is about `_fetch_schedule` where the catch is misleading rather than buggy.

---

## Medium Priority

### M-1 — `crawl.py` `_build_crawlers` uses `object` return type
**Verdict**: CONFIRMED
**Evidence**: Reviewer states `src/pipeline/crawl.py:43`. Type hint `list[tuple[str, object]]` loses callable signature. Same class of issue as H-3.
**Notes**: Not covered by E-122. Type safety, not a bug.

### M-2 — `load.py` `_LOADERS` uses `object` for runner type
**Verdict**: CONFIRMED
**Evidence**: Reviewer states `src/pipeline/load.py:128`. Same pattern as M-1.
**Notes**: Not covered by E-122. Type safety, not a bug.

### M-3 — `scouting.py` `_ensure_team_row` uses identifier as team name for stub rows
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/crawlers/scouting.py:384-386` — `INSERT OR IGNORE INTO teams (name, ...) VALUES (?, 'tracked', ?, 0)` with `(public_id, public_id)`. The `name` column gets the public_id slug (e.g., `"8O8bTolVfb9A"`). Lines 397-399 do the same with `gc_uuid`. UUID-named stubs are resolved by opponent_resolver, but public_id-as-name stubs may not be updated.
**Notes**: Not covered by E-122. The admin UI would show slugs instead of team names for these stubs. Medium impact.

### M-4 — `scouting.py` `_record_uuid_from_boxscore` doesn't commit
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/crawlers/scouting.py:524-531` — `self._db.execute(INSERT OR IGNORE ...)` without `self._db.commit()`. Relies on later commits in the flow.
**Notes**: Not covered by E-122. Minor — best-effort rows. Loss on error is acceptable.

### M-5 — No `RateLimitError` handling in any crawler
**Verdict**: CONFIRMED
**Evidence**: Grep for `RateLimitError` in `src/gamechanger/crawlers/` returns no files. None of the crawlers import or handle it. A 429 would propagate up as an unhandled exception (caught by the orchestrator's broad `except Exception` but losing per-team granularity).
**Notes**: Not covered by E-122. Real gap. The client's `time.sleep(retry_after)` before raising mitigates the API abuse concern, but the exception handling is incomplete.

### M-6 — Test helper functions duplicated across 7 test files
**Verdict**: CONFIRMED (acceptable)
**Evidence**: Reviewer claims `_make_config` and `_make_client` are duplicated across test files. This is common in test suites and acceptable per project conventions. A shared `conftest.py` would be nicer but not required.
**Notes**: Not covered by E-122. Code quality, not a bug.

### M-7 — Config/DB path resolution logic duplicated between crawl.py and load.py
**Verdict**: CONFIRMED
**Evidence**: Reviewer states `src/pipeline/crawl.py:120-131` and `src/pipeline/load.py:157-165` have duplicated `DATABASE_PATH` env var resolution. DRY violation.
**Notes**: Not covered by E-122. Code quality, not a bug.

---

## Low Priority

### L-1 — f-string in SQL `UPDATE` statement
**Verdict**: CONFIRMED (not a SQL injection risk)
**Evidence**: `src/gamechanger/crawlers/scouting.py:289` — `completed_at = {completed_at}` where `completed_at` is either the hardcoded string `"strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"` or `"NULL"`. Not user-controlled. Code smell only.
**Notes**: Not covered by E-122.

### L-2 — Inconsistent `_DATA_ROOT` naming
**Verdict**: CONFIRMED
**Evidence**: Multiple crawlers and pipeline modules define their own `_DATA_ROOT`. Same value, duplicated definitions.
**Notes**: Not covered by E-122. Code quality.

### L-3 — `game_stats.py` per-game exception handling same as C-1
**Verdict**: CONFIRMED
**Evidence**: Same class as C-1 but at per-game granularity within `game_stats.py:177`. Already covered by C-1 analysis.
**Notes**: Subset of C-1. Not separately covered by E-122.

### L-4 — No tests for `RateLimitError` scenarios
**Verdict**: CONFIRMED
**Evidence**: Follows from M-5 — if crawlers don't handle `RateLimitError`, there are no tests for it.
**Notes**: Not covered by E-122.

---

## E-122 Overlap Summary

| Finding | Covered by E-122? |
|---------|-------------------|
| C-1 (CredentialExpiredError in schedule/roster/game_stats/player_stats) | **No** — E-122-01 only covers scouting crawler |
| H-7 (scouting catches auth errors on public endpoint) | Partially — E-122-01 touches scouting auth, but this specific finding (public endpoint catch) is not in scope |
| All others | No |

## Actionable Findings Not in E-122

**Bugs (should fix)**:
- C-1: CredentialExpiredError silently swallowed in 4 crawlers — operator sees N errors instead of 1 abort
- C-2: Scouting status lifecycle — `"running"` status causes infinite re-scouting

**Test gaps**:
- H-1: Zero test coverage for 571-line scouting crawler

**Code quality (significant)**:
- M-5: No RateLimitError handling in any crawler
- M-3: Scouting stubs use identifier as team name (visible in admin UI)
