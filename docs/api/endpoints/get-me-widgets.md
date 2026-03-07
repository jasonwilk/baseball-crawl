---
method: GET
path: /me/widgets
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Returns empty widgets array. Discovered 2026-03-07.
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
tags: [user, me]
caveats: []
related_schemas: []
see_also:
  - path: /teams/{team_id}/web-widgets
    reason: Team-level widgets (confirmed populated with schedule widget)
---

# GET /me/widgets

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns widget configurations for the authenticated user.

```
GET https://api.team-manager.gc.com/me/widgets
```

## Response

```json
{"widgets": []}
```

Empty `widgets` array observed.

**Discovered:** 2026-03-07. **Confirmed (empty):** 2026-03-07.
