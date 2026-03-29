# Spray Endpoint Asymmetry -- Research Findings

**Date**: 2026-03-29
**Investigators**: Main session + api-scout (live API calls + file analysis)

## The Incorrect Claim

CLAUDE.md, E-158, E-163, E-176, and the API endpoint doc all state:

> "The spray endpoint returns BOTH teams' data regardless of which team's UUID is used."

This is **false**. The behavior is asymmetric.

## Verified Behavior (Live API Calls 2026-03-29)

### Test Setup

Game: BBA Titans (gc_uuid `91c3eddc`) vs opponent (gc_uuid `4b335748`), event_id `6c44cdd4`.

| Call | team_id in URL | spray offense players | Both teams? |
|------|---------------|----------------------|-------------|
| Own UUID (`91c3eddc`, Titans) | Titans UUID | 14 (7 Titans + 7 opponent) | **YES** |
| Opponent UUID (`4b335748`) | Opponent UUID | 7 (0 Titans, 7 opponent) | **NO** |
| Unrelated UUID (`c8310f5c`) | Unrelated UUID | **404 Not Found** | N/A |

### Correct Characterization

The endpoint `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` is **team-scoped with asymmetric behavior**:

1. **Owning team perspective** (team whose schedule includes the game): Response includes BOTH teams' spray data in offense/defense sections. The `team_id` in the response matches the URL parameter.

2. **Opponent/participant perspective** (a team that played in the game but isn't the "owner"): Response includes ONLY that team's own spray data. Opponent batters (the "owning" team) are absent.

3. **Unrelated team**: 404 -- the endpoint validates that the team_id participated in the event_id game.

### What "Owning" Means

The schedule endpoint (`GET /teams/{team_id}/schedule`) returns games for teams the authenticated user manages. When you call player-stats with your managed team's UUID, you get the full view. When using an opponent's UUID (even if valid), you get a partial view scoped to that team only.

## Impact on Current Code

### E-176 Boxscore-UUID Fallback (Fundamentally Broken)

For teams with `gc_uuid=NULL`, the scouting spray crawler extracts opponent UUIDs from cached boxscores and calls the spray endpoint with those UUIDs. This fetches spray data **for the opponents, not for the scouted team**.

Evidence: Lincoln Sox 12U (team 51, gc_uuid=NULL) report generation:
- 56 games crawled via boxscore-UUID fallback
- 2021 spray events loaded into DB
- **0 events attributed to team 51** (all belong to opponents)
- Report renders with 0 spray charts

### gc_uuid Resolver (Cannot Help Report-Generated Teams)

The E-176-03 resolver has three tiers:
1. **Tier 1 (member boxscores)**: Requires shared games between the target team and a member team. Report-generated teams (ad-hoc URL paste) have zero shared games → always fails.
2. **Tier 2 (progenitor_team_id)**: Requires opponents.json cache from member team crawl. No member team link → always fails.
3. **Tier 3 (POST /search)**: Could work, but depends on unambiguous name match.

For Lincoln Sox 12U (pasted URL, no member-team connection), all three tiers fail.

### Even WITH gc_uuid, the Endpoint Is Still Asymmetric

If we resolved team 51's gc_uuid, calling the spray endpoint with it would return team 51's offense/defense data. But it would ALSO include opponents' spray data in the same response (per the "owning team" behavior). The current loader correctly handles this via roster-based team attribution.

The real fix needs to ensure the scouted team's OWN gc_uuid is used for API calls.

## Affected Documentation

These files contain the incorrect "both teams" claim:
- `CLAUDE.md` (line ~128, spray chart pipeline section)
- `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md` (multiple locations)
- `docs/api/flows/spray-chart-rendering.md` (line 44)
- `.project/archive/E-158-spray-charts/epic.md` (original source)
- `.project/archive/E-176-fix-spray-scouting/epic.md` (most inaccurate version)

## Possible Fix Approaches

### Approach A: Resolve gc_uuid Before Spray Crawl (Preferred)

For report-generated teams, the generator already calls the public API (`GET /public/teams/{public_id}`) in step 1b. Some public endpoints may expose identifiers that help resolve gc_uuid:
- The public team endpoint's response structure needs investigation
- The scouting boxscores contain the OTHER team's UUID; if we can cross-reference, we might find the scouted team's own UUID from the opponent's perspective

### Approach B: Call Spray Endpoint from Opponent's Perspective and Invert

Since calling with UUID-A returns both teams' data from A's perspective, if we know ANY opponent's gc_uuid AND that opponent's schedule includes the game, we could call with the opponent's UUID... but we already showed this does NOT return the scouted team's data. This approach is invalid.

### Approach C: Use Per-Player Season Endpoint

`GET /teams/{team_id}/players/{player_id}/stats` returns `offensive_spray_charts` per game. This needs a valid team_id (gc_uuid) AND individual player_ids. Still needs gc_uuid resolution.

### Approach D: Accept Spray Charts Are Unavailable Without gc_uuid

If gc_uuid cannot be resolved for a team (no member-team connection, no successful search match), spray charts are simply unavailable. The report renders without them. This is the honest fallback.
