# E-176: Fix Spray Charts for Scouting Reports and Opponent Pipeline

## Status
`COMPLETED`

## Overview
Spray charts are completely broken for tracked opponent teams that lack a `gc_uuid`. The scouting spray crawler skips them, and the report generator works around this with inline API crawling that duplicates crawler logic, uses fragile exact-name matching, and was never deployed. This epic fixes the pipeline properly: the crawler learns a boxscore-UUID fallback, the report generator stops doing inline crawl/load, gc_uuid is opportunistically resolved where possible, and all tracked teams get spray coverage regardless of how they were added to the system.

## Background & Context

**Immediate trigger**: Team 33 ("Lincoln Northeast Reserve/Freshman Rockets", `public_id=VJdJBnYuw4Ya`) has `gc_uuid=NULL`. The scouting spray crawler (`ScoutingSprayChartCrawler`) does `SELECT gc_uuid FROM teams WHERE public_id = ?` and skips any team where the result is NULL. Zero spray data is crawled or loaded for this team.

**Report generator workaround (commit e802bae)**: Added `_resolve_and_crawl_spray()` with three resolution tiers: (1) DB lookup, (2) POST /search exact name match, (3) boxscore-UUID extraction. This was never deployed (container not rebuilt) and has architectural issues:
- Duplicated crawl logic (`_crawl_spray_via_boxscore_uuids` reimplements the core crawl loop)
- Exact name matching is effectively dead code for compound team names
- Report generator now does inline API crawling, mixing concerns

**API behavior**: The spray endpoint (`GET /teams/{gc_uuid}/schedule/events/{event_id}/player-stats`) requires a UUID path parameter but returns BOTH teams' data regardless of which team's UUID is used. This means any participant's UUID works -- if we can find the opponent's UUID from a boxscore, we can fetch spray data for both teams.

**Boxscore key structure**: Each boxscore JSON has two top-level keys: one is the scouted team's `public_id` slug and the other is the other team's `gc_uuid` (UUID format). When fetching boxscores FROM a tracked team's perspective, the UUID key belongs to their opponent. When fetching FROM a member team's perspective, the UUID key belongs to the opponent (which may be the tracked team we want).

**opponent_links gap**: Teams added via the admin "generate report" flow (paste GC URL) get a `teams` row with `membership_type=tracked` but no `opponent_links` entry. The scouting spray crawler's `crawl_all()` discovers teams via `opponent_links`, so direct-add teams are invisible to it.

**Research**: Three agents (SE, DE, API Scout) investigated. Findings confirmed all failure modes and ranked gc_uuid resolution approaches:
1. Extract from member-team boxscore keys (BEST -- zero extra API calls, already cached)
2. `progenitor_team_id` from opponents endpoint (GOOD -- already cached, NULL for ~14% manual-entry opponents)
3. POST /search with shortened name (FALLBACK -- needs fuzzy matching heuristic)
4. Per-game opponent UUID from scouting boxscores (WORKAROUND -- not the team's own gc_uuid, but valid for calling the spray endpoint per-game)

No expert consultation required -- this is a pure Python pipeline fix with well-understood API behavior confirmed by prior research.

## Goals
- Tracked opponents get spray chart data in scouting reports and dashboards without requiring `gc_uuid` to be pre-populated on the team row
- `bb data scout` crawls spray data for all tracked opponents, including those without `gc_uuid`, using a boxscore-UUID fallback
- The report generator renders from existing DB data only -- no inline API crawling for spray charts
- `gc_uuid` is opportunistically resolved and stored on team rows when discoverable from cached data
- All tracked teams get spray pipeline coverage regardless of how they were added (opponent discovery vs. direct URL)

## Non-Goals
- Resolving `gc_uuid` for 100% of tracked teams -- some will never be resolvable (no shared games with member teams, no progenitor_team_id, ambiguous search results)
- Changing the spray chart endpoint or API behavior
- Modifying the spray chart loader logic (it already handles both teams' data correctly)
- Adding new API endpoints or authenticated calls for gc_uuid resolution (we use only cached data and existing endpoints)

## Success Criteria
- Running `bb data scout` for a tracked team with `gc_uuid=NULL` produces spray chart files and DB rows (using the boxscore-UUID fallback)
- Generating a scouting report for a team with `gc_uuid=NULL` includes spray charts (rendered from DB data populated by the pipeline, not inline crawling)
- The report generator contains zero spray-specific crawl or UUID resolution code
- Teams added via direct scouting URL appear in `bb data scout` spray crawl output
- All existing tests pass; new tests cover the boxscore-UUID fallback path and gc_uuid resolution cascade

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-176-01 | Boxscore-UUID fallback in scouting spray crawler | DONE | None | - |
| E-176-02 | Report generator spray cleanup | DONE | E-176-01 | - |
| E-176-03 | Opportunistic gc_uuid resolution cascade | DONE | None | - |
| E-176-04 | Spray pipeline coverage for direct-add teams | DONE | E-176-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Boxscore-UUID Extraction Pattern
Each scouting boxscore JSON file at `data/raw/{season_id}/scouting/{public_id}/boxscores/{event_id}.json` has two top-level keys: one is the `public_id` slug (not a UUID), the other is a `gc_uuid` (matches UUID regex `^[0-9a-f]{8}-...$`). The UUID key belongs to the OTHER team in that game -- not the scouted team.

The spray endpoint returns both teams' data regardless of which team's UUID is used. So using the opponent's UUID from a boxscore is valid for fetching spray data for both teams in that game.

The UUID regex for extraction: `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$` (case-insensitive).

### TN-2: gc_uuid Resolution Cascade
When resolving a tracked team's `gc_uuid`, apply this cascade (stop at first success):

1. **Member-team boxscore extraction**: Scan member team boxscore directories (`data/raw/{season}/teams/{member_gc_uuid}/boxscores/*.json`). Each boxscore has two top-level keys: the member team's `gc_uuid` and the opponent's `gc_uuid`. Extract the UUID key that does NOT match the member team's own `gc_uuid` (= the opponent's UUID). Then cross-reference with the `games` table: look up the game by `games.game_id` (which stores the event_id value; the boxscore filename stem is the event_id) and verify that the target tracked team's `teams.id` appears as `home_team_id` or `away_team_id`. If confirmed, the extracted opponent UUID is the target tracked team's `gc_uuid`. Zero API calls. **Prerequisite**: The games table must be populated (i.e., the resolver must run after the main scouting crawl/load, not before).

2. **progenitor_team_id from cached opponents data**: Check `data/raw/{season}/teams/{member_gc_uuid}/opponents.json` for entries where the `name` field matches the target team's name (case-insensitive). The opponents.json payload contains `root_team_id`, `owning_team_id`, `name`, `is_hidden`, `progenitor_team_id` -- no `public_id` field. The `progenitor_team_id` field (when non-NULL) is a reliable gc_uuid. NULL for ~14% of opponents (manual entry without GC lookup).

3. **POST /search with shortened name**: Strip classification suffixes (e.g., "Reserve/Freshman", "Varsity", "JV") from the team name and search with the shortened version. Accept a single unambiguous match for the correct season year. Skipped when `season_year` is None (results cannot be validated). This is the only tier that makes an API call.

Store the resolved `gc_uuid` on the team row using `UPDATE teams SET gc_uuid = ? WHERE id = ? AND gc_uuid IS NULL` (conditional -- never overwrite an existing value).

### TN-3: Report Generator Architecture
The report generator (`src/reports/generator.py`) runs the full scouting pipeline synchronously in Step 4: `ScoutingCrawler.scout_team()` + `ScoutingLoader.load_team()`. This is correct -- the generator's purpose is "paste URL -> get report," which requires crawling.

The spray-specific code added in commit e802bae (`_resolve_and_crawl_spray`, `_build_boxscore_uuid_map`, `_crawl_spray_via_boxscore_uuids`, `_resolve_gc_uuid_via_search`) is what must be removed. After the main scouting crawl/load completes, the generator should call `ScoutingSprayChartCrawler.crawl_team()` + `ScoutingSprayChartLoader.load_all()` -- the same pipeline path used by `bb data scout`. With Story 01's boxscore-UUID fallback in place, this handles `gc_uuid=NULL` teams correctly.

### TN-4: Direct-Add Team Discovery
`ScoutingSprayChartCrawler.crawl_all()` currently queries only the `opponent_links` table:
```sql
SELECT DISTINCT public_id FROM opponent_links
WHERE public_id IS NOT NULL AND is_hidden = 0
```
Teams added via the admin "generate report" flow have no `opponent_links` row -- they exist only in the `teams` table with `membership_type='tracked'`.

**Schema note**: `opponent_links` and `team_opponents` are two SEPARATE tables (both are tables, neither is a view):
- `team_opponents`: opponent relationship registry (`our_team_id` → `opponent_team_id`)
- `opponent_links`: GC opponents endpoint resolution tracker (has `root_team_id`, `public_id`, `is_hidden`, `resolution_method`, `resolved_team_id`)

The fix: extend `crawl_all()` to UNION the existing `opponent_links` query with tracked teams that have no `opponent_links` entry. The second branch must exclude teams that have an `opponent_links` row with `is_hidden=1` (to preserve hidden-team filtering). The implementer should design the exact query to handle this edge case -- the key constraint is: all tracked teams with a `public_id` get coverage, hidden teams stay hidden, no duplicates.

### TN-5: Files Touched Per Story
| File | 01 | 02 | 03 | 04 |
|------|----|----|----|----|
| `src/gamechanger/crawlers/scouting_spray.py` | M | | | M |
| `src/reports/generator.py` | | M | | |
| `tests/test_scouting_spray_crawler.py` | M | | | M |
| `tests/test_report_generator.py` | | M | | |
| `src/gamechanger/resolvers/__init__.py` | | | C | |
| `src/gamechanger/resolvers/gc_uuid_resolver.py` | | | C | |
| `tests/test_gc_uuid_resolver.py` | | | C | |
| `src/cli/data.py` | | | M | |

M = modify, C = create. Stories 01 and 04 touch the same files -- Story 04 depends on Story 01.

## Open Questions
- None -- all technical questions resolved by prior research.

## History
- 2026-03-28: Created
- 2026-03-28: Set to READY after 3 review passes (23 findings: 13 accepted, 10 dismissed). E-173 compatibility verified -- no stale assumptions.
- 2026-03-28: Set to ACTIVE, dispatch started
- 2026-03-28: All stories DONE, epic COMPLETED

### Review Scorecard (Dispatch)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-176-01 | 4 | 4 | 0 |
| Per-story CR -- E-176-02 | 0 | 0 | 0 |
| Per-story CR -- E-176-03 | 2 | 1 | 1 |
| Per-story CR -- E-176-04 | 2 | 1 | 1 |
| **Total** | **8** | **6** | **2** |

### Documentation Assessment
No documentation impact -- this epic fixes internal pipeline behavior without changing user-facing features, CLI commands, or deployment configuration.

### Context-Layer Assessment
1. New convention/pattern: No
2. Architectural decision: No
3. Footgun/failure mode: No
4. Agent behavior change: No
5. Domain knowledge: No
6. New CLI command/workflow: No

### Review Scorecard (Planning)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 7 | 3 | 4 |
| Internal iteration 1 -- Holistic team (PM + SE) | 11 | 7 | 4 |
| Codex iteration 1 | 5 | 3 | 2 |
| **Total** | **23** | **13** | **10** |
