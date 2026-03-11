---
method: GET
path: /organizations/{org_id}/opponents
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Schema documented. 7 opponents observed. Discovered 2026-03-05.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.opponent_team:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: "7 opponents"
discovered: "2026-03-05"
last_confirmed: null
tags: [organization, opponent]
caveats:
  - >
    OBSERVED STATUS: Schema was documented from web browser headers only -- not confirmed
    via independent curl call. Response body was captured but not independently verified.
  - >
    UUID SEMANTICS: The `owning_team_id` field is the organization UUID (= path param
    `org_id`), not a team UUID. Do not use it as `team_id` in other endpoints.
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponents
    reason: Team-level opponent list with additional fields (root_team_id, progenitor_team_id)
  - path: /organizations/{org_id}/opponent-players
    reason: Bulk opponent player roster at org level (HTTP 500 -- blocked)
  - path: /organizations/{org_id}/standings
    reason: Win/loss records for all org opponents
---

# GET /organizations/{org_id}/opponents

**Status:** OBSERVED (web headers, schema documented). Response schema captured but not independently verified via curl.

Returns all opponents across all teams in the organization. Provides an org-level view of the opponent registry.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/opponents
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization identifier (from `/me/related-organizations` or team `organizations` field) |

## Response

Bare JSON array of opponent objects. 7 opponents observed.

| Field | Type | Description |
|-------|------|-------------|
| `root_team_id` | UUID | The opponent's root team UUID |
| `progenitor_team_id` | UUID | The original/canonical team UUID |
| `owning_team_id` | UUID | Organization UUID that owns this opponent record (= `org_id`) |
| `name` | string | Opponent team name |
| `is_hidden` | boolean | Whether this opponent is hidden (all `false` observed) |

## Example Response

```json
[
  {
    "root_team_id": "<team-uuid>",
    "progenitor_team_id": "<team-uuid>",
    "owning_team_id": "<org-uuid>",
    "name": "REDACTED Team 9U",
    "is_hidden": false
  }
]
```

**Discovered:** 2026-03-05.
