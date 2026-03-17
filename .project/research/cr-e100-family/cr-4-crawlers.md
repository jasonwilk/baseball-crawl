# CR-4: Crawlers Review

**Scope**: `src/gamechanger/crawlers/` -- game_stats.py, opponent.py, opponent_resolver.py, player_stats.py, roster.py, schedule.py, scouting.py

## Critical Issues

### 1. CredentialExpiredError swallowed in game_stats.py (game_stats.py:177)

`GameStatsCrawler._crawl_team` catches `GameChangerAPIError` and then `Exception`, but `CredentialExpiredError` is **not** a subclass of `GameChangerAPIError` -- they are independent exception hierarchies (see `exceptions.py:14` and `exceptions.py:45`). When a 401 occurs:

- The `except GameChangerAPIError` clause does NOT catch it.
- The `except Exception` clause catches it, logs "Unexpected error", and **continues** to the next game.

This means an expired token causes the crawler to attempt every remaining game with a dead token, generating N error log lines instead of aborting immediately. Contrast with `opponent.py:263-271` and `opponent_resolver.py:151-152,277-278` which correctly catch and re-raise `CredentialExpiredError`.

**Same issue in**: `schedule.py:101` and `player_stats.py:96` -- both have the same `GameChangerAPIError` + bare `Exception` pattern without `CredentialExpiredError` handling.

### 2. CredentialExpiredError swallowed in scouting.py (scouting.py:197,218,246)

`ScoutingCrawler._fetch_schedule`, `_fetch_and_write_roster`, and `_fetch_boxscores` all catch `(CredentialExpiredError, ForbiddenError, GameChangerAPIError)` in a single except clause and log+continue. This means a 401 during scouting does NOT abort the run -- it logs a warning and continues to the next game/step with a dead token.

The `_fetch_boxscores` loop (line 246) is especially wasteful: on a 401, it will attempt every remaining game's boxscore with an expired token.

Contrast with `opponent.py:263-271` which correctly re-raises `CredentialExpiredError` to abort.

### 3. scouting.py `_finalize_crawl_result` writes "running" not "completed" (scouting.py:182)

**After further analysis: this is intentional**, not a bug. The crawl phase writes `"running"`, and the CLI layer calls `update_run_load_status("completed")` after the load phase succeeds. This is a two-phase status lifecycle. **Reclassified to Observation** -- the design is correct but the `"running"` status name is misleading for "crawl done, load pending". A value like `"crawled"` would be clearer.

## Warnings

### 1. opponent_resolver.py uses TeamEntry.id as GC UUID without validation (opponent_resolver.py:190)

`_resolve_team` uses `team.id` for the API call (`/teams/{team.id}/opponents`). `TeamEntry.id` is documented as "GameChanger team UUID (member teams) or public_id slug (tracked teams)" -- but this code assumes it's always a UUID. For member teams loaded via `load_config_from_db`, `team.id` is `row["gc_uuid"] or str(row["id"])` (config.py:207), so if `gc_uuid` is NULL, `team.id` would be the stringified INTEGER PK, which would produce an invalid API URL. This is unlikely for member teams (they should always have `gc_uuid`), but there's no guard.

### 2. scouting.py scout_all queries opponent_links but not team_opponents (scouting.py:311-313)

The query `SELECT DISTINCT public_id FROM opponent_links WHERE public_id IS NOT NULL AND is_hidden = 0` only looks at `opponent_links`. The schema also has `team_opponents` (junction table linking member teams to tracked opponents). If opponents are registered in `team_opponents` but not yet in `opponent_links` (before resolution runs), they won't be scouted. This may be by design (scouting depends on resolution), but worth noting.

### 3. scouting.py _ensure_team_row uses public_id as name stub (scouting.py:386-387)

When inserting a new team row, the name is set to the `public_id` slug (e.g., `"8O8bTolVfb9A"`). While `opponent_resolver._ensure_opponent_team_row` has logic to update UUID-as-name stubs (line 375), there's no equivalent for public_id-as-name stubs. These stub names persist until something else updates them.

### 4. Unused import: datetime in roster.py (roster.py:29)

`from datetime import datetime, timezone` is imported but never used in the module.

## Minor Issues

### 1. game_stats.py _crawl_team parameter type mismatch (game_stats.py:107)

`_crawl_team(self, team_id: str, season: str)` takes `team_id` as a string (GC UUID). This is correct for the current usage but the type hint could be more descriptive (e.g., a type alias for GC UUIDs vs. public_id slugs vs. INTEGER PKs). Low priority -- the current code works correctly.

### 2. Inconsistent freshness defaults across crawlers

- `schedule.py`: 1 hour default
- `roster.py`, `player_stats.py`, `opponent.py`, `scouting.py`: 24 hours default
- `game_stats.py`: No freshness check (existence-only, which is correct since completed games don't change)

This is likely intentional (schedules change more frequently) but not documented anywhere as a design decision.

## Observations

### Positive patterns found across all crawlers:

1. **`from __future__ import annotations`**: Present in all 7 files.
2. **`pathlib.Path`**: Used consistently; no `os.path` usage.
3. **`logging` module**: Used throughout; no `print()` for operational output.
4. **No imports from `scripts/`**: Import boundary respected.
5. **No credential exposure**: No hardcoded tokens, no auth header logging.
6. **Idempotency**: All crawlers implement either freshness-based or existence-based skip logic.
7. **Error isolation**: Individual failures don't abort the overall crawl (except CredentialExpiredError where handled).
8. **Rate limiting**: Built into the HTTP session factory (`src/http/session.py`) with min 1s delay + jitter per request, so crawlers don't need explicit `time.sleep()`. The `opponent_resolver.py` adds additional 1.5s delays on top of the session-level rate limiting.
9. **TeamRef/TeamEntry usage**: `opponent_resolver.py` correctly uses `team.id` (GC UUID) for API calls and `team.internal_id` (INTEGER PK) for DB foreign keys. Other crawlers that only write to disk (not DB) correctly use `team.id` for both API calls and file paths.
10. **`noqa: BLE001`**: Properly annotated on all broad `except Exception` clauses.
11. **Manual-link protection in opponent_resolver.py**: The COALESCE-based upsert SQL correctly preserves `resolution_method='manual'` rows during auto-resolution passes.
