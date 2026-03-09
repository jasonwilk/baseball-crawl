---
method: GET
path: /teams/{team_id}/import-summary
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: confirmed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). 1 hit, HTTP 200.
      Accept: application/vnd.gc.com.none+json; version=0.0.0.
      Called on opponent team_id cb509002-0bb4-43f1-aecf-d4358c63e50a, which is
      NOT our team. This is a check on a potential opponent team's import status,
      called during the opponent search-and-add flow.
accept: "application/vnd.gc.com.none+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: "2026-03-09"
tags: [team, opponent, stats]
caveats:
  - >
    OPPONENT TEAM ACCESS: Called on an opponent team UUID (not our own team_id),
    confirming this endpoint is accessible for any team UUID (not own-team-only).
    The team cb509002-0bb4-43f1-aecf-d4358c63e50a was being evaluated as a potential
    opponent to import.
  - >
    RESPONSE BODY UNKNOWN: Body schema not captured (proxy logs metadata only).
    Based on the endpoint name and context (pre-import check), the response likely
    contains information about what data is available for import from this team:
    whether they have game stats, a roster, etc. Possible fields: has_stats (bool),
    game_count (int), last_updated (timestamp).
  - >
    FLOW CONTEXT: This was called at 06:29:52, after 3 rounds of /search/opponent-import
    and before POST /opponent/import at 06:30:07. The ~15-second gap suggests the
    user reviewed this data before confirming the import.
see_also:
  - path: /search/opponent-import
    reason: Search endpoint called before this during opponent import flow
  - path: /post-teams-team_id-opponent-import
    reason: The import action called after reviewing this summary
  - path: /teams/{team_id}/season-stats
    reason: Detailed stats (available after import)
---

# GET /teams/{team_id}/import-summary

**Status:** CONFIRMED (mobile proxy, 1 hit, HTTP 200). Response body not captured. Last verified: 2026-03-09.

Returns a summary of available import data for a team. Called during the opponent import flow to check whether a candidate opponent team has stats/data that can be imported. Accessible for any team UUID, not just your own team.

```
GET https://api.team-manager.gc.com/teams/{team_id}/import-summary
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | The UUID of the team to check (may be an opponent's UUID) |

## Request Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.none+json; version=0.0.0
User-Agent: Odyssey/2026.8.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0
```

## Response

**HTTP 200.** Body not captured. Based on the endpoint name and flow context, expected to describe the importable data available for this team:

```json
{
  "has_stats": true,
  "game_count": 12,
  "last_updated": "2025-10-01T00:00:00Z",
  "season": "fall_2025"
}
```

Actual schema must be verified by capture.

## Opponent Import Flow Position

This endpoint appears between search and import in the opponent add sequence:

1. `GET /search/opponent-import?name=...` -- find candidate teams
2. **`GET /teams/{candidate_uuid}/import-summary`** -- check available data
3. `POST /teams/{my_team_id}/opponent/import` -- confirm the import

The summary data likely drives the UI display showing the user what data they would get by importing this opponent (e.g., "12 games of stats available").

## Known Limitations

- Response schema not captured -- needs follow-up.
- Unclear whether all team UUIDs return 200 or whether non-existent / private teams return 404/403.

**Discovered:** 2026-03-09. Session: 2026-03-09_062610 (mobile/iOS).
