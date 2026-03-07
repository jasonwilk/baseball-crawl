---
method: GET
path: /teams/{team_id}/web-widgets
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 1 widget observed. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [team, user]
caveats: []
related_schemas: []
see_also: []
---

# GET /teams/{team_id}/web-widgets

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns the web widget configurations for a team.

```
GET https://api.team-manager.gc.com/teams/{team_id}/web-widgets
```

## Response

Bare JSON array of widget objects.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Widget UUID |
| `type` | string | Widget type. Observed: `"schedule"` |

## Example Response

```json
[{"id": "5417dbce-11ad-44d3-afc4-244147272961", "type": "schedule"}]
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
