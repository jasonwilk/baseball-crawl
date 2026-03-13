# E-104: Athlete Profile Endpoint Probe -- Opponent Player Access

## Status
`READY`

## Overview
Probe the four athlete-profile endpoints to determine whether they work for opponent players (not just own-team family/guardian-linked players). This is the linchpin question for cross-team player identity: can we go from a boxscore `player_id` to an `athlete_profile_id` and retrieve career stats for any player in GameChanger?

## Background & Context
During a 2026-03-13 vision review session, the data-engineer discovered that GameChanger has a cross-team player identity concept: `athlete_profile_id`. Key findings from proxy observation:

1. **GC `player_id` is per-team-per-roster, not per-person.** Same kid on different teams = different UUIDs. One person observed with 9 distinct `player_id` values across 9 team seasons (2019-2025).

2. **Four athlete-profile endpoints exist** (all status: OBSERVED, never independently confirmed):
   - `GET /athlete-profile/{id}` -- profile metadata (name, handle, graduation year, positions)
   - `GET /athlete-profile/{id}/players` -- career timeline: all (team, season, jersey, games_played) tuples
   - `GET /athlete-profile/{id}/career-stats-association` -- lightweight ID map: list of `player_id` UUIDs
   - `GET /athlete-profile/{id}/career-stats` -- full career stat block (~31KB)

3. **These endpoints are known to work for own-team players** (family/guardian relationship). They have NOT been tested with opponent player UUIDs from boxscores.

4. **The `GET /players/{player_id}` endpoint** returns a `person_id` field (status: OBSERVED). The relationship between `person_id` and `athlete_profile_id` is unknown -- `person_id` may BE the `athlete_profile_id`, or there may be a separate lookup needed.

5. **E-100** (team model overhaul) is adding a nullable `gc_athlete_profile_id` column to the players table. That column is useless without knowing how to populate it for opponent players.

**Why this matters**: The project serves three coach personas (USSSA youth, HS, Legion) who all need: "what do I already know about this player from prior seasons/teams?" Cross-team player identity is core to the scouting value proposition ("Familiar Faces" -- you faced this pitcher in HS, here is what he threw). Without knowing whether these endpoints work for opponents, we cannot design the data pipeline.

No expert consultation required -- this is pure API exploration work within api-scout's direct-routing domain.

## Goals
- Independently confirm all four athlete-profile endpoints work (live curl, not just proxy observation)
- Determine whether athlete-profile endpoints are accessible for opponent players
- Determine the `player_id` -> `athlete_profile_id` lookup path (direct field? separate endpoint? same UUID?)
- Document all findings in `docs/api/endpoints/` per project conventions

## Non-Goals
- Schema changes or database migrations (that is E-100's domain)
- Building a pipeline to populate `gc_athlete_profile_id` (future epic)
- Testing the `/search/opponent-import` or `/search` endpoints (separate exploration if needed)
- Mobile profile testing (web profile is sufficient for this probe)

## Success Criteria
- All four athlete-profile endpoint docs updated from OBSERVED to CONFIRMED (or documented as inaccessible with specific error codes)
- A clear answer to: "Can we call these endpoints for an opponent player's `athlete_profile_id`?"
- A clear answer to: "How do we get from a `player_id` (from a boxscore) to an `athlete_profile_id`?"
- Findings documented in a probe summary that future epics can reference

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-104-01 | Confirm athlete-profile endpoints and test opponent access | TODO | None | api-scout |
| E-104-02 | Document player_id to athlete_profile_id lookup path | TODO | E-104-01 | api-scout |

## Dispatch Team
- api-scout

## Technical Notes

### Test Strategy

The api-scout should use the web profile (`gc-token` + `gc-device-id` from `.env`) for all probes.

**Own-team test (control):** Pick a known own-team player whose `athlete_profile_id` was observed in the proxy session. Curl all four endpoints independently. This confirms the endpoints work outside of proxy observation.

**Opponent test (experiment):** Pick an opponent `player_id` from a boxscore (available in the crawled data or from a `GET /game-streams/{id}/boxscore` call). Attempt to:
1. Call `GET /players/{player_id}` with the opponent's player_id to get their `person_id`
2. Determine if `person_id` == `athlete_profile_id` (try using it as the path param)
3. If not, look for another field or endpoint that bridges the gap
4. Call all four athlete-profile endpoints with whatever ID is discovered

**Key endpoint docs to reference:**
- `/workspaces/baseball-crawl/docs/api/endpoints/get-athlete-profile-athlete_profile_id.md`
- `/workspaces/baseball-crawl/docs/api/endpoints/get-athlete-profile-athlete_profile_id-players.md`
- `/workspaces/baseball-crawl/docs/api/endpoints/get-athlete-profile-athlete_profile_id-career-stats-association.md`
- `/workspaces/baseball-crawl/docs/api/endpoints/get-athlete-profile-athlete_profile_id-career-stats.md`
- `/workspaces/baseball-crawl/docs/api/endpoints/get-players-player_id.md`

### Accept Headers (from existing docs)
- `/athlete-profile/{id}`: `application/vnd.gc.com.athlete_profile+json; version=0.0.0`
- `/athlete-profile/{id}/players`: `application/vnd.gc.com.athlete_profile_players:list+json; version=0.0.0`
- `/athlete-profile/{id}/career-stats-association`: `application/vnd.gc.com.athlete_profile_career_stats_association:list+json; version=0.0.0`
- `/athlete-profile/{id}/career-stats`: `application/vnd.gc.com.athlete_profile_career_stats+json; version=0.0.0`
- `/players/{player_id}`: `application/vnd.gc.com.player+json; version=0.1.0`

### Possible Outcomes
1. **Best case**: `person_id` from `/players/{player_id}` IS the `athlete_profile_id`, and all endpoints work for any player (including opponents). Cross-team identity is fully available.
2. **Good case**: Endpoints work for opponents but require a different lookup path (e.g., a search endpoint or roster response includes `athlete_profile_id` directly).
3. **Partial**: Endpoints work for opponents but return limited data (e.g., no career stats, only the ID map).
4. **Worst case**: Endpoints are restricted to family/guardian-linked players only. Cross-team identity requires an alternative approach.

## Open Questions
- None -- the stories are designed to answer the open questions.

## History
- 2026-03-13: Created. Motivated by vision review session discovery of cross-team player identity via `athlete_profile_id`. E-100 adding the column; this epic determines how to populate it.
