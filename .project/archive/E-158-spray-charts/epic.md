# E-158: Spray Chart Pipeline and Dashboard Integration

## Status
`COMPLETED`

## Overview
Build a complete spray chart pipeline — crawl, load, render, display — so coaches can see where players (own and opponent) put the ball in play. Spray charts are a core scouting tool for defensive positioning and identifying hitter tendencies. This epic delivers PNG-rendered spray charts on the player profile and opponent scouting pages, updated automatically after each crawl.

## Background & Context
A research spike (`.project/research/spray-chart-spike/`) confirmed:
- The `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` endpoint returns spray chart data (`spray_chart_data.offense` / `spray_chart_data.defense`) with x/y coordinates per ball-in-play event. One call returns both teams' data.
- GameChanger's coordinate system and SVG field geometry were reverse-engineered from the JS bundle. The spike's `render.py` replicates GC's exact rendering.
- The `spray_charts` table exists in `migrations/001_initial_schema.sql` but is unpopulated and needs schema additions (event ID for idempotency, indexes).
- Opponent spray data is accessible using `progenitor_team_id` as the path parameter — confirmed working.
- Offensive spray coverage is ~93% (scorekeeper-dependent). Defensive is ~16%.

**Expert consultation completed:**
- **DE**: Schema needs `event_gc_id TEXT UNIQUE` for idempotent ingestion, plus query indexes. No `hr_location` column needed (compute at render time). Migration 006.
- **API-scout**: Use web Accept header (`application/json, text/plain, */*`). One call returns both teams' data. Use `progenitor_team_id` for opponents. Endpoint fully documented at `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md`.
- **UXD**: Full-width inline cards on player profile (below stats) and opponent detail (after Team Batting card). No side-by-side on mobile. Team chart first, per-player via links. No new nav tab needed.
- **Baseball-coach**: Opponent per-player is #1 priority (defensive positioning), then opponent team aggregate, then own-player season. Binary hit/out for bench use. 10 BIP minimum threshold with "small sample" flag for 5-9 BIP. Shape differentiation (filled circle vs X) for B&W printing is SHOULD HAVE. Defensive charts deferred.
- **SE**: Renderer at `src/charts/spray.py` (not under `src/api/`). Separate crawler class (different endpoint, Accept header, URL structure). Separate loader. Add numpy alongside matplotlib.

## Goals
- Populate the `spray_charts` table with ball-in-play events from the GameChanger API for both own-team and opponent players
- Render spray chart PNG images replicating GameChanger's field geometry and coordinate system
- Display per-player spray charts on the player profile page (own players and opponent players)
- Display opponent team aggregate spray chart and per-player spray chart links on the opponent scouting report
- Charts update automatically after each crawl completes ("real-time feel")

## Non-Goals
- Browser-native SVG/canvas rendering (future — PNG via matplotlib for now)
- Enhanced per-result-type color mode (future — binary hit/out for MVP)
- Shape differentiation for B&W printing (SHOULD HAVE per coach — defer to follow-on; filled circle vs X for hit/out)
- Defensive spray charts (only 16% API coverage)
- Per-game spray charts on the box score page (lower priority — defer)
- Full opponent season spray data from games not involving our teams (requires scouting pipeline integration — defer)
- Date range or opponent filtering (full-season aggregate sufficient for MVP)
- Pitcher handedness filter (SHOULD HAVE per coach — defer; requires bats/throws data not yet populated)
- Printable spray chart bundle (SHOULD HAVE per coach — defer to follow-on)
- Pre-generated image caching (on-the-fly rendering is sufficient at LSB scale)
- Spray chart data from the per-player season stats endpoint (`GET /teams/{team_id}/players/{player_id}/stats`) — per-game endpoint is sufficient and more efficient

## Success Criteria
- After a crawl completes for a team, spray chart data is in the database for all completed games
- The player profile page shows a spray chart image for any player with >= 10 BIP
- Players with 5-9 BIP see a "small sample" message with their BIP count (no chart rendered)
- The opponent scouting report shows a team aggregate spray chart and per-player links to spray charts
- Charts render correctly on mobile (375px viewport) as full-width images
- BIP count is shown alongside every chart ("Based on N balls in play")
- Re-running the loader for the same games does not create duplicate records

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-158-01 | Spray chart schema migration | DONE | None | - |
| E-158-02 | Spray chart crawler | DONE | None | - |
| E-158-03 | Spray chart loader | DONE | E-158-01, E-158-02 | - |
| E-158-04 | Spray chart rendering module | DONE | None | - |
| E-158-05 | Player profile spray chart | DONE | E-158-03, E-158-04 | - |
| E-158-06 | Opponent scouting spray chart | DONE | E-158-05 | - |

## Dispatch Team
- software-engineer
- data-engineer

## Technical Notes

### TN-1: Coordinate Transform
Raw API coordinates map to SVG space (320×480 viewBox) via:
```
svgX = 49.189 + rawX × 0.6926
svgY = 104.158 + rawY × 0.6447
```
Home plate ≈ SVG (160, 295). Center field ≈ SVG (160, 104). Y=0 is top (center field), Y increases toward home plate. The spike's `render.py` has the exact constants and field geometry paths.

### TN-2: API Response Structure
The player-stats endpoint returns `spray_chart_data` with two sections:
- `offense`: keyed by player UUID → array of events
- `defense`: keyed by player UUID → array of events

Each event has: `id` (UUID — the idempotency key), `createdAt` (Unix ms), `attributes.playResult`, `attributes.playType`, `attributes.defenders[]` (each with `location.x`, `location.y`, `position`, `error`).

Store only the **primary defender** (first in the `defenders` array) for each event. The primary defender's location represents where the ball was hit.

The `playResult` enum is open — known values include: `single`, `double`, `triple`, `home_run`, `batter_out`, `batter_out_advance_runners`, `fielders_choice`, `error`, `sac_fly`, `dropped_third_strike`, `other_out`, `offensive_interference`, `sacrifice_bunt_error`, `sacrifice_fly_error`. Do not use a CHECK constraint — store whatever the API returns.

### TN-3: Hit/Out Classification
GC binary classification (for rendering): `single`, `double`, `triple`, `home_run`, `dropped_third_strike` → **hit** (green #00D682). Everything else → **out** (red #B90018).

### TN-4: HR Zone Bubbles
Non-in-the-park home runs are counted by zone (left/center/right) based on the SVG x-coordinate and shown as numbered green circles outside the outfield arc. Zone classification is computed at render time — no schema column needed.

X-coordinate zone thresholds (in SVG space after coordinate transform):
- **Left field**: svgX < 109 (3B diamond is at x≈109)
- **Right field**: svgX > 211 (1B diamond is at x≈211)
- **Center field**: 109 ≤ svgX ≤ 211

These landmarks derive from the base diamond positions in the spike's field geometry constants. The spike's `render.py` calls `ev.get("hr_location")` but the spike's `fetch.py` never extracted the API's `attributes.hrLocation` field into its flattened event dicts — so the spike always gets None and defaults to center zone. The API does provide `attributes.hrLocation` (with values like `left_field`, `center_field`, `right_field`, `in_the_park`, `null`) but the production loader does not store it. Use the x-coordinate thresholds above when coordinates are available; fall back to center zone when they are not (see empty-defenders paragraph below).

**Empty defenders for over-the-fence HRs**: When `play_result` is `home_run` and `defenders[]` is empty (no fielder touched the ball), there are no x/y coordinates. Default to center zone. The spike handles this with `ev.get("hr_location") or "center"` — the production renderer should apply the same center-zone fallback.

### TN-5: Opponent Access Pattern
For opponent spray data, use `progenitor_team_id` as the `team_id` path parameter (NOT `gc_uuid`). The same `event_id` appears in both teams' views of the game. One API call returns both teams' spray data — the loader must determine player ownership per TN-10 (games table + team_rosters lookup).

### TN-6: Idempotent Ingestion
Each spray event has a stable GC UUID (`event_gc_id`). Use `INSERT OR IGNORE` keyed on the UNIQUE `event_gc_id` column. Do NOT delete-and-reinsert. Partial crawl failures are safe — already-stored events persist, new events append.

### TN-7: Thresholds and BIP Display

**Per-player charts** (player profile, opponent per-player links):
- **>= 10 BIP**: Render the spray chart. Show "Based on N balls in play" alongside the chart image.
- **5-9 BIP**: Show "Small sample — N balls in play" message. Do NOT render a chart (noise at this sample size). Do NOT silently skip — coaches will wonder why the chart is missing.
- **< 5 BIP**: Show "Not enough data yet — N balls in play recorded."
- **0 BIP / no data crawled**: Show "Charts will appear after the next sync."

**Team aggregate charts** (opponent team aggregate):
- **>= 20 BIP**: Render the spray chart. Show "Based on N balls in play against our teams."
- **10-19 BIP**: Show "Small sample — N balls in play against our teams." Do NOT render a chart (insufficient for reliable team tendency). Helps coach calibrate — 15 BIP from one game is real data, just not enough to position on.
- **< 10 BIP**: Show "Not enough data yet — N balls in play recorded."
- **0 BIP / no data crawled**: Show "Charts will appear after the next sync."

The team threshold is higher (20 vs 10) because one full game against an opponent typically yields 20-30 team BIP — below that, no reliable team tendency emerges.

BIP count is mandatory context on every chart. On the opponent scouting report, label spray data as "against our teams" (since this epic only includes games where our teams played the opponent). Per-player links in the batting table: "Only showing players with 10+ balls in play."

### TN-8: Image Dimensions and Mobile Layout
Charts render as 4×6 inch PNGs at 150 DPI (matching GC's 320×480 SVG proportion). On the dashboard, charts display as full-width inline images inside standard Tailwind card components. No side-by-side layout on mobile — portrait charts stacked vertically.

### TN-9: Accept Header
This endpoint uses a non-standard Accept header: `application/json, text/plain, */*` (web profile). It does NOT use a vendor-typed Accept header like other GC endpoints.

### TN-10: Player team_id Resolution in Loader
The `players` table has NO `team_id` column — players are cross-team entities. To determine `team_id` for each spray chart event:

1. From the file path (`data/raw/{season}/teams/{gc_uuid}/spray/{event_id}.json`), extract the crawling team's `gc_uuid`. Look up the crawling team's `teams.id`.
2. From the `games` table, look up the game by `game_id` (= `event_id` from the filename) to get `home_team_id` and `away_team_id`.
3. For each player UUID in the spray data, check `team_rosters` for both `home_team_id` and `away_team_id` to determine which team the player belongs to. Filter by `season_id` (the `{season}` path segment from the file path, e.g., `2026-spring-hs`) to avoid ambiguous matches when a player moved between teams across seasons (e.g., JV 2024 → Varsity 2025).
4. Players found in neither roster: insert a stub row in `players` (FK-safe orphan handling), then assign the non-crawling team's `team_id` as a best-guess (players not on the crawling team's roster are most likely opponents). Log a WARNING for manual review.

This approach correctly handles both own-team and opponent players from a single API response.

### TN-11: Season Isolation
Per the fresh-start philosophy, spray charts default to current-season data. The `season_id TEXT` column (added in E-158-01) stores the full season slug (e.g., `2026-spring-hs`) from the file path — no year parsing needed. Using `season_id` instead of `season_year` avoids merging data when multiple seasons share the same year (e.g., spring HS and summer legion). Dashboard queries filter by `season_id`. The player profile spray chart (E-158-05) uses the current season. The opponent detail page (E-158-06) uses the route's already-resolved `season_id` variable to support historical navigation — when a coach views last season's opponent stats, they see last season's spray data too. This prevents cross-season chart contamination. Adding the column now avoids a backfill migration later.

### TN-12: Data Coverage
Spray data is scorekeeper-dependent (~93% offensive, ~16% defensive). The `spray_chart_data` field is `null` (not empty array) when no data was recorded. Handle `null` explicitly in the loader.

## Open Questions
- None remaining after expert consultation.

## History
- 2026-03-26: Created. Expert consultation completed with DE, api-scout, UXD, baseball-coach, SE.
- 2026-03-26: Review process completed. 3 internal holistic review iterations + 2 CR spec audits + 2 Codex spec review iterations. Epic set to READY.
- 2026-03-26: All 6 stories implemented and verified. Full spray chart pipeline delivered: schema migration (006), SprayChartCrawler (player-stats endpoint), SprayChartLoader (idempotent ingestion with team_id resolution via TN-10), rendering module (exact GC field geometry, coordinate transform, hit/out colors, HR zone bubbles), player profile spray chart card (4 TN-7 threshold tiers, image endpoint), and opponent scouting spray chart (team aggregate + per-player "View spray" links). 16 total CR/Codex findings, all accepted. matplotlib + numpy added as dependencies. Epic set to COMPLETED.

### Documentation Assessment
Triggers fired: **1** (new feature: spray chart pipeline + dashboard cards), **4** (schema change: migration 006), **5** (system change: new CLI crawler/loader, new image routes). Docs-writer dispatch required for:
- `docs/admin/` — new `bb data crawl --crawler spray-chart` and `bb data load --loader spray-chart` CLI commands, migration 006, new image routes (`/dashboard/charts/spray/player/{id}.png`, `/dashboard/charts/spray/team/{id}.png`), matplotlib+numpy dependency addition
- `docs/coaching/` — new spray chart cards on player profile and opponent scouting pages, threshold behavior (TN-7 tiers), "View spray" links in batting leaders table

### Context-Layer Assessment
1. **New convention, pattern, or constraint established?** — **Yes.** The `src/charts/` package establishes a rendering module pattern (function returns PNG bytes, called from routes via `run_in_threadpool`). The image endpoint pattern (`.png` route returning `content-type: image/png` with 204 for below-threshold) is new. CLAUDE.md should document the charts package and image route pattern.
2. **Architectural decision with ongoing implications?** — **Yes.** matplotlib + numpy are new dependencies. The `src/charts/` package location (not under `src/api/`) was a deliberate SE consultation decision. The coordinate transform constants and field geometry are derived from GC's JS bundle — future chart types may reuse this approach. CLAUDE.md Data Model section should note `spray_charts` table population status change (was "unpopulated", now populated by E-158).
3. **Footgun, failure mode, or boundary discovered?** — **No.** No novel gotchas beyond what's already documented in the epic's Technical Notes.
4. **Change to agent behavior, routing, or coordination?** — **No.** Standard dispatch, no agent changes.
5. **Domain knowledge discovered that should influence agent decisions in future epics?** — **Yes.** Spray chart coverage is scorekeeper-dependent (~93% offensive, ~16% defensive). The `progenitor_team_id` pattern for opponent access via the player-stats endpoint. The TN-7 threshold tiers (10 BIP per-player, 20 BIP team aggregate) are coaching-validated decisions. These should be captured in CLAUDE.md or agent memory.
6. **New CLI command, workflow, or operational procedure introduced?** — **Yes.** `bb data crawl --crawler spray-chart` and `bb data load --loader spray-chart` are new CLI options. No new `bb` subcommand or skill, but the existing `bb data` command group gained new choices. CLAUDE.md should reflect the spray-chart crawler/loader availability.

**Verdicts**: Triggers 1, 2, 5, 6 = **yes**. Triggers 3, 4 = **no**. Claude-architect dispatch required.

### Ideas Backlog Review
- **IDEA-009** (Per-Player Per-Game Stats and Spray Charts): Trigger partially met — spray charts are now delivered. The "per-player per-game stats" portion remains independent. Consider updating the idea to note spray charts are done and narrowing scope to per-game stats only.
- **IDEA-035** (Opponent Page Redesign): E-158 added spray chart card and "View spray" links to the opponent detail page — partial progress toward this idea's scope. Remaining: proactive flags, PDF export.
- **IDEA-037** (Scouting Report Redesign): Same partial progress as IDEA-035 — spray charts now integrated.
- No ideas are fully unblocked by E-158 alone; spray charts are additive to existing pages rather than a prerequisite for other ideas.

### Vision Signals Review
26 unprocessed signals in `docs/vision-signals.md` (last curation: 2026-03-13). Signals span coaching UX, auth evolution, opponent identity, stat compilation, and dashboard customization. Recommend asking the user if they want to "curate the vision" at a natural pause.

### Per-Story Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-158-01 | 0 | 0 | 0 |
| Per-story CR — E-158-02 | 5 | 5 | 0 |
| Per-story CR — E-158-03 | 3 | 3 | 0 |
| Per-story CR — E-158-04 | 1 | 1 | 0 |
| Per-story CR — E-158-05 | 1 | 1 | 0 |
| Per-story CR — E-158-06 | 2 | 2 | 0 |
| CR integration review | 1 | 1 | 0 |
| Codex code review | 3 | 3 | 0 |
| **Total** | **16** | **16** | **0** |

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — Holistic team | 19 | 13 | 6 |
| Internal iteration 2 — CR spec audit | 3 | 1 | 2 |
| Internal iteration 2 — Holistic team | 15 | 11 | 4 |
| Internal iteration 3 — CR spec audit | 2 obs | 0 | 2 |
| Internal iteration 3 — Holistic team | 8 | 6 | 2 |
| Codex iteration 1 | 5 | 5 | 0 |
| Codex iteration 2 | 4 | 4 | 0 |
| **Total** | **~56** | **40** | **16** |
