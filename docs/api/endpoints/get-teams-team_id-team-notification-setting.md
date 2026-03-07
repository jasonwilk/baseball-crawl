---
method: GET
path: /teams/{team_id}/team-notification-setting
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Schema documented. Confirmed 2026-03-07.
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
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [team, user]
caveats: []
related_schemas: []
see_also: []
---

# GET /teams/{team_id}/team-notification-setting

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns the event reminder notification setting for a team.

```
GET https://api.team-manager.gc.com/teams/{team_id}/team-notification-setting
```

## Response

```json
{"team_id": "72bb77d8-REDACTED", "event_reminder_setting": "never"}
```

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | Team UUID |
| `event_reminder_setting` | string | Event reminder frequency. Observed: `"never"`. Other values may include `"always"`, `"custom"`. |

**Discovered:** 2026-03-05. **Confirmed:** 2026-03-07.
