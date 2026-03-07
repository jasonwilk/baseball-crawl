---
method: GET
path: /me/archived-teams
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 8 records. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: data/raw/me-archived-teams-sample.json
raw_sample_size: "8 archived team records (2019-2023, ages 8U-13U)"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [me, team]
caveats:
  - >
    ngb DOUBLE-PARSE: ngb field is a JSON-encoded string (same quirk as /me/teams and
    /teams/{team_id}). Parse with json.loads(team["ngb"]) to get the list.
related_schemas: []
see_also:
  - path: /me/teams
    reason: Active teams -- same schema, no archived field
  - path: /me/teams-summary
    reason: Lightweight summary of archived team count and year range
---

# GET /me/archived-teams

**Status:** CONFIRMED LIVE -- 200 OK. 8 records. Last verified: 2026-03-07.

Returns the list of archived (prior season) teams the authenticated user was associated with. Schema is identical to `GET /me/teams` response objects.

**Coaching relevance: HIGH.** Gives access to historical season team objects for multi-season longitudinal analysis.

```
GET https://api.team-manager.gc.com/me/archived-teams
```

## Response

Bare JSON array of archived team objects. Same schema as active teams in `GET /me/teams`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Team UUID |
| `name` | string | Team display name |
| `team_type` | string | User's role (`"admin"`, etc.) |
| `city` | string | City |
| `state` | string | State/province |
| `country` | string | Country |
| `age_group` | string | Age group (e.g., `"13U"`) |
| `competition_level` | string | `"club_travel"`, `"school"`, `"recreational"` |
| `sport` | string | Sport |
| `season_year` | integer | Season year |
| `season_name` | string | Season name (`"summer"`, `"fall"`) |
| `stat_access_level` | string | Stat visibility setting |
| `scorekeeping_access_level` | string | Scorekeeping permission level |
| `streaming_access_level` | string | Streaming permission level |
| `organizations` | array | Organization memberships |
| `ngb` | string | National Governing Body (**JSON-encoded string -- double-parse**) |
| `user_team_associations` | array | User's roles on this team (e.g., `["family", "manager"]`) |
| `team_avatar_image` | string (URL) | Signed CloudFront avatar URL |
| `created_at` | string (ISO 8601) | Team creation date |
| `public_id` | string | Public ID slug |
| `archived` | boolean | Always `true` in this response |
| `record` | object | Season record: `{"wins": int, "losses": int, "ties": int}` |

**Additional fields observed in actual sample (2026-03-07):**
- `paid_access_level`: optional string, value `"premium"` on older teams (2019-2021); absent on newer records (2022+). Likely migrated to subscription system.
- `team_avatar_image`: may be absent on some teams (seen absent on 2 of 8 records in sample -- older teams from 2021 and before).

**Discovered:** 2026-03-07. **Confirmed with raw sample:** 2026-03-07.
