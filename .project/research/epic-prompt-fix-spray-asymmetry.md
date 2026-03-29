# Epic Planning Prompt: Fix Spray Charts for Reports

## Context for PM

This prompt is based on live API verification performed 2026-03-29 by the main session and api-scout. Full evidence is at `.project/research/spray-endpoint-asymmetry.md`. Two prior epics (E-176, E-158) built on a false premise about the spray endpoint -- this epic corrects the damage.

---

## The Problem

Spray charts do not appear in standalone scouting reports for any tracked team that lacks a `gc_uuid`. The entire problem reduces to one thing: **we need the scouted team's own `gc_uuid` to call the spray endpoint, and we don't have it.**

### Why We Need the Team's OWN gc_uuid

The spray endpoint (`GET /teams/{team_id}/schedule/events/{event_id}/player-stats`) is **team-scoped**. Live API calls on 2026-03-29 proved:

| Scenario | Spray data returned |
|----------|-------------------|
| Call with Team A's own UUID for a game A played in | Both teams' spray data (A's batters + opponent batters) |
| Call with Opponent B's UUID for the same game | **Only B's data** (A's batters are absent) |
| Call with an unrelated team's UUID | 404 Not Found |

We only need the scouted team's spray data. One call with the scouted team's own gc_uuid returns it. But without that UUID, we get nothing useful -- calling with any other UUID returns someone else's spray data.

### What E-176 Got Wrong

E-176 assumed the endpoint returns both teams' data "regardless of which team's UUID is used." It added a "boxscore-UUID fallback" that extracts the *opponent's* UUID from cached boxscores. Because of the asymmetry, this fetches spray data for the opponents, not the scouted team.

**Evidence from Lincoln Sox 12U (team 51, `gc_uuid=NULL`, report slug `Qr1YBRqZQGuvPaVw`):**
- 56 games crawled via boxscore-UUID fallback
- 2,021 spray events loaded -- all attributed to 31 different opponent teams, 0 to team 51
- Report renders with 0 spray chart images
- ~30 orphan team rows created as side effects

### Why gc_uuid Resolution Fails for Report-Generated Teams

The E-176-03 gc_uuid resolver has three tiers, all of which fail for teams added via the "generate report" flow (paste a GC URL):

1. **Tier 1 (member boxscores)**: Requires shared games between the target team and a member team. Report-generated teams have zero shared games. Always fails.
2. **Tier 2 (progenitor_team_id)**: Requires opponents.json cache from member team crawl. No member-team link exists. Always fails.
3. **Tier 3 (POST /search)**: Could work via name matching, but isn't wired into the report generator flow.

For Lincoln Sox 12U (12U travel ball, unrelated to our HS Freshman Grizzlies member team), all three tiers fail.

---

## What Needs to Happen

The fix has two parts: stop doing the wrong thing, and find a way to do the right thing.

### 1. Remove the Boxscore-UUID Fallback

The fallback in `ScoutingSprayChartCrawler` (`_build_boxscore_uuid_map`, `_crawl_team_season_with_uuid_map`) is actively harmful -- it fetches data for the wrong team and creates orphan team/spray rows. Remove it. When `gc_uuid` is NULL, log a message and skip. Spray charts are unavailable for that team.

### 2. Resolve gc_uuid from public_id

This is the core problem. The report generator has the team's `public_id` (from the pasted URL) but needs the `gc_uuid` for the spray endpoint.

**Confirmed solution: `POST /search` with `public_id` filtering** (verified live 2026-03-29)

The report generator already fetches the team name from `GET /public/teams/{public_id}` in step 1b. After that:

1. `POST /search` with `{"name": "<team_name>"}` (Content-Type: `application/vnd.gc.com.post_search+json; version=0.0.0`)
2. Each hit in `response.hits[]` contains `result.id` (gc_uuid) and `result.public_id`
3. Filter for `result.public_id == our_public_id` — **exact match, zero ambiguity**
4. Take `result.id` — that's the `gc_uuid`

**Proof** (Lincoln Sox 12U, `public_id=0kfqCjpbDcSH`):
- Search for "Lincoln Sox 12U" → 33 results (multiple seasons/levels)
- Result #2: `public_id=0kfqCjpbDcSH`, `id=03b1e8ec-123e-47bb-bc0c-c5d80fba8acf`
- Called spray endpoint with that UUID → 23 offense players (11 Lincoln Sox + 12 opponent)
- Lincoln Sox's own spray data is present. This is the missing piece.

This costs 1 API call per report generation. The resolved `gc_uuid` should be stored on the team row so subsequent operations (dashboard scouting, re-reports) don't need to search again.

**Edge case**: If the search returns no hit with a matching `public_id` (team deleted from GC, very obscure name, etc.), spray charts are unavailable. The report should render cleanly without them -- which it already does.

### 3. Correct Documentation

The "both teams" claim appears in:
- `CLAUDE.md` (spray chart pipeline section)
- `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md`
- `docs/api/flows/spray-chart-rendering.md`

Replace with the accurate asymmetric behavior: returns both teams only when called with the team whose schedule contains the game.

### 4. Clean Up Orphan Data (Optional)

The ~2,021 spray events for opponents (teams 52-82) and the ~30 orphan team rows are side effects of the broken fallback. They're harmless but messy. Could be a cleanup story or left alone.

---

## Scope Boundaries

### In Scope
- Remove boxscore-UUID fallback from scouting spray crawler
- Investigate and implement public_id → gc_uuid resolution (if viable)
- Correct API documentation
- Graceful degradation when spray charts are unavailable

### Out of Scope
- Spray chart rendering logic (works when data exists)
- Member-team spray pipeline (uses own UUID, works correctly)
- Report generation flow redesign beyond the spray fix

---

## Key Files

| File | Role |
|------|------|
| `src/gamechanger/crawlers/scouting_spray.py` | Broken boxscore-UUID fallback (lines 360-507) |
| `src/reports/generator.py` | Report generator; calls `_crawl_and_load_spray()` at line 551 |
| `src/gamechanger/resolvers/gc_uuid_resolver.py` | Three-tier resolver; needs wiring for report flow |
| `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md` | Incorrect "both teams" claim |
| `docs/api/flows/spray-chart-rendering.md` | Incorrect "both teams" claim |
| `CLAUDE.md` | Incorrect claim in spray chart pipeline section |
| `.project/research/spray-endpoint-asymmetry.md` | Full evidence from live API verification |

---

## Pre-Verified Facts (No Further Investigation Needed)

These were verified with live API calls on 2026-03-29. The planner can treat them as ground truth:

1. **`POST /search` returns `gc_uuid` and `public_id` per hit.** Searching by name, then filtering hits by `public_id`, yields an exact `gc_uuid` match. Confirmed for Lincoln Sox 12U (`0kfqCjpbDcSH` → `03b1e8ec`).

2. **The spray endpoint with that resolved `gc_uuid` returns the scouted team's spray data.** Called with `03b1e8ec` → 23 offense players (11 Lincoln Sox, 12 opponent). This is the data the report needs.

3. **The spray endpoint is asymmetric.** Calling with an opponent's UUID returns only the opponent's spray data. Calling with an unrelated UUID returns 404. Only the team's OWN UUID yields their batters' spray data.

4. **The boxscore-UUID fallback is harmful.** It fetches opponents' data, creates ~30 orphan team rows, and produces 0 useful spray rows for the scouted team.
