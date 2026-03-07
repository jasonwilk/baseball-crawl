---
method: GET
path: /teams/{team_id}/public-url
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
tags: [team, user]
caveats:
  - >
    SCHEMA UNKNOWN: Likely returns a single-field object with the public web URL for
    the team (e.g., {"url": "https://web.gc.com/teams/{public_id}"}), similar to
    GET /teams/{team_id}/public-team-profile-id which returns {"id": "<slug>"}.
    Schema not captured.
related_schemas: []
see_also:
  - path: /teams/{team_id}/public-team-profile-id
    reason: Returns the public_id slug -- equivalent for API access to public endpoints
---

# GET /teams/{team_id}/public-url

**Status:** OBSERVED (proxy log, 1 hit, status 200). Schema not captured.

Returns the public web URL for a team's GameChanger profile page. Likely returns a URL of the form `https://web.gc.com/teams/{public_id}`.

```
GET https://api.team-manager.gc.com/teams/{team_id}/public-url
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team identifier |

## Response

Schema not captured. Expected: single-field object with the public URL.

**Note:** For programmatic access to the team's public API, use `GET /teams/{team_id}/public-team-profile-id` instead to retrieve the `public_id` slug.

**Discovered:** 2026-03-05.
