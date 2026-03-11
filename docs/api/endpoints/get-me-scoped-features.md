---
method: GET
path: /me/scoped-features
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. Returns empty scoped_features map.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.scoped_features+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-11"
last_confirmed: null
tags: [me, permissions]
see_also:
  - path: /teams/{team_id}/scoped-features
    reason: Same response schema, but scoped to a team instead of the user
  - path: /organizations/{org_id}/scoped-features
    reason: Same response schema, scoped to an organization
---

# GET /me/scoped-features

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Response body empty. Schema based on observed data.

Returns feature flags scoped to the authenticated user account. Analogous to `/teams/{team_id}/scoped-features` and `/organizations/{org_id}/scoped-features` but at the user level. Observed to return an empty map.

```
GET https://api.team-manager.gc.com/me/scoped-features
```

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.scoped_features+json; version=0.0.0
```

## Response

**HTTP 200.** Single JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `scoped_features` | object | Map of feature flag names to their values. Empty map when no feature flags are active for this user. |

## Example Response

```json
{
  "scoped_features": {}
}
```

**Coaching relevance: NONE.** Feature flags for internal GC use only. Not relevant to data ingestion.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
