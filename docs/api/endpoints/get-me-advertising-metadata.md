---
method: GET
path: /me/advertising/metadata
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
tags: [user, me]
caveats:
  - >
    PII IN TARGETING: targeting.gc_user-id_v1 contains user UUID. Treat as PII.
related_schemas: []
see_also: []
---

# GET /me/advertising/metadata

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns advertising and targeting metadata for the authenticated user. **Coaching relevance: NONE** for data ingestion.

```
GET https://api.team-manager.gc.com/me/advertising/metadata
```

## Response

| Field | Type | Description |
|-------|------|-------------|
| `ppid` | string | Publisher Provided ID -- hashed identifier for ad targeting |
| `do_not_sell` | boolean | Whether the user opted out of data selling |
| `is_staff` | boolean | Whether the user is a GameChanger staff member |
| `targeting` | object | Ad targeting key-value pairs |
| `targeting.gc_ppid_v1` | string | Same as `ppid` |
| `targeting.gc_user-id_v1` | UUID | User UUID (**PII -- redact**) |
| `targeting.gc_age-groups_v1` | string | Comma-separated age groups coached |
| `targeting.gc_comp-levels_v1` | string | Comma-separated competition levels |
| `targeting.gc_teams-sports_v1` | string | Sports involved |
| `targeting.gc_subscription-type` | string | Subscription tier |

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
