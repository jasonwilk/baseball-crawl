---
method: GET
path: /me/teams-summary
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Schema documented. 8 archived teams, years 2019-2023. Confirmed 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.teams_summary+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [me, team]
caveats: []
related_schemas: []
see_also:
  - path: /me/teams
    reason: Full team list with complete team objects
  - path: /me/archived-teams
    reason: Full archived team list
---

# GET /me/teams-summary

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Lightweight summary of the authenticated user's team history. Much smaller payload than `GET /me/teams` -- useful for a quick "how many teams does this user have?" check.

```
GET https://api.team-manager.gc.com/me/teams-summary
```

## Response

| Field | Type | Description |
|-------|------|-------------|
| `archived_teams` | object | Summary of archived teams |
| `archived_teams.count` | integer | Number of archived teams (observed: `8`) |
| `archived_teams.range` | object | Year range of archived teams |
| `archived_teams.range.from_year` | integer | Earliest season year (observed: `2019`) |
| `archived_teams.range.to_year` | integer | Latest season year (observed: `2023`) |

## Example Response

```json
{
  "archived_teams": {
    "count": 8,
    "range": {"from_year": 2019, "to_year": 2023}
  }
}
```

**Discovered:** 2026-03-05. **Confirmed:** 2026-03-07.
