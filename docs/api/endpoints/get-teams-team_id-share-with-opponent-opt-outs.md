---
method: GET
path: /teams/{team_id}/share-with-opponent/opt-outs
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not independently captured from web profile.
  mobile:
    status: observed
    notes: >
      1 hit, HTTP 200. Captured from iOS proxy session 2026-03-12_034919
      (app version 2026.9.0). Called during navigation of a followed team's page.
      Response body was "[]" (2 bytes) -- empty array, meaning no opt-outs configured.
accept: "application/vnd.gc.com.share_with_opponent_opt_outs+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-12"
last_confirmed: null
tags: [team, opponent]
caveats:
  - >
    RESPONSE CONFIRMED EMPTY ARRAY: The observed response was "[]" -- an empty array
    (2 bytes). When no opt-outs are configured, the endpoint returns an empty JSON array.
    The structure of non-empty entries is not yet known; a live curl against a team with
    configured opt-outs would be needed to confirm the item schema.
  - >
    POTENTIAL COACHING RELEVANCE: GameChanger has a "share stats with opponent" feature.
    When enabled, both teams in a game can see each other's player-level stats. This
    endpoint likely returns which opponents (or games) the team has chosen NOT to share
    with. Could affect what data is available via opponent-scoped endpoints.
  - >
    ACCESSIBLE ON FOLLOWED NON-OWNED TEAMS: Observed called with a team UUID the
    operator follows but does not administer. This suggests any authenticated follower
    can query opt-outs, not just team admins.
see_also:
  - path: /teams/{team_id}/opponents
    reason: Opponent registry -- opt-outs likely reference opponent team IDs
  - path: /teams/{team_id}/schedule/events/{event_id}/player-stats
    reason: Per-game player stats -- sharing opt-outs may affect data availability here
---

# GET /teams/{team_id}/share-with-opponent/opt-outs

**Status:** OBSERVED -- HTTP 200 (1 hit) in web proxy session 2026-03-12_034919.

Returns the list of opponents or games that the team has opted out of sharing stats with. GameChanger has a "share stats with opponent" feature where teams can choose to share or withhold their player-level stats from opposing teams. This endpoint returns the opt-out list.

```
GET https://api.team-manager.gc.com/teams/{team_id}/share-with-opponent/opt-outs
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Response

Returns a JSON array. When no opt-outs are configured, returns `[]`. Non-empty item schema not yet confirmed.

**Example response (empty):**
```json
[]
```

**Potential coaching relevance: MODERATE.** If an opponent has opted out of sharing stats, player-level stat data may not be available via opponent-scoped endpoints. Understanding opt-out status could explain missing data during scouting. Call this endpoint before requesting per-game player stats for a team to determine if sharing restrictions apply.

**Discovered:** 2026-03-12. Session: 2026-03-12_034919 (mobile).
