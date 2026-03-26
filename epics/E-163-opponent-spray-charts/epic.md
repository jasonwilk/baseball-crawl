# E-163: Full-Season Opponent Spray Charts and Dashboard Display

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Extend the scouting pipeline to crawl and load spray chart data for all opponent games (not just games against LSB), then wire up the dashboard to display spray charts for both member and opponent players. Currently, opponent spray data only exists for games against LSB (~3 games per opponent); this epic enables full-season spray coverage (~20-30 games per opponent) for any opponent with a `gc_uuid`. Additionally, the dashboard spray chart display is broken — image routes don't exist, template context variables are missing, and thresholds hide available data. This epic fixes all of it.

## Background & Context
The spray chart pipeline (E-158) was built for member teams only. The scouting pipeline (E-097) fetches schedules, rosters, and boxscores for opponents but not spray data. Meanwhile, the dashboard was partially wired for spray charts — the template markup and renderer (`src/charts/spray.py`) exist, but the route handlers, DB queries, and template context variables were never implemented.

The operator wants: (1) full-season spray charts for all opponents, not just BIP from games against LSB, and (2) spray charts shown for any player regardless of BIP count — "however many they have, I want a spray chart."

**API constraint**: The player-stats endpoint (`GET /teams/{team_id}/schedule/events/{event_id}/player-stats`) requires `gc_uuid` as the `team_id` parameter. Only 33/63 tracked opponents currently have `gc_uuid`. Opponents without `gc_uuid` are gracefully skipped. The `event_id` parameter equals `games.game_id` in the database (confirmed via api-scout).

**Scale**: ~200 API calls for 10 opponents × 20 games. ~21 MB raw data. Sequential with jitter per HTTP discipline.

## Goals
- Full-season opponent spray charts: crawl player-stats for every completed game on an opponent's schedule (not just games vs LSB)
- Working dashboard spray charts: image routes that render PNG spray charts from DB data for any player or team
- No artificial thresholds: show spray charts regardless of BIP count, with a sample-size note for small counts
- Graceful degradation: opponents without `gc_uuid` are skipped without error

## Non-Goals
- Spray chart analytics or derived metrics (heat maps, pull/push/center zones) — future work
- Pitcher spray charts (defensive view) — currently offensive only in the scouting context
- PDF export of spray charts — deferred to IDEA-035/IDEA-037
- Acquiring `gc_uuid` for opponents that don't have it — that's the resolver's job (E-162, IDEA-044)

## Success Criteria
- `bb data scout` (or scouting sync) fetches and stores spray chart JSON for all completed games of opponents that have `gc_uuid`
- Spray chart data loads into `spray_charts` table for opponent players
- `/dashboard/charts/spray/player/{player_id}.png` and `/dashboard/charts/spray/team/{team_id}.png` return PNG images
- Player profile page shows inline spray chart for any permitted-team player with ≥1 BIP
- Opponent print page shows per-player spray charts instead of "coming soon" placeholders
- Opponent detail page shows team-aggregate spray chart

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-163-01 | Scouting Spray Chart Crawler | TODO | None | - |
| E-163-02 | Scouting Spray Chart Loader | TODO | E-163-01 | - |
| E-163-03 | Spray Chart Image Routes | TODO | None | - |
| E-163-04 | Fix Player Profile Spray Chart Display | TODO | E-163-03 | - |
| E-163-05 | Opponent Page Spray Charts | TODO | E-163-04 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Scouting Spray Crawl Architecture

The scouting spray crawl extends `ScoutingCrawler` (or runs as a follow-up step). For each opponent with `gc_uuid`:

1. Read cached `games.json` from scouting dir (already fetched by scouting crawler)
2. Filter to completed games
3. For each completed game, call `GET /teams/{gc_uuid}/schedule/events/{event_id}/player-stats`
4. Write the full player-stats JSON response to `data/raw/{season_id}/scouting/{public_id}/spray/{event_id}.json`

**Terminology note**: The player-stats endpoint returns a full player stats response that includes spray chart data (`spray_chart_data` field). The crawler writes the entire response; the loader (E-163-02) extracts the `spray_chart_data` array from it.

The `event_id` is the `id` field from `games.json` (same as `games.game_id` in the DB — confirmed by api-scout).

The crawler needs the opponent's `gc_uuid`. Lookup: `SELECT gc_uuid FROM teams WHERE public_id = ?` (`teams.public_id` is UNIQUE). For tracked opponents, `teams.gc_uuid` IS the `progenitor_team_id` stored by the resolver — confirmed by api-scout as the correct value to pass to the player-stats endpoint. The endpoint works with any valid team UUID, not just teams the authenticated user manages (confirmed in endpoint doc: "TEAM_ID SCOPE CONFIRMED BROAD"). Opponents without `gc_uuid` are skipped with an INFO log.

Idempotency: existence-only check (same as member spray chart crawler). If the file already exists, skip. Files are written even when `spray_chart_data` is null in the response (scorekeeper did not record) — this preserves idempotency so the crawler does not re-fetch the same game.

### TN-2: Scouting Spray Load Architecture

The scouting spray loader requires a **new loader class** (`ScoutingSprayChartLoader`). The existing `SprayChartLoader.load_dir()` cannot be reused directly because it infers `gc_uuid` from the directory path (`spray_dir.parent.name`), but scouting paths use `public_id` instead. The new loader adapts the insertion logic patterns from `SprayChartLoader` but with scouting-specific resolution:

- Scouting spray files are at `data/raw/{season_id}/scouting/{public_id}/spray/`
- Team resolution: `SELECT id FROM teams WHERE public_id = ?` (not `WHERE gc_uuid = ?`)
- `season_id` derivation: extract from the directory path (`data/raw/{season_id}/scouting/...`) — the `{season_id}` component is already in the path structure
- Player team assignment: resolve players against the scouted team's roster (already loaded by scouting loader). Use the same roster lookup pattern as `SprayChartLoader._resolve_player_team_id`.
- Null `spray_chart_data`: when the JSON file's `spray_chart_data` field is null (scorekeeper did not record), skip gracefully with an INFO log — do not attempt to insert

### TN-3: Spray Chart Image Route Design

Two new route handlers in `src/api/routes/dashboard.py`:

- `GET /dashboard/charts/spray/player/{player_id}.png?season_id=<optional>` — renders per-player offensive spray chart
- `GET /dashboard/charts/spray/team/{team_id}.png?season_id=<optional>` — renders team-aggregate offensive spray chart

Both routes:
1. Query `spray_charts` table for offensive BIP events matching the player/team and season
2. Pass events to `render_spray_chart()` from `src/charts/spray.py`
3. Return `Response(content=png_bytes, media_type="image/png")`
4. Return 204 No Content when no BIP events exist
5. Use `run_in_threadpool` for DB + renderer calls (blocking I/O)
6. Require authenticated session but skip `permitted_teams` check (spray chart auth exception documented in CLAUDE.md)

When `season_id` is omitted, use the most recent season with spray data for that player/team.

### TN-4: Template Context Fix for Player Profile

The `player_profile` route in `src/api/routes/dashboard.py` (around line 1839) must pass:
- `spray_bip_count`: count of offensive BIP events for the player in the current season
- `spray_season_id`: the season_id to use for the spray chart image URL

Query: `SELECT COUNT(*) FROM spray_charts WHERE player_id = ? AND chart_type = 'offensive' AND season_id = ?`

### TN-5: Threshold Changes

The operator directive is "however many they have, I want a spray chart." New threshold behavior:
- **≥1 BIP**: Show the spray chart image with a "Based on N balls in play" subtitle
- **0 BIP**: Show "No spray chart data available" (no image request)
- **Remove**: The 10-BIP player threshold and 20-BIP team threshold gates
- **Remove**: The "Small sample", "Not enough data", and "Charts will appear after the next sync" intermediate states

The canonical empty state text is "No spray chart data available" — use this exact wording on all three surfaces: player profile, opponent detail, opponent print.

### TN-6: Opponent Detail Team Spray Chart

The opponent detail page (`src/api/templates/dashboard/opponent_detail.html`) needs a "Team Spray Chart" card showing the aggregate offensive spray chart for the opponent team. The route passes `team_spray_bip_count` and the template renders the image when ≥1 BIP exists.

### TN-7: Opponent Print Per-Player Spray Charts

Replace the `.spray-placeholder` divs (which currently show "Spray chart coming soon") in `src/api/templates/dashboard/opponent_print.html` with actual `<img>` tags pointing to the player spray chart image route. Each batter card gets a spray chart if they have ≥1 offensive BIP; otherwise show "No spray chart data available" (per TN-5).

The opponent_print route must pass per-player spray BIP counts so the template can conditionally render images vs empty state text. Pass a dict `{player_id: bip_count}` (or embed the count in the existing batting data list) so the template can look up each batter's BIP count by player_id.

**Styling constraint**: `opponent_print.html` is a standalone HTML document with embedded CSS (not Tailwind). Additions must use inline styles (e.g., `style="width:100%; display:block;"`) or the existing embedded `<style>` block. Image width should be 100% of the grid cell (the existing tendencies grid handles sizing — the cell is ~160px wide).

### TN-8: File Layout for Scouting Spray Data

```
data/raw/{season_id}/scouting/{public_id}/spray/{event_id}.json
```

This mirrors the member team layout (`data/raw/{season}/teams/{gc_uuid}/spray/{event_id}.json`) but under the scouting path.

### TN-9: CLI and Pipeline Integration

The scouting spray crawl should be triggered automatically as part of `bb data scout` (after the main scouting crawl+load). It should also be callable independently via `bb data crawl --crawler scouting-spray` for targeted runs.

**Integration path**: The scouting-spray crawler and loader must be special-cased in `src/cli/data.py` (like `bb data scout` is today), NOT routed through the `pipeline/crawl.py` factory. The factory pattern has no DB connection, so it cannot look up opponent `gc_uuid` values. The `--crawler scouting-spray` and `--loader scouting-spray` flags are handled directly in the CLI layer.

The spray load step should run as part of `bb data load --loader scouting-spray` and also automatically after the crawl in the `bb data scout` flow.

## Open Questions
None.

## History
- 2026-03-26: Created. SE, api-scout, and UXD consulted during discovery. api-scout confirmed event_id == game_id and endpoint availability.
- 2026-03-26: Iteration 1 review — 24 findings (6 CR, 18 domain expert). 19 accepted, 5 dismissed. Key fixes: removed crawl.py factory routing (B-1), fixed gc_uuid lookup to use teams.public_id (S-3), prescribed skip behavior for missing games (M-3), named all specific tests requiring update across 3 stories, added season_id derivation and null handling guidance, standardized empty state wording, added db.py and test_cli_scout.py to file lists.
- 2026-03-26: Codex spec review iteration 1 — 6 findings, 4 accepted, 2 dismissed. Key fixes: narrowed AC-5 to member/permitted-team players (opponent profiles are 403), added AC-7 edge case rationale, added ?season_id= to all image URLs, added test_cli_data.py to Files lists.
- 2026-03-26: Set to READY. Review scorecard:

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 6 | 6 | 0 |
| Internal iteration 1 — Holistic team | 18 | 13 | 5 |
| Codex iteration 1 | 6 | 4 | 2 |
| **Total** | **30** | **23** | **7** |
