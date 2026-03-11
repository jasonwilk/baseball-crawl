---
method: GET
path: /me/person-external-associations
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. HTTP 200. 1 record observed.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.person_external_associations:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: "1 record"
discovered: "2026-03-11"
last_confirmed: null
tags: [me, user]
see_also:
  - path: /teams/{team_id}/external-associations
    reason: External system links at the team level (MaxPreps, USSSA)
---

# GET /me/person-external-associations

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Schema based on observed data.

Returns external system associations for the authenticated user's person identity. Maps the GameChanger internal `person_id` to external organization identifiers (e.g., legacy GameChanger MongoDB user IDs).

```
GET https://api.team-manager.gc.com/me/person-external-associations
```

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.person_external_associations:list+json; version=0.0.0
```

## Response

**HTTP 200.** JSON array of external association objects.

| Field | Type | Description |
|-------|------|-------------|
| `[].person_id` | UUID | The user's internal GC person UUID |
| `[].external_id` | string | Identifier in the external system |
| `[].external_organization` | string | Name of the external system. Observed: `"gamechanger"` (appears to be a legacy MongoDB document ID). |

## Example Response

```json
[
  {
    "person_id": "00000000-REDACTED",
    "external_id": "5b81f401cebf2500199d6715",
    "external_organization": "gamechanger"
  }
]
```

**Note:** The `external_organization: "gamechanger"` value with a MongoDB-format `external_id` suggests this maps the new UUID-based identity system to the legacy GC user record.

**Coaching relevance: NONE.** Internal identity plumbing. Not relevant to data ingestion.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
