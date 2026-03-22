# E-147: Team Season Year and Cohort-Based Dashboard Navigation

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add a `season_year` column to the `teams` table so each team carries its own year, then rewrite the dashboard navigation to group teams into year-based cohorts. This eliminates the bug where two identically-named teams (e.g., "Standing Bear Freshman Grizzlies" 2025 vs. 2026) appear side-by-side because `get_team_year_map()` derives year from stat data rather than from team metadata.

## Background & Context
Two teams named "Standing Bear Freshman Grizzlies" appear side-by-side in the dashboard, both showing "2026". Team 8 is last year's freshman team (should be 2025), team 78 is this year's (2026). Both map to 2026 because `get_team_year_map()` in `src/api/db.py` derives year from a UNION+JOIN on stat tables, and both teams have stats in the `2026-spring-hs` season. The root cause: the `teams` table has no `season_year` column.

**Expert consultation completed:**
- **data-engineer**: Identified 7 team INSERT paths, recommended `season_year INTEGER` column, prioritized admin add-team as golden path. `TeamProfile` dataclass already parses `year` from API -- it's discarded at the INSERT boundary.
- **ux-designer**: Designed cohort selector -- year dropdown filters `permitted_team_infos` server-side so teams from different years never appear together. Default: current year. "(current)" label. "← Current season" back-link when viewing history.
- **api-scout**: Confirmed `season_year` available on `GET /me/teams` and `GET /teams/{team_id}` (authenticated), `team_season.year` on `GET /public/teams/{public_id}` (public).

## Goals
- Every team row carries its own `season_year` value, eliminating the expensive stat-table-derived year lookup
- Dashboard shows one year-cohort at a time -- coaches never see duplicate team names across seasons
- Existing teams (8 and 78) are correctly assigned to their actual years (2025 and 2026)
- Pipeline paths that create or update teams propagate `season_year` when the value is available

## Non-Goals
- Full `season_name` column (deferred -- just year for now)
- Changing the `seasons` table or season_id derivation
- Per-game or per-stat year resolution (this is team-level metadata)
- Mobile credential pipeline changes

## Success Criteria
- `SELECT season_year FROM teams WHERE id IN (8, 78)` returns `2025` and `2026` respectively
- Dashboard at `/dashboard` with no `?year=` param shows only current-year teams
- Dashboard at `/dashboard?year=2025` shows only 2025 teams and a "← Current season" link
- `get_team_year_map()` reads from `teams.season_year` (no stat table UNION)
- Admin add-team correctly persists `season_year` from the GameChanger API response

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-147-01 | Migration, backfill, and year-map rewrite | TODO | None | - |
| E-147-02 | Admin add-team: thread season_year into INSERT | TODO | E-147-01 | - |
| E-147-03 | Pipeline self-healing: propagate season_year on sync | TODO | E-147-01 | - |
| E-147-04 | Cohort-based dashboard navigation | TODO | E-147-01 | - |

## Dispatch Team
- software-engineer
- data-engineer

## Technical Notes

### TN-1: Migration Strategy
New migration `004_add_team_season_year.sql`. Adds `season_year INTEGER` to `teams`. Existing rows get NULL. `ALTER TABLE ADD COLUMN` is safe per migration conventions (tracked by `_migrations`, runs once). Existing migrations: 001 (initial schema), 002 (user role), 003 (crawl_jobs).

### TN-2: Backfill Logic
The stat-derived year logic (`MAX(s.year)` over stat tables) is exactly what causes the bug -- it maps team 8 to 2026 instead of 2025. The backfill MUST NOT reuse that logic.

Instead, the migration includes only explicit corrections for the two known-wrong teams:
- `UPDATE teams SET season_year = 2025 WHERE id = 8;`
- `UPDATE teams SET season_year = 2026 WHERE id = 78;`

All other teams start with `season_year = NULL`. The self-healing pipeline (E-147-03) fills NULLs from the API on the next sync. This is correct because: (a) the API is the authoritative source for `season_year`, (b) the number of existing teams is small, and (c) a sync cycle after deployment fills all remaining values automatically.

### TN-3: get_team_year_map() Rewrite
Rewrite `get_team_year_map()` in `src/api/db.py` (~line 1205) to read from `teams.season_year` instead of the UNION+JOIN on stat tables. NULL values fall back to current calendar year. The function signature stays the same (`team_ids: list[int] → dict[int, int]`) so callers don't change.

### TN-4: API Field Mapping
| Source | Endpoint | Field Path | Type |
|--------|----------|-----------|------|
| Authenticated | `GET /me/teams` | `season_year` | int |
| Authenticated | `GET /teams/{team_id}` | `season_year` | int |
| Public | `GET /public/teams/{public_id}` | `team_season.year` | int |

`TeamProfile` dataclass in `src/gamechanger/team_resolver.py` already parses `year` from the API response. The value is available but discarded at INSERT boundaries.

### TN-5: Team INSERT Paths (7 total)
1. **Admin add-team** (`src/api/routes/admin.py:~710`) -- golden path, `TeamProfile.year` already available → Story E-147-02
2. **Roster loader stub** (`src/gamechanger/loaders/roster.py:~329`) -- NULL ok on insert → Story E-147-03
3. **Season stats loader stub** (`src/gamechanger/loaders/season_stats_loader.py:~597`) -- can derive from season_id → Story E-147-03
4. **Game loader stub** (`src/gamechanger/loaders/game_loader.py:~1087`) -- can derive from game date → Story E-147-03
5. **Opponent resolver** (`src/gamechanger/crawlers/opponent_resolver.py:~366`) -- NULL ok on insert → Story E-147-03
6. **Scouting crawler stubs** (`src/gamechanger/crawlers/scouting.py:~394,~537`) -- NULL on insert → Story E-147-03
7. **Scouting loader** (`src/gamechanger/loaders/scouting_loader.py:~560`) -- NULL ok on insert → Story E-147-03

For paths 2-7, NULL is acceptable on INSERT. The self-healing pattern (Story E-147-03) adds UPDATE logic to the member crawl and scouting pipeline to fill `season_year` when it's available from the API response.

### TN-6: Cohort Filtering
Server-side filtering in dashboard routes: filter `permitted_team_infos` to teams matching `active_year` before passing to templates. The route logic changes:
- `available_years` derived from `set(team_year_map.values())` (the output of `get_team_year_map()`), NOT from `SELECT DISTINCT season_year` — the SQL DISTINCT drops NULLs, which would exclude teams relying on the NULL-fallback-to-current-year behavior in TN-3
- `year_team_infos` filtering already exists (line ~369 in dashboard.py) -- it just needs to use the new column-based year map
- Add `current_year` template variable (max `season_year` among active teams)
- **NULL-fallback behavior**: Teams with `season_year = NULL` fall back to current calendar year in `get_team_year_map()` (TN-3). These teams participate in the current-year cohort until the self-healing pipeline fills their `season_year`. This is intentional -- no special handling needed.

The `_team_selector.html` macro needs a new `current_year` parameter for the "(current)" label and "← Current season" back-link. The macro is imported without `with context` (`{% from ... import team_selector %}`), so `current_year` must be passed explicitly. All 4 page templates that call the macro (`team_stats.html`, `team_pitching.html`, `game_list.html`, `opponent_list.html`) must be updated to pass the new argument.

Edge cases:
- **Empty year cohort**: If `?year=` specifies a year with no matching teams (stale bookmark), fall back silently to `current_year`.
- **Single-year span**: When only one year exists, the macro shows a static `<span>` (no dropdown). No "(current)" label needed -- the absence of the dropdown already implies it's the only/current year.

### TN-7: Loader Warning Guard
When a loader processes data for a team, if `teams.season_year` is set and the loaded data's year (from season_id or game date) doesn't match, log a warning. Do not block the load -- mismatches may be legitimate (e.g., offseason data). This is observability, not enforcement.

## Open Questions
None -- all resolved during exploration.

## History
- 2026-03-22: Created from exploration findings (DE, UX, api-scout)
- 2026-03-22: Spec review iteration 1 -- 5 findings accepted and incorporated (backfill logic rewrite, migration renumber to 004, TeamProfile path fix, member crawl path fix, template file list + TN-6 correction)
- 2026-03-22: Spec review iteration 2 -- 3 findings accepted and incorporated (NULL-fallback cohort behavior documented in TN-6 and E-147-04, admin two-phase form threading in E-147-02, roster.py added to E-147-03 warning guard scope)
- 2026-03-22: Holistic review -- 6 findings incorporated (member crawl new API call in E-147-03, scouting resolve_team() call in E-147-03, admin 3-step flow with redirect params in E-147-02, empty year cohort fallback in E-147-04, single-year span label in E-147-04/TN-6, test fixture dependency in E-147-01)
- 2026-03-22: PM self-review -- 2 implementer-convenience notes added to E-147-03 (gc_uuid vs integer PK clarification, skip API call when season_year already set)
- 2026-03-22: Spec review iteration 3 -- 2 of 4 findings accepted and incorporated (available_years must derive from get_team_year_map() values not SQL DISTINCT which drops NULLs; nullable-safe encoding of season_year in redirect params to avoid str(None)="None" bug). 2 dismissed (gc_uuid URL pattern already clarified in Notes; SE routing correct for crawler/loader work).
- 2026-03-22: Epic set to READY after 3 spec review iterations + 2 holistic reviews (18 findings total: 16 accepted, 2 dismissed)
