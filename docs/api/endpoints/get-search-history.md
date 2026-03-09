---
method: GET
path: /search/history
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Discovered 2026-03-07.
  mobile:
    status: observed
    notes: 1 hit, HTTP 200. Confirmed 2026-03-09 (session 063531). Called at app launch before user begins typing in search bar.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [search, user]
caveats: []
related_schemas: []
see_also: []
---

# GET /search/history

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns the authenticated user's recent search history. Contains team search results with public metadata including UUIDs and `public_id` values.

**Coaching relevance: LOW for analytics.** Useful for discovering team UUIDs from team names when the user has previously searched for those teams.

```
GET https://api.team-manager.gc.com/search/history
```

## Response

| Field | Type | Description |
|-------|------|-------------|
| `max_results` | integer | Maximum history entries (observed: `10`) |
| `history` | array | Ordered list of recent searches (most recent first) |
| `history[].type` | string | Result type. Observed: `"team"` |
| `history[].result` | object | The search result object |

### `result` Object (when `type = "team"`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Team UUID |
| `public_id` | string | Team public ID slug |
| `name` | string | Team display name |
| `sport` | string | Sport |
| `season` | object | `{"name": "summer", "year": 2019}` |
| `location` | object | `{"city": "...", "state": "...", "country": "..."}` |
| `staff` | array of strings | Coach/staff names (plain strings, not UUIDs) |
| `number_of_players` | integer | Player count on the team |
| `avatar_url` | string (URL, optional) | Signed CloudFront avatar URL |

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
