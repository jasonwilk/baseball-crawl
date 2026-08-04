---
method: GET
path: /organizations/{org_id}/standings
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 6 teams with all-zero data for travel ball org. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.team_record:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [organization, stats]
caveats:
  - >
    ALL-ZERO FOR TRAVEL BALL ORG: the organization used for testing (a `travel`-subtype org)
    returned 6 teams with all zeros. Schema is fully populated for org types that track
    standings (e.g., high school leagues with scheduled in-conference games). The org's real
    UUID prefix appeared here in prose until 2026-08-04; an 8-char prefix is an identifier and
    the PII denylist cannot catch it, so it was removed by reading rather than by scanning.
related_schemas: []
see_also:
  - path: /organizations/{org_id}/team-records
    reason: >
      Returns identical schema. Re-checked 2026-08-04: still byte-identical on every org
      tested, so the "may be same data with different semantic intent" question is STILL OPEN
      -- five months on, no evidence has separated them.
  - path: /me/related-organizations
    reason: Source of org_id values for related organizations
---

# GET /organizations/{org_id}/standings

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns win/loss standings for all teams in an organization. Same schema as `GET /organizations/{org_id}/team-records`.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/standings
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

## Response

Bare JSON array of team standing records.

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | Team UUID |
| `home` | object | Home game record: `{wins, losses, ties}` |
| `away` | object | Away game record (same shape as `home`) |
| `overall` | object | Overall record (same shape as `home`) |
| `last10` | object | Last 10 games record (same shape as `home`) |
| `winning_pct` | float | Overall winning percentage (0.0 to 1.0) |
| `runs` | object | Run differential data |
| `runs.scored` | integer | Total runs scored |
| `runs.allowed` | integer | Total runs allowed |
| `runs.differential` | integer | `scored - allowed` |
| `streak` | object | Current win/loss streak |
| `streak.count` | integer | Length of current streak |
| `streak.type` | string | `"win"` or `"loss"` |

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
