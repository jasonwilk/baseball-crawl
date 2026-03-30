# E-189: Opponent Flow Pipeline and Display Parity

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Close four gaps in the opponent scouting flow so that the web pipeline (admin UI "Sync") produces the same data as the CLI (`bb data scout`), auto-resolved opponents get scouted without manual intervention, the gc_uuid resolver uses precise public_id filtering, and the dashboard opponent detail page displays PA/IP badges and heat-map coloring consistent with the standalone reports.

## Background & Context

E-173 fixed the core opponent workflow (resolution write-through, auto-scout on manual resolve, unified "Find on GC" page, dashboard sort, terminology). E-186 and E-187 fixed spray charts and display calibration for standalone reports. But four gaps remain between the CLI pipeline and the web pipeline, and between the reports display and the dashboard display:

1. **Web pipeline missing spray stages**: `run_scouting_sync` in `src/pipeline/trigger.py` runs `ScoutingCrawler` + `ScoutingLoader` but never instantiates `ScoutingSprayChartCrawler` or `ScoutingSprayChartLoader`. The CLI (`bb data scout`) has Steps 1.5 (gc_uuid resolution), 2 (spray crawl), 3 (spray load) -- none exist in the web trigger.

2. **Auto-resolved opponents never scouted**: `_discover_opponents()` in trigger.py runs the schedule seeder + `OpponentResolver.resolve()`, which successfully auto-resolves ~7 of ~25 opponents. But it never triggers `run_scouting_sync` for them. Auto-scout exists only in admin HTTP routes (manual connect + search resolve via BackgroundTasks). Verified 2026-03-29: Freshman Grizzlies sync resolved 7 opponents; 3 were never scouted at all.

3. **gc_uuid resolver ambiguity**: The three-tier cascade in `gc_uuid_resolver.py` Tier 3 strips classification suffixes and searches by name + season_year. For common names ("Lincoln"), this returns dozens of results and the "exactly 1 match" filter fails. The report generator's approach (search by name, filter by public_id exact match) is strictly better for teams that have a public_id. The resolver already receives `public_id` as a parameter but doesn't use it.

4. **Dashboard opponent detail lacks data-depth context**: `opponent_detail.html` shows batting/pitching tables with GP annotations but no PA/IP badges, no heat-map coloring per E-187's display philosophy. The standalone reports have graduated heat intensity and PA/IP badges; the dashboard should match.

Promoted from IDEA-059. No expert consultation required for Gaps 1-3 (pure pipeline parity -- mirroring existing CLI behavior). Baseball-coach consulted for Gap 4 (display requirements). Software-engineer consulted for implementation feasibility. No claude-architect consultation required for E-189-05 -- the story codifies implemented behavior from Stories 01-02 into CLAUDE.md, requiring no architectural decisions.

## Goals
- `run_scouting_sync` produces the same data artifacts as `bb data scout` (spray charts + gc_uuid resolution)
- Opponents auto-resolved during member sync are automatically scouted without manual "Sync" clicks
- gc_uuid resolver uses public_id filtering when available, eliminating ambiguous name-only matches
- Dashboard opponent detail page displays PA/IP badges and graduated heat-map coloring matching standalone reports

## Non-Goals
- Changes to the scouting crawlers or loaders themselves (only wiring existing modules into the web trigger)
- Dashboard opponent list page changes (E-173 already delivered sort + data status indicators)
- New stat columns or schema changes
- Spray chart rendering changes (threshold, colors, etc.)
- Print view heat-map coloring changes (PA/IP badges are in scope; heat-map on print is not)
- Changes to `bb data scout` CLI (already complete)

## Success Criteria
- When an operator clicks "Sync" on an opponent in the admin UI, spray chart data is fetched and loaded (not just batting/pitching stats)
- After a member team sync that auto-resolves opponents, those opponents have scouting data within minutes without manual intervention
- gc_uuid resolution succeeds for teams with common names (e.g., "Lincoln") when public_id is available
- The dashboard opponent detail page shows PA badges on batting rows, IP badges on pitching rows, and graduated heat-map coloring consistent with the display philosophy rule

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-189-01 | Add spray stages and gc_uuid resolution to web scouting pipeline | DONE | None | - |
| E-189-02 | Auto-scout opponents resolved during member sync | DONE | E-189-01 | - |
| E-189-03 | Add public_id filtering to gc_uuid resolver Tier 3 | DONE | None | - |
| E-189-04 | Add PA/IP badges and heat-map coloring to dashboard opponent detail | DONE | None | - |
| E-189-05 | Context-layer: codify pipeline parity requirement | DONE | E-189-01, E-189-02 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### TN-1: Pipeline Parity Pattern

The CLI (`bb data scout` in `src/cli/data.py:346-435`) runs five stages after auth:
1. Scouting crawl (`ScoutingCrawler.scout_team`)
2. Scouting load (`ScoutingLoader.load_team`)
3. gc_uuid resolution (`_resolve_missing_gc_uuids` -> `resolve_gc_uuid`)
4. Spray crawl (`ScoutingSprayChartCrawler.crawl_team`)
5. Spray load (`ScoutingSprayChartLoader.load_all`)

The web trigger (`run_scouting_sync` in `src/pipeline/trigger.py:378-504`) runs only stages 1-2. Story 01 adds stages 3-5.

The spray crawl requires gc_uuid (the `ScoutingSprayChartCrawler` calls `GET /teams/{gc_uuid}/schedule/events/{event_id}/player-stats`). Teams without gc_uuid are skipped with an INFO log -- this is the existing behavior in the CLI and should be preserved in the web trigger.

Spray stages are non-fatal: if the main crawl+load succeeds but spray fails, the crawl_job should still be marked "completed" (spray is additive enrichment, not core data). This matches the CLI's behavior where spray errors set exit_code=1 but the main pipeline result is reported separately.

### TN-2: Auto-Scout After Discovery

`_discover_opponents()` runs the seeder + resolver. Record the current UTC timestamp before the resolver runs. After the resolver completes, query `opponent_links` for rows where `resolved_at >= sync_start_time` (newly resolved during this cycle) and the resolved team has `public_id IS NOT NULL`, excluding opponents that already have a `crawl_jobs` row with `status = 'running'` (any age -- matching admin route's `_has_running_job()` behavior) or `status = 'completed'` within the last 24 hours. For each, create a `crawl_jobs` row (sync_type='scouting_crawl', status='running') and call `run_scouting_sync` sequentially (not as BackgroundTasks -- we're already in a background context).

The sequential approach is correct here because:
- We're already in a background pipeline (no request to respond to)
- Rate limiting between API calls is built into the GameChangerClient
- Parallelism would risk overwhelming the API

Create a `crawl_jobs` row for each auto-scout (same as the admin route pattern) so the admin UI shows "Syncing..." status.

### TN-3: gc_uuid Resolver Improvement

The `resolve_gc_uuid` function in `src/gamechanger/resolvers/gc_uuid_resolver.py` already receives `public_id` as a parameter (line 47). Tier 3 (`_tier3_search`, line ~236) currently:
1. Strips classification suffixes from team name
2. Searches POST /search
3. Filters by season_year match
4. Requires exactly 1 match

The improvement adds a preferred path when `public_id` is available:
1. Search POST /search with the team name (same as now)
2. Filter results by `result.public_id == public_id` (exact match)
3. If found, return `result.id` as gc_uuid
4. If not found, fall back to the existing name+year logic

This matches the report generator's approach (`src/reports/generator.py:_resolve_gc_uuid`, line ~370) but integrated into the existing tier cascade rather than extracted as a shared utility.

**season_year gate relaxation**: Currently `resolve_gc_uuid()` skips Tier 3 entirely when `season_year is None` (lines 111-115). With the public_id filtering path, season_year is not needed -- the exact public_id match is unambiguous. When `public_id` is available, Tier 3 should proceed even if `season_year is None`. The existing name+season_year fallback path still requires season_year.

### TN-4: Dashboard Display Parity

The dashboard opponent detail template (`src/api/templates/dashboard/opponent_detail.html`) currently shows GP annotations on rate stats. The display philosophy rule (`.claude/rules/display-philosophy.md`) fires on this template and mandates PA/IP badges and graduated heat intensity.

**PA badges on batting rows**: PA = AB + BB + HBP + SHF. All four fields are already in the template context (query in `get_opponent_scouting_report`, `src/api/db.py:690`). Display as `<span class="...">N PA</span>` next to each rate stat, replacing the current GP annotation.

**IP badges on pitching rows**: `ip_outs` is already in the template context. Display as formatted IP (using the existing `ip_display` filter) as a badge next to ERA/K9/WHIP.

**Heat-map coloring**: Apply the graduated heat intensity tiers from `.claude/rules/display-philosophy.md` to the batting and pitching tables. The route (`src/api/routes/dashboard.py:opponent_detail`) must compute qualified counts and max-heat tiers, then pass per-player heat levels to the template. The same thresholds apply: 5 PA batting, 6 IP (18 outs) pitching.

**Print view**: `opponent_print.html` should also get PA/IP badges for consistency. Heat-map coloring in print is optional (black text on white is fine for print).

**Existing heat-map logic**: `src/reports/renderer.py` already contains heat-map computation functions: `_max_heat_for_depth()`, `_percentile_rank()`, `_percentile_to_level()`, `_compute_pa()`, plus tier constants `_BATTING_HEAT_TIERS` and `_PITCHING_HEAT_TIERS`. These are currently private to the renderer. The implementer may extract shared utilities or reimplement for the dashboard route.

### TN-5: File Ownership

| File | Stories |
|------|---------|
| `src/pipeline/trigger.py` | E-189-01, E-189-02 |
| `src/gamechanger/resolvers/gc_uuid_resolver.py` | E-189-03 |
| `src/api/routes/dashboard.py` | E-189-04 |
| `src/api/templates/dashboard/opponent_detail.html` | E-189-04 |
| `src/api/templates/dashboard/opponent_print.html` | E-189-04 |
| Tests for each story | E-189-01, E-189-02, E-189-03, E-189-04 |
| Context-layer files (CLAUDE.md, rules) | E-189-05 |

Stories 01 and 02 both modify `src/pipeline/trigger.py` -- 01 must run before 02 (02 depends on 01's changes being staged). Stories 03 and 04 touch entirely separate files and are order-independent -- they can run in any order relative to each other and relative to the 01-02 chain.

## Open Questions
None -- all gaps are well-characterized from IDEA-059 research and code reading.

## History
- 2026-03-29: Created. Promoted from IDEA-059. Expert consultations with baseball-coach (display priorities) and software-engineer (implementation feasibility) completed during discovery.
- 2026-03-30: Set to READY after 2 internal review iterations + Codex review (23 findings: 19 accepted, 4 dismissed).
- 2026-03-30: COMPLETED. All 5 stories DONE. Delivered: (1) web scouting pipeline parity with CLI -- spray crawl/load + gc_uuid resolution added to `run_scouting_sync`; (2) auto-scout for opponents resolved during member sync -- eliminates manual "Sync" clicks; (3) gc_uuid resolver Tier 3 uses public_id filtering for unambiguous resolution of common team names; (4) dashboard opponent detail page now shows PA/IP badges and graduated heat-map coloring matching standalone reports; (5) CLAUDE.md codifies pipeline parity requirement and auto-scout trigger pattern.

### Documentation Assessment
Trigger 1 (new feature ships): YES -- PA/IP badges and heat-map coloring on dashboard opponent detail. However, `docs/coaching/scouting-reports.md` already documents the opponent detail page and was updated 2026-03-29 for E-163. The new badges are visual enhancements to existing stats (no new data or workflow), and `docs/coaching/understanding-stats.md` already covers PA thresholds and sample size guidance. The web pipeline parity (spray stages, auto-scout) is operator-invisible -- it just makes the existing "Sync" button produce more complete data. No new admin workflows or commands. **Verdict: No documentation update required** -- the feature is a display enhancement to documented pages, not a new workflow or concept.

### Context-Layer Assessment
1. **New convention or pattern introduced?** YES -- pipeline parity requirement (web = CLI). Handled by E-189-05 (CLAUDE.md updated).
2. **Existing convention changed or deprecated?** NO -- no conventions changed.
3. **New agent capability or workflow?** NO -- no agent changes.
4. **File path or architecture change that affects routing?** NO -- no new files that change routing.
5. **Lesson learned that should inform future work?** NO -- execution was clean (6 findings, all accepted, 0 dismissed).
6. **Integration pattern that other agents need to know?** YES -- auto-scout trigger pattern (three resolution paths). Handled by E-189-05 (CLAUDE.md updated).
**Verdict: Context-layer impact fully addressed by E-189-05.** No additional claude-architect dispatch needed.

### Review Scorecard (Planning)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 7 | 1 |
| Internal iteration 1 -- Holistic team (PM+SE+api-scout) | 9 | 7 | 2 |
| Codex review round 1 | 6 | 5 | 1 |
| Internal iteration 2 -- CR spec audit | 0 | 0 | 0 |
| Internal iteration 2 -- Holistic team (PM) | 0 | 0 | 0 |
| **Total** | **23** | **19** | **4** |

### Review Scorecard (Implementation)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-189-01 (2 rounds) | 1 | 1 | 0 |
| Per-story CR -- E-189-02 | 0 | 0 | 0 |
| Per-story CR -- E-189-03 | 0 | 0 | 0 |
| Per-story CR -- E-189-04 | 0 | 0 | 0 |
| Per-story CR -- E-189-05 | skipped (context-layer) | - | - |
| CR integration review (pass 1) | 0 | 0 | 0 |
| CR integration review (pass 2, post-remediation) | 0 | 0 | 0 |
| Codex code review (round 1) | 5 | 5 | 0 |
| Codex code review (round 2) | 5 | 4 | 1 |
| **Total** | **11** | **10** | **1** |
