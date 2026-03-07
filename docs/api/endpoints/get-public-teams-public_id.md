---
method: GET
path: /public/teams/{public_id}
status: CONFIRMED
auth: none
profiles:
  web:
    status: confirmed
    notes: No gc-token or gc-device-id required. Returns 200 OK without authentication.
  mobile:
    status: not_applicable
    notes: Public endpoint -- no auth profile distinction.
accept: "application/vnd.gc.com.public_team_profile+json; version=0.1.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/public-team-profile-sample.json
raw_sample_size: "~1.2 KB"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [team, public]
related_schemas: []
see_also:
  - path: /public/teams/{public_id}/games
    reason: Game schedule and scores for this team (also no-auth)
  - path: /teams/{team_id}
    reason: Authenticated equivalent with UUID path and more fields
  - path: /teams/{team_id}/public-team-profile-id
    reason: UUID-to-public_id bridge (get public_id from a team UUID)
  - path: /teams/public/{public_id}/id
    reason: Reverse bridge -- public_id slug to UUID (requires auth despite /public/ path)
---

# GET /public/teams/{public_id}

**Status:** CONFIRMED LIVE -- 200 OK. **AUTHENTICATION: NOT REQUIRED.** Last verified: 2026-03-04.

Returns the public profile for a team identified by its `public_id` slug. No `gc-token` or `gc-device-id` required. This is the first unauthenticated endpoint confirmed in this API.

```
GET https://api.team-manager.gc.com/public/teams/{public_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Alphanumeric public ID slug (e.g., `"a1GFM9Ku0BbF"`). NOT a UUID. |

## Headers

```
Accept: application/vnd.gc.com.public_team_profile+json; version=0.1.0
User-Agent: Mozilla/5.0 ...
```

Do NOT include `gc-token` or `gc-device-id` headers on this request.

## Response

Single JSON object with team profile data.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | The `public_id` slug (NOT the UUID). The internal UUID is not exposed. |
| `name` | string | Team name |
| `sport` | string | `"baseball"` |
| `ngb` | **JSON-encoded string** | NGB affiliation. Same double-parse quirk as authenticated endpoints. |
| `location` | object | Team location (city, state, etc.) |
| `age_group` | string | Age bracket |
| `team_season` | object | Current season info with record |
| `team_season.season` | object | Season identifier |
| `team_season.record` | object | Win/loss/tie record. Uses **singular keys**: `win`, `loss`, `tie` (NOT `wins`/`losses`/`ties` as in authenticated endpoints). |
| `avatar_url` | string | Signed CloudFront URL for team avatar. Will expire -- do not cache long-term. |
| `staff` | array | Array of plain name strings (e.g., `["Jason Smith", "Mike Jones"]`). No roles, no IDs. |

**Record key normalization:** Authenticated `GET /teams/{team_id}` uses plural keys (`wins`/`losses`/`ties`) in a top-level `record` object. This endpoint uses singular keys (`win`/`loss`/`tie`) inside `team_season.record`. Parsers must handle both shapes.

## Example Response

```json
{
  "id": "a1GFM9Ku0BbF",
  "name": "Lincoln Rebels 14U",
  "sport": "baseball",
  "ngb": "[\"usssa\"]",
  "location": {
    "city": "Lincoln",
    "state": "NE"
  },
  "age_group": "14U",
  "team_season": {
    "season": {"year": 2025, "name": "summer"},
    "record": {"win": 61, "loss": 29, "tie": 2}
  },
  "avatar_url": "https://media-service.gc.com/...",
  "staff": ["Coach Smith", "Coach Jones"]
}
```

## Known Limitations

- `id` field in response is the `public_id` slug, NOT the UUID. The UUID is not exposed by this endpoint.
- Record uses singular keys (`win`/`loss`/`tie`), not plural (`wins`/`losses`/`ties`). Normalize on parse.
- `avatar_url` is a signed CloudFront URL that will expire. Do not cache long-term.
- `staff` is an array of name strings with no role or UUID information.
- `ngb` requires double-JSON-parsing.
- `team_season` reflects current season only; historical records not accessible via this endpoint.

**Discovered:** 2026-03-04. **Confirmed no-auth:** 2026-03-04.
