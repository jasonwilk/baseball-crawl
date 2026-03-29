# IDEA-059: Opponent Flow Pipeline and Display Gaps

## Status
`CANDIDATE`

## Summary
The opponent scouting flow (dashboard + `bb data scout`) has four gaps discovered during E-187 evaluation and live testing: (1) the web pipeline (`run_scouting_sync`) has no spray crawl or gc_uuid resolution, (2) the member sync's `_discover_opponents()` auto-resolves opponents but never triggers scouting for them, (3) the three-tier gc_uuid resolver doesn't use public_id filtering, and (4) the dashboard opponent detail page has no data-depth context. The reports flow was fixed by E-186/E-187; the opponent flow was not.

## Why It Matters
- **Spray charts missing on dashboard**: When a coach clicks "Sync" on an opponent in the admin UI, `run_scouting_sync` runs. It does crawl + load but NO spray crawl. Spray data is never fetched for opponents synced via the web UI.
- **Auto-resolved opponents never scouted**: When a member team syncs, `_discover_opponents()` seeds opponent_links and auto-resolves 7 of 25 opponents via progenitor_team_id and POST /search. But it never triggers `run_scouting_sync` for any of them. Auto-scout only exists in the admin HTTP routes (manual connect + search resolve via BackgroundTasks). Verified 2026-03-29: Freshman Grizzlies sync resolved 7 opponents, 3 were never scouted at all (Elkhorn North, Lincoln Lutheran, Lincoln NW).
- **gc_uuid resolution gap**: The CLI (`bb data scout`) runs `_resolve_missing_gc_uuids()` which uses the three-tier cascade. Tier 3 (POST /search) uses name + season_year matching without public_id filtering -- ambiguous for common names ("Lincoln" returns dozens of results). The report generator's approach (search by name, filter by public_id exact match) is more reliable but only exists in `src/reports/generator.py`.
- **Dashboard shows raw numbers with no context**: The opponent detail page dumps stat tables with no PA/IP badges, no heat-map coloring, no data-depth indicators. The "never suppress, always contextualize" philosophy from E-187 applies here too, but the dashboard wasn't in scope.

## Root Cause Analysis

### Gap 1: No spray crawl in `run_scouting_sync`
`src/pipeline/trigger.py:378` (`run_scouting_sync`) runs `ScoutingCrawler.scout_team()` + `ScoutingLoader.load_team()` then marks done. It never instantiates `ScoutingSprayChartCrawler` or `ScoutingSprayChartLoader`. Compare with `src/cli/data.py:360` which has Steps 1.5 (gc_uuid resolution), 2 (spray crawl), and 3 (spray load) after the main crawl+load.

### Gap 1b: Auto-resolved opponents never scouted (verified 2026-03-29)
`src/pipeline/trigger.py:183` (`_discover_opponents()`) runs the schedule seeder (line 262) + `OpponentResolver.resolve()` (lines 278-280). The resolver successfully resolves opponents via progenitor_team_id and POST /search fallback, writing to `opponent_links` and calling `finalize_opponent_resolution()`. But `_discover_opponents()` **never enqueues `run_scouting_sync`** for resolved opponents -- it simply returns.

Auto-scout triggering exists **only** in admin HTTP routes (`src/api/routes/admin.py` lines 2519-2528 for manual connect, lines 2821-2829 for search resolve) via FastAPI `background_tasks.add_task()`. The background pipeline has no equivalent mechanism.

Evidence: Freshman Grizzlies member sync resolved 7 opponents. Zero `scouting_crawl` crawl_jobs were created. Teams 137 (Elkhorn North), 138 (Lincoln Lutheran), and 32 (Lincoln NW) were newly resolved during this sync and have **zero scouting_runs** -- the system knows who they are but never fetched their data.

### Gap 2: Three-tier resolver vs. public_id filtering
`src/gamechanger/resolvers/gc_uuid_resolver.py` Tier 3 (`_tier3_search`, line 236):
- Strips classification suffixes from the team name
- Searches POST /search
- Filters by `season_year` match
- Requires exactly 1 match (ambiguous = skip)

`src/reports/generator.py` (`_resolve_gc_uuid`, line 370):
- Searches POST /search with the full team name
- Filters by `public_id` exact match (zero ambiguity)
- Returns immediately on match

The report generator's approach is strictly better for any team that has a `public_id` (which all report-generated and opponent-linked teams do). The three-tier resolver's value is Tiers 1-2 (cached data, zero API calls) for teams that share games with member teams. The ideal approach: try Tiers 1-2 first, then fall back to public_id filtering (not the ambiguous name+year search).

### Gap 3: Dashboard data-depth context
`src/api/templates/dashboard/opponent_detail.html` shows batting/pitching tables with no threshold system, no PA/IP badges, no heat-map coloring. The spray chart threshold is 1 BIP (actually more aligned with "show what you have" than the report's 3 BIP). The "never suppress, always contextualize" principle should apply here -- PA/IP badges would help coaches on the dashboard just as much as on reports.

## Possible Fix Approaches

### For Gap 1 (spray in web pipeline)
Add spray crawl + load steps to `run_scouting_sync` after the main load, mirroring the CLI's Steps 1.5-3. Also add gc_uuid resolution before the spray crawl. This is ~20 lines of new code following the existing pattern in `src/cli/data.py`.

### For Gap 2 (resolver improvement)
Add a Tier 3b to `gc_uuid_resolver.py` that uses public_id filtering when `public_id` is available. Keep Tiers 1-2 (cached data, zero API calls) and the existing Tier 3 (name+year for teams without public_id). The cascade becomes: Tier 1 (boxscores) → Tier 2 (progenitor) → Tier 3a (search + public_id filter, when public_id available) → Tier 3b (search + name+year, legacy fallback).

Alternatively, factor out the report generator's `_resolve_gc_uuid` into a shared utility and use it wherever public_id is available.

### For Gap 3 (dashboard context)
Add PA/IP badges to the opponent detail batting and pitching tables. This is template-only work (no Python changes if PA is already in the template context). Heat-map coloring on the dashboard is a larger scope question.

## Scope If Promoted

An epic from this idea would likely include:
- Story 1: Add spray crawl + gc_uuid resolution to `run_scouting_sync` in `src/pipeline/trigger.py`
- Story 2: Add auto-scout triggering to `_discover_opponents()` for newly resolved opponents (call `run_scouting_sync` sequentially after resolver returns)
- Story 3: Improve gc_uuid resolver to use public_id filtering when available
- Story 4: Add PA/IP badges to dashboard opponent detail page (apply "never suppress, always contextualize" from E-187)
- Story 5: Context-layer updates (document pipeline parity requirement between CLI and web trigger)
- Probably 4-5 stories total

## Dependencies & Blockers
- [x] E-186 (spray chart fix) -- complete
- [ ] E-187 (threshold calibration + display philosophy) -- in progress. The display philosophy rule from E-187-03 defines the principles this epic would apply to the dashboard.

## Open Questions
- Should the dashboard opponent detail page get heat-map coloring too, or just PA/IP badges?
- Should the three-tier resolver be refactored, or should the report generator's approach be extracted as a shared utility?
- Should the spray crawl in `run_scouting_sync` use the same gc_uuid resolution as the report generator, or the three-tier cascade?

## Notes
- The CLI (`bb data scout`) has a complete pipeline (crawl + load + gc_uuid resolution + spray crawl + spray load). The web pipeline (`run_scouting_sync`) is missing the last 3 steps. This is a feature gap, not a bug -- spray was added to the CLI in E-176 but never ported to the web trigger.
- The dashboard spray chart threshold (1 BIP) is actually more aligned with "show what you have" than the report threshold (3 BIP). Don't "fix" it upward.
- E-187's "never suppress, always contextualize" display philosophy rule will fire on `src/api/routes/dashboard.py` and `src/api/templates/**` -- providing guidance to the agent implementing Gap 3.

---
Created: 2026-03-29
Last reviewed: 2026-03-29
Review by: 2026-06-27
