---
method: GET
path: /organizations/{org_id}/events
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Empty array for travel ball org. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.organization_schedule_event:list+json; version=0.1.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [organization, events]
caveats:
  - >
    EMPTY FOR TRAVEL BALL ORG: Returned [] for travel ball org (87452e66). Likely populated
    for organized league orgs (e.g., high school programs with league game calendars).
related_schemas: []
see_also:
  - path: /organizations/{org_id}/game-summaries
    reason: Game summaries at org level (also empty for travel ball org)
---

# GET /organizations/{org_id}/events

**Status:** CONFIRMED LIVE -- 200 OK (empty array). Last verified: 2026-03-07.

Returns events (scheduled games/practices) for an organization. Full schema unknown -- returned empty array `[]` for the travel ball org tested.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/events
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

## Investigation Status

Response was `[]` for travel ball org `87452e66`. Endpoint likely populated for organized league orgs with league game calendars. Full response schema not captured.

**Discovered:** 2026-03-07. **Confirmed (empty):** 2026-03-07.
