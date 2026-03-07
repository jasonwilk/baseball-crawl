---
method: GET
path: /me/external-calendar-sync-url/team/{team_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: observed
    notes: 1 hit, status 200. Discovered 2026-03-05.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: null
tags: [me, calendar]
caveats:
  - >
    NOT RELEVANT FOR DATA INGESTION: Returns a URL for subscribing to the team's
    schedule in an external calendar application (iCal/Google Calendar). Not useful
    for analytics pipelines.
  - >
    SCHEMA UNKNOWN: Likely returns a single-field object with a webcal:// or
    https:// URL. Not confirmed.
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule
    reason: Authenticated team schedule (full event objects with game data)
---

# GET /me/external-calendar-sync-url/team/{team_id}

**Status:** OBSERVED (proxy log, 1 hit, status 200). Schema not captured.

Returns a URL for subscribing to a team's schedule in an external calendar application (e.g., Apple Calendar, Google Calendar). Not relevant to data ingestion.

```
GET https://api.team-manager.gc.com/me/external-calendar-sync-url/team/{team_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team identifier |

## Response

Schema not captured. Expected: single-field object with a calendar subscription URL.

**Discovered:** 2026-03-05.
