---
method: GET
path: /teams/{team_id}/schedule/event-series/{series_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: partial
    notes: HTTP 404 returned for series UUID 40b6a03f on 2026-03-07. Endpoint exists but series not found. Schema unknown.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [team, events]
caveats:
  - >
    HTTP 404 CONFIRMED: Series UUID 40b6a03f returned 404. The series may not exist
    for this team, or the series UUID may be from a different team's scope. Schema unknown.
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule
    reason: Full team schedule -- event-series may be referenced within schedule items
---

# GET /teams/{team_id}/schedule/event-series/{series_id}

**Status:** OBSERVED (proxy capture). HTTP 404 for series tested 2026-03-07. Schema unknown.

Returns event series details for a team. Full schema not captured.

```
GET https://api.team-manager.gc.com/teams/{team_id}/schedule/event-series/{series_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |
| `series_id` | UUID | Event series UUID |

## Investigation Status

HTTP 404 returned for series `40b6a03f-c666-4448-9c36-f33764eb3442`. The series may not exist for this team or the UUID may be from a different team's scope.

**Discovered:** 2026-03-07. **Last tested:** 2026-03-07 (404).
