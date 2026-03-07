---
method: GET
path: /organizations/{org_id}/avatar-image
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: observed
    notes: 2 hits, status 200. Discovered 2026-03-05.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: null
tags: [organization, media]
caveats:
  - >
    SCHEMA UNKNOWN: Likely returns a `full_media_url` signed CloudFront URL, matching
    the pattern of GET /teams/{team_id}/avatar-image, but this has not been confirmed.
related_schemas: []
see_also:
  - path: /teams/{team_id}/avatar-image
    reason: Team avatar -- same pattern, schema confirmed
---

# GET /organizations/{org_id}/avatar-image

**Status:** OBSERVED (proxy log, 2 hits, status 200). Schema not captured.

Returns avatar/logo image metadata for the organization. Likely returns a signed CloudFront URL following the same pattern as `GET /teams/{team_id}/avatar-image`.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/avatar-image
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization identifier |

## Response

Schema not captured. Expected: object with `full_media_url` (signed CloudFront URL), following the team avatar pattern.

**Discovered:** 2026-03-05.
