---
method: GET
path: /teams/{team_id}/avatar-image
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Returns signed CloudFront URL. Discovered 2026-03-07.
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
tags: [team, media]
caveats:
  - >
    URL EXPIRES: Signed CloudFront URL has time-limited validity. Do not cache long-term.
related_schemas: []
see_also: []
---

# GET /teams/{team_id}/avatar-image

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns a signed URL for the team's avatar/logo image.

```
GET https://api.team-manager.gc.com/teams/{team_id}/avatar-image
```

## Response

| Field | Type | Description |
|-------|------|-------------|
| `full_media_url` | string (URL) | Time-limited signed CloudFront URL to the team avatar image |

URL pattern: `https://media-service.gc.com/{image-uuid}?Policy={base64}&Key-Pair-Id={id}&Signature={sig}`

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
