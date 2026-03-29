# E-186: Fix Spray Charts for Standalone Reports

## Status
`COMPLETED`

## Overview
Spray charts do not appear in standalone scouting reports for any tracked team that lacks a `gc_uuid`. This is the third attempt at fixing spray chart scouting (after E-158 and E-176). The root cause is a false premise embedded across code and documentation: that the spray endpoint returns both teams' data regardless of which team's UUID is used. Live API verification on 2026-03-29 proved the endpoint is **asymmetric** -- it returns both teams' data ONLY when called with the owning team's own gc_uuid. This epic removes the harmful boxscore-UUID fallback, wires in a verified gc_uuid resolution path, corrects documentation, and codifies the resolution pattern into the context layer.

## Background & Context
Two prior epics built on a false premise about the spray endpoint:

- **E-158** (Spray Charts): Original implementation. Documented the endpoint as "returns both teams regardless of which UUID" -- an incorrect claim that was never verified with controlled testing.
- **E-176** (Fix Spray Scouting): Added a boxscore-UUID fallback for teams without gc_uuid. Because of the asymmetry, this fetches spray data for the *opponents*, not the scouted team. Evidence: Lincoln Sox 12U (team 51) report crawled 56 games, loaded 2,021 events -- ALL attributed to opponents, ZERO to team 51. Also created ~30 orphan team rows.

**Live API Verification (2026-03-29)** confirmed:

| Scenario | Result |
|----------|--------|
| Call with team's OWN gc_uuid | Both teams' spray data (own + opponent) |
| Call with OPPONENT's gc_uuid | Only opponent's data (own team absent) |
| Call with UNRELATED gc_uuid | 404 Not Found |

**Verified fix**: `POST /search` by team name, filter hits by `public_id` exact match, extract `id` = gc_uuid. Confirmed for Lincoln Sox 12U (`public_id=0kfqCjpbDcSH` -> `gc_uuid=03b1e8ec`). Called spray endpoint with that UUID -> 23 offense players (11 Lincoln Sox + 12 opponent).

Full evidence: `.project/research/spray-endpoint-asymmetry.md` and `.project/research/epic-prompt-fix-spray-asymmetry.md`.

No expert consultation required for coaching value -- this is a bug fix restoring intended behavior. SE consulted on implementation approach. CA consulted on context-layer placement. UXD consulted on graceful degradation.

## Goals
1. Spray charts appear in standalone reports for teams whose gc_uuid can be resolved via POST /search + public_id filtering
2. The harmful boxscore-UUID fallback is completely removed from the scouting spray crawler
3. Resolved gc_uuid values are persisted on the team row for reuse by subsequent operations
4. All documentation containing the false "both teams" claim is corrected to describe the actual asymmetric behavior
5. The public_id-to-gc_uuid bridge pattern is codified in the context layer so agents instinctively reach for it
6. Zero broken tests remain (including the two pre-existing E-185 test failures)

## Non-Goals
- Spray chart rendering logic changes (works when data exists)
- Member-team spray pipeline changes (uses own UUID, works correctly)
- Report generation flow redesign beyond the spray fix
- Cleanup of orphan data from the broken fallback (harmless side-effect data)
- Modifying the existing three-tier gc_uuid resolver cascade (the new resolution is a separate, simpler path)
- Offline/cached gc_uuid resolution (the single POST /search call per report is acceptable)

## Success Criteria
- Generating a report for a team with only a `public_id` (no pre-existing `gc_uuid`) produces spray charts when the POST /search resolves a gc_uuid
- Generating a report for a team whose gc_uuid cannot be resolved renders cleanly without spray charts (no crash, no wrong data)
- The `_build_boxscore_uuid_map` and `_crawl_team_season_with_uuid_map` methods no longer exist in `src/gamechanger/crawlers/scouting_spray.py`
- `CLAUDE.md`, the player-stats endpoint doc, and the spray chart rendering flow doc all describe the asymmetric behavior accurately
- All tests pass (including the two previously failing E-185 tests)
- The bridge pattern is documented in a context-layer file that agents encounter when working on gc_uuid resolution

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-186-01 | Remove boxscore-UUID fallback and fix test failures | DONE | None | SE |
| E-186-02 | Wire gc_uuid resolution into report generator | DONE | E-186-01 | SE |
| E-186-03 | Correct API documentation and CLAUDE.md | DONE | None | CA |
| E-186-04 | Codify public_id-to-gc_uuid bridge pattern | DONE | E-186-03 | CA |

## Dispatch Team
- software-engineer (E-186-01, E-186-02)
- claude-architect (E-186-03, E-186-04)

## Technical Notes

### TN-1: Spray Endpoint Asymmetric Behavior (Verified 2026-03-29)

`GET /teams/{team_id}/schedule/events/{event_id}/player-stats` is team-scoped:

- **Owning team perspective** (team whose schedule includes the game): returns BOTH teams' spray data. The `team_id` in the response matches the URL parameter.
- **Opponent/participant perspective** (a team that played in the game but is not the schedule owner): returns ONLY that team's own spray data. The owning team's batters are absent.
- **Unrelated team**: 404.

"Owning" means: the team whose `GET /teams/{team_id}/schedule` returns this game. For scouting, this means we need the scouted team's OWN gc_uuid.

**Canonical vocabulary** (use consistently in all docstrings, docs, and code comments across all stories): **owning team** = the team whose schedule contains the game; **participant** = a team that played in the game but does not own the schedule entry.

### TN-2: gc_uuid Resolution via POST /search + public_id Filtering

The report generator already fetches the team name from `GET /public/teams/{public_id}` in Step 1b. After that:

1. `POST /search` with body `{"name": "<team_name>"}` and Content-Type `application/vnd.gc.com.post_search+json; version=0.0.0`
2. Each hit in `response.hits[]` contains `result.id` and `result.public_id`. Note: `result.id` is documented as `progenitor_team_id` in the API spec (`docs/api/endpoints/post-search.md`) -- this is the canonical GC team UUID, stored in `teams.gc_uuid`.
3. Filter for `result.public_id == our_public_id` -- exact match, zero ambiguity
4. Take `result.id` -- that is the gc_uuid (= `progenitor_team_id`)

The resolved gc_uuid is stored on the team row (`UPDATE teams SET gc_uuid = ? WHERE id = ? AND gc_uuid IS NULL`). The conditional update ensures we never overwrite an existing gc_uuid.

**Edge case**: If the search returns no hit with a matching public_id (team deleted from GC, name mismatch, etc.), spray charts are unavailable. The report renders without them.

### TN-3: Boxscore-UUID Fallback Removal Scope

Three code elements in `src/gamechanger/crawlers/scouting_spray.py` must be removed:

1. `_build_boxscore_uuid_map` method (lines 360-414): Extracts opponent UUIDs from cached boxscore files
2. `_crawl_team_season_with_uuid_map` method (lines 416-508): Calls spray endpoint with per-game opponent UUIDs
3. Fallback path in `crawl_team` method (lines 237-263): The `gc_uuid is None` branch that invokes the above two methods

After removal, when `gc_uuid` is None, `crawl_team` logs an INFO message and returns an empty `CrawlResult`.

The module docstring (lines 1-47) must be updated to remove the boxscore-UUID fallback description and the false "both teams regardless of which UUID" claim.

### TN-4: Test Failure Fix (E-185 Regression)

Two tests in `tests/test_report_renderer.py` fail:
- `test_spray_charts_as_base64_data_uris`
- `test_spray_chart_render_failure_is_non_fatal`

Root cause: Both use `patch("src.charts.spray.render_spray_chart")` but the renderer uses a deferred import (`from src.charts.spray import render_spray_chart` inside a function). At patch time, the `src.charts.spray` module has not been imported, so the patch target does not exist. Fix: add `import src.charts.spray` before each `patch()` call to force the module into `sys.modules`.

### TN-5: Documentation Corrections

The false "both teams" claim appears in three active documentation files:

1. **`CLAUDE.md`** (line ~128): "one call returns both teams' spray data per game" -- correct to describe asymmetric behavior
2. **`docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md`**: Multiple locations claim "Both teams" without qualification. The "Both teams" column in the comparison table (line 279), the frontmatter (line 10-11), the status line (line 77), overview (line 79), and "What Was Validated" section must be corrected.
3. **`docs/api/flows/spray-chart-rendering.md`** (line 44): "both teams' all players in a single API call" -- must be qualified with "when called with the owning team's UUID"

Archived epic files (E-158, E-176) are frozen per project convention and are NOT modified.

### TN-6: Graceful Degradation

When spray charts are unavailable (gc_uuid unresolvable), the report currently omits the "Batter Tendencies" section silently. This is acceptable behavior -- the report renders cleanly without it. No UX changes are required for this epic. (If UXD recommends a placeholder message, that can be captured as a follow-up idea.)

### TN-7: `_crawl_and_load_spray` Signature Change

The `_crawl_and_load_spray` function in `src/reports/generator.py` currently takes `(client, public_id, season_id)`. After E-186-02, it needs the resolved `gc_uuid` passed through so the spray crawler uses the correct UUID. The function should accept an optional `gc_uuid` parameter and pass it to `ScoutingSprayChartCrawler.crawl_team()`.

## Open Questions
None -- all questions resolved by live API verification and expert consultation.

## History
- 2026-03-29: Created. Third attempt at fixing spray charts after E-158 and E-176. Based on live API verification proving endpoint asymmetry.
- 2026-03-29: Set to READY after internal review.
- 2026-03-29: Set to ACTIVE, dispatch started.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 5 | 4 | 1 |
| Internal iteration 1 -- Holistic team (PM) | 5 | 3 | 2 |
| **Total** | **10** | **7** | **3** |

Codex validation: skipped (findings were spec-precision, not architectural).

- 2026-03-29: All stories DONE, epic COMPLETED.

### Review Scorecard (Dispatch)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-186-01 | 0 | 0 | 0 |
| Per-story CR -- E-186-02 | 2 | 1 | 1 |
| **Total** | **2** | **1** | **1** |

E-186-03 and E-186-04 were context-layer-only -- CR skipped, PM verified ACs alone.

### Documentation Assessment
No documentation impact -- this epic fixes internal pipeline behavior and corrects existing documentation. No new user-facing features requiring `docs/admin/` or `docs/coaching/` updates.

### Context-Layer Assessment
| Trigger | Verdict | Notes |
|---------|---------|-------|
| New convention/pattern | YES | gc-uuid-bridge.md rule -- codified in E-186-04 |
| Architectural decision | YES | Spray endpoint asymmetry -- codified in E-186-03 |
| Footgun/failure mode | YES | False "both teams" premise -- warned in gc-uuid-bridge.md |
| Agent behavior change | No | |
| Domain knowledge | YES | Spray endpoint behavior -- codified in E-186-03 |
| New CLI command/workflow | No | |

All "yes" items were codified during the epic itself (stories 03 and 04). No additional context-layer work needed.
