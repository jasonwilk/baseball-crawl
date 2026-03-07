---
method: GET
path: /me/team-tile/{team_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Discovered 2026-03-07.
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
tags: [me, team]
caveats:
  - >
    ngb DOUBLE-PARSE: ngb field is a JSON-encoded string. Parse with json.loads(team["ngb"]).
related_schemas: []
see_also:
  - path: /me/teams
    reason: Full team list -- same data but as a collection
  - path: /teams/{team_id}
    reason: Full team detail with more fields (settings, scorekeeping, etc.)
---

# GET /me/team-tile/{team_id}

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns a compact team summary for the specified team -- the "tile" used in the app's team list UI.

```
GET https://api.team-manager.gc.com/me/team-tile/{team_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Response

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Team UUID |
| `name` | string | Team display name |
| `team_type` | string | User's role (`"admin"`, etc.) |
| `sport` | string | Sport |
| `season_year` | integer | Current season year |
| `season_name` | string | Season name |
| `stat_access_level` | string | Stat visibility |
| `streaming_access_level` | string | Streaming permission |
| `organizations` | array | Organization memberships |
| `ngb` | string | NGB (**JSON-encoded string -- double-parse**) |
| `user_team_associations` | array | User's roles on this team |
| `team_avatar_image` | string or null | Avatar URL (null if no avatar) |
| `created_at` | string (ISO 8601) | Team creation date |
| `public_id` | string | Public ID slug |
| `archived` | boolean | Whether team is archived |
| `record` | object | `{"wins": int, "losses": int, "ties": int}` |
| `badge_count` | integer | Count of notification badges |

## Example Response

```json
{
  "id": "72bb77d8-REDACTED",
  "name": "Lincoln Rebels 14U",
  "sport": "baseball",
  "season_year": 2025,
  "season_name": "summer",
  "stat_access_level": "confirmed_full",
  "archived": false,
  "record": {"wins": 61, "losses": 29, "ties": 2},
  "badge_count": 0
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
