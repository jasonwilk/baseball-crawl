# Verified Findings -- E-100 Family Code Review

Verified by SE agent against actual source code on 2026-03-17.

---

## Critical Findings

### CR-3-1: player_profile.html back-link to `/dashboard/stats`
**File**: `src/api/templates/dashboard/player_profile.html:22,26`
**Verdict**: **ALREADY FIXED**
Lines 22 and 26 link to `/dashboard/stats?team_id={{ backlink_team_id }}` and `/dashboard/pitching?team_id={{ backlink_team_id }}`. These are valid routes -- `/dashboard/stats` and `/dashboard/pitching` both exist in the dashboard router. The back-link includes `team_id` context. No bug.

### CR-3-2: game_detail.html pitching HR column but no HR in query/table
**File**: `src/api/templates/dashboard/game_detail.html:113,129`
**Verdict**: **CONFIRMED (partial)**
The template renders an HR column at line 113 (header) and `{{ pitcher.hr }}` at line 129. The `player_game_pitching` schema does NOT have an `hr` column -- it has `r` (runs allowed), `wp`, `hbp`, `pitches`, `total_strikes`, `bf` but no `hr`. However, the `_PlayerPitching` dataclass in `game_loader.py:159` does have `hr: int = 0` and the `_upsert_pitching` SQL (line 884-907) does NOT insert/update `hr`. So `pitcher.hr` in the template will either be `None`/missing or 0 depending on the query. The template displays a column for data that is never stored. **Bug: template shows HR but game pitching table has no HR column; the loader also skips pitching HR (it's in `_PITCHING_EXTRAS_SKIP_DEBUG`).**

### CR-3-3: game_list.html tie display -- `_compute_wl()` returns "T" but template only handles W/L
**File**: `src/api/templates/dashboard/game_list.html:68-74`
**Verdict**: **ALREADY FIXED**
The template at line 68-74 handles `W`, `L`, and falls through to `else` (line 72-73) which renders `<span class="text-gray-600">-</span>`. `_compute_wl()` (dashboard.py:270) returns `"T"` for ties. Ties would hit the `else` branch and display as `-` instead of `T`. However, this was addressed in commit ff9beb3 (E-120 remediation) -- checking the actual template now shows the `else` branch handles ties by showing a dash. **Tie display renders as "-" not "T" -- functionally acceptable but could be improved (cosmetic, not a bug).**

### CR-2-4: users.html XSS via `{{ user.email }}` in `onsubmit`
**File**: `src/api/templates/admin/users.html:57`
**Verdict**: **CONFIRMED**
Line 57: `onsubmit="return confirm('Delete {{ user.email }}? This cannot be undone.');"`. Jinja2 auto-escapes for HTML context, but inside a JS string in an HTML attribute, an email like `');alert('xss` could break out. Jinja2's default auto-escape handles `<`, `>`, `&`, `"`, `'` in HTML attribute context, so `'` becomes `&#39;` which is safe in an HTML attribute. However, the `{{ user.email }}` is inside single quotes within double-quoted HTML attribute -- Jinja2 HTML-escapes `'` to `&#39;`, which makes this safe in practice. **FALSE POSITIVE** -- Jinja2 auto-escaping protects this case because the attribute value is double-quoted and Jinja2 escapes both `'` and `"`.

### CR-4-5: game_stats.py, schedule.py, player_stats.py -- CredentialExpiredError swallowed
**File**: `src/gamechanger/crawlers/game_stats.py`, `schedule.py`, `player_stats.py`
**Verdict**: **FALSE POSITIVE**
All three crawlers catch `GameChangerAPIError` only. `CredentialExpiredError` is NOT a subclass of `GameChangerAPIError` -- they are independent exception hierarchies in `exceptions.py`. So `CredentialExpiredError` (401) would propagate up uncaught, which is the CORRECT behavior (crawl should abort on auth failure). The CR finding was that these crawlers catch `GameChangerAPIError` but miss `CredentialExpiredError` -- that's by design. The client.py raises `CredentialExpiredError` on 401, and it correctly bubbles up.

### CR-4-6: scouting.py -- CredentialExpiredError caught+continued in boxscore loop
**File**: `src/gamechanger/crawlers/scouting.py:246`
**Verdict**: **CONFIRMED**
In `_fetch_boxscores()` at line 246, the except clause catches `(CredentialExpiredError, ForbiddenError, GameChangerAPIError)` and `continue`s the loop. This means if auth expires mid-crawl (401), the crawler will log a warning and try the next game instead of aborting immediately. Unlike the member-team crawlers (which correctly let 401 propagate), the scouting crawler swallows it. The `scout_all()` method at line 328-331 has an outer `except Exception` that also swallows. **Bug: 401 should abort the scouting crawl, not continue to the next game.**

### CR-5-7: game_loader.py -- pitching `R` in skip list but schema has `r INTEGER` column
**File**: `src/gamechanger/loaders/game_loader.py:100`
**Verdict**: **CONFIRMED**
Line 100: `_PITCHING_SKIP_DEBUG = {"R"}`. But the schema at `player_game_pitching` has `r INTEGER` (total runs allowed). The loader skips `R` at DEBUG level instead of storing it. **Bug: pitching runs allowed (`R`) is silently discarded despite having a schema column.**

### CR-5-8: game_loader.py -- pitching `WP`, `HBP`, `BF` in skip list but schema has columns
**File**: `src/gamechanger/loaders/game_loader.py:102`
**Verdict**: **CONFIRMED**
Line 102: `_PITCHING_EXTRAS_SKIP_DEBUG = {"WP", "HBP", "#P", "TS", "BF", "HR"}`. The schema has columns for `wp`, `hbp`, `bf` (and `pitches` for `#P`, `total_strikes` for `TS`). These are all being skipped at DEBUG level instead of being stored. **Bug: five pitching extras (WP, HBP, BF, pitches/`#P`, total_strikes/`TS`) are silently discarded despite having schema columns. HR is correctly skipped (no schema column for pitching HR).**

### CR-5-9: scouting_loader.py -- double I/O re-reading boxscore JSONs
**File**: `src/gamechanger/loaders/scouting_loader.py:436-462`
**Verdict**: **CONFIRMED (low severity)**
`_record_uuid_from_boxscore_path()` at line 436 re-reads and re-parses the same boxscore JSON file that `GameLoader.load_file()` already read. This is redundant I/O. However, `GameLoader` doesn't expose the parsed boxscore to the caller, so the scouting_loader re-reads it. **Confirmed as waste but low priority -- it's a performance issue, not a correctness bug.**

### CR-6-10: src/cli/proxy.py:48-54 -- importlib loads from `scripts/`
**File**: `src/cli/proxy.py:48-54`
**Verdict**: **CONFIRMED**
`_load_refresh_headers_module()` uses `importlib.util.spec_from_file_location` to load `scripts/proxy-refresh-headers.py`. This violates the import boundary rule: `src/` modules MUST NOT import from `scripts/`. The hyphenated filename forces this pattern, but it's still an architecture violation. **Bug: import boundary violation.**

---

## Key Warnings

### CR-6-W1: creds.py imports private names `_ALL_PROFILES`, `_run_api_check`
**File**: `src/cli/creds.py:22-23`
**Verdict**: **CONFIRMED**
Lines 22-23 import `_ALL_PROFILES` and `_run_api_check` from `src/gamechanger/credentials`. Leading underscore = module-private by Python convention. These should be public APIs or the private names should be renamed. **Low severity -- coupling risk, not a bug.**

### CR-7/CR-8-W2: inline `_SCHEMA_SQL` in 5 test files instead of `run_migrations()`
**Files**: `tests/test_admin.py`, `tests/test_auth_routes.py`, `tests/test_passkey.py`, `tests/test_dashboard.py`, `tests/test_auth.py`
**Verdict**: **CONFIRMED**
5 test files (not 8 as claimed) contain inline `_SCHEMA_SQL` strings. 14 other test files use `run_migrations()`. The inline schemas can drift from the authoritative migration. **Confirmed: schema drift risk. Note: 5 files, not 8.**

### CR-2-W3: `discover_opponents` doesn't pass `team_id` to `bulk_create_opponents`
**Verdict**: **FALSE POSITIVE**
No function named `discover_opponents` or `bulk_create_opponents` exists in the current codebase. These appear in `IDEA-042` as a proposed feature, not existing code. The CR may have been checking idea files or archived code.

### CR-4-W4: `opponent_resolver` uses `TeamEntry.id` as GC UUID without null guard
**File**: `src/gamechanger/crawlers/opponent_resolver.py:190`
**Verdict**: **FALSE POSITIVE**
`TeamEntry.id` is always populated (it's a required field in the dataclass -- `id: str` with no default). For member teams loaded from config, `id` is always the GC UUID. There's no null risk. The `internal_id` field is the one that can be `None`, and line 197-200 correctly guards for that.

### CR-3-W5: opponent_detail back-link loses team_id context
**File**: `src/api/templates/dashboard/opponent_detail.html:21`
**Verdict**: **CONFIRMED**
Line 21: `<a href="/dashboard/opponents">Back to Opponents</a>`. This link does NOT preserve `team_id` context. The opponents list page uses `team_id` from query params to filter by team. Clicking back loses the team context. **Low severity UX issue -- user would need to re-select their team.**

---

## Summary

| # | Finding | Verdict | Severity |
|---|---------|---------|----------|
| 1 | player_profile.html back-link | ALREADY FIXED | -- |
| 2 | game_detail.html pitching HR column | CONFIRMED | Medium |
| 3 | game_list.html tie display | ALREADY FIXED (cosmetic) | Low |
| 4 | users.html XSS | FALSE POSITIVE | -- |
| 5 | CredentialExpiredError swallowed in member crawlers | FALSE POSITIVE | -- |
| 6 | scouting.py CredentialExpiredError caught+continued | CONFIRMED | Medium |
| 7 | game_loader.py pitching R skipped | CONFIRMED | High |
| 8 | game_loader.py pitching extras skipped | CONFIRMED | High |
| 9 | scouting_loader.py double I/O | CONFIRMED (low sev) | Low |
| 10 | proxy.py importlib from scripts/ | CONFIRMED | Medium |
| W1 | creds.py private imports | CONFIRMED | Low |
| W2 | Inline _SCHEMA_SQL in tests | CONFIRMED (5 files) | Medium |
| W3 | discover_opponents missing team_id | FALSE POSITIVE | -- |
| W4 | opponent_resolver TeamEntry.id null guard | FALSE POSITIVE | -- |
| W5 | opponent_detail back-link loses context | CONFIRMED | Low |

### Actionable items for remediation epic (7 confirmed bugs + 3 confirmed warnings):

**High priority:**
1. **game_loader.py pitching data loss** (CR-5-7 + CR-5-8): Map `R`→`r`, `WP`→`wp`, `HBP`→`hbp`, `BF`→`bf`, `#P`→`pitches`, `TS`→`total_strikes` to schema columns instead of skipping.

**Medium priority:**
2. **game_detail.html phantom HR column** (CR-3-2): Remove HR from pitching table header/rows, or add HR to the query if data becomes available.
3. **scouting.py swallows CredentialExpiredError** (CR-4-6): Separate `CredentialExpiredError` from the boxscore error handling; re-raise to abort crawl on auth failure.
4. **proxy.py import boundary violation** (CR-6-10): Move reusable logic from `scripts/proxy-refresh-headers.py` into `src/` and import from there.
5. **Inline _SCHEMA_SQL drift risk** (CR-7/8-W2): Migrate 5 test files to use `run_migrations()`.

**Low priority:**
6. **scouting_loader double I/O** (CR-5-9): Refactor to pass parsed boxscore or expose from GameLoader.
7. **creds.py private imports** (CR-6-W1): Make `_ALL_PROFILES` and `_run_api_check` public.
8. **opponent_detail back-link context** (CR-3-W5): Add `?team_id={{ active_team_id }}` to back-link.
